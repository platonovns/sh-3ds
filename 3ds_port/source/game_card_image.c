/* Standard PS1 layout adapted from PsyCross libapi.c. GPL-3.0-or-later.
 * Keep failed/truncated existing images untouched. Every mutation replaces a
 * complete validated image; .bak survives interrupted replacement on FAT. */
#include "game_card_image.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>

static uint8_t *image;
static int mount_error;
int game_card_mount_error(void) {return mount_error;}
static int card_fail(int stage) {mount_error=stage*10000+(errno>0 && errno<10000?errno:0);return 0;}
static char card_path[512], temp_path[520], backup_path[520];
static uint32_t le32(const uint8_t *p) {return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static unsigned link_of(const uint8_t *p) {return p[8]|p[9]<<8;}
static uint8_t checksum(const uint8_t *p) {uint8_t x=0;for(unsigned i=0;i<127;i++)x^=p[i];return x;}
static void seal(uint8_t *p) {p[127]=checksum(p);}
static int name_valid(const char *s) {return s && s[0] && strlen(s)<=20 && !strpbrk(s, ":/\\*");}
static void entry_make(uint8_t *p, unsigned state, unsigned bytes, const char *name)
{
    memset(p,0,128);p[0]=state;
    for(unsigned i=0;i<4;i++)p[4+i]=bytes>>(i*8);
    p[8]=p[9]=255;if(name)memcpy(p+10,name,strlen(name));seal(p);
}
static void fresh(uint8_t *p)
{
    memset(p,0,8192);memset(p+8192,255,GAME_CARD_BYTES-8192);
    p[0]='M';p[1]='C';seal(p);
    for(unsigned i=1;i<=15;i++)entry_make(p+128*i,0xa0,0,NULL);
    for(unsigned i=16;i<36;i++) {uint8_t *f=p+128*i;memset(f,255,4);f[8]=f[9]=255;seal(f);}
    memset(p+36*128,255,27*128);memcpy(p+63*128,p,128);
}
int game_card_validate(const uint8_t *p,size_t n)
{
    if(!p || n!=GAME_CARD_BYTES || p[0]!='M' || p[1]!='C' || checksum(p)!=p[127])return 0;
    unsigned owned=0;
    for(unsigned i=1;i<=15;i++) {
        const uint8_t *e=p+128*i;
        if(checksum(e)!=e[127] || (e[0]!=0x51 && e[0]!=0x52 && e[0]!=0x53 && e[0]!=0xa0 && e[0]!=0xa1 && e[0]!=0xa2 && e[0]!=0xa3))return 0;
        if(e[0]!=0x51)continue;
        unsigned bytes=le32(e+4),block=i,count=0,seen=0;
        if(!bytes || bytes>15*8192 || !e[10] || !memchr(e+10,0,21))return 0;
        for(;;) {
            if(block<1 || block>15 || (seen&(1u<<block)) || (owned&(1u<<block)))return 0;
            seen|=1u<<block;const uint8_t *f=p+128*block;
            if(checksum(f)!=f[127] || f[0]!=(count==0?0x51:(link_of(f)==65535?0x53:0x52)))return 0;
            count++;if(link_of(f)==65535)break;block=link_of(f)+1;
        }
        if(count!=(bytes+8191)/8192)return 0;
        owned|=seen;
        for(unsigned j=1;j<i;j++)if(p[j*128]==0x51 && !memcmp(p+j*128+10,e+10,20))return 0;
    }
    for(unsigned i=1;i<=15;i++)if((p[i*128]==0x52 || p[i*128]==0x53) && !(owned&(1u<<i)))return 0;
    return 1;
}
static int load(const char *path,uint8_t *p)
{
    FILE *f=fopen(path,"rb");if(!f){if(errno==ENOENT)return 0;card_fail(3);return -1;}
    size_t n=fread(p,1,GAME_CARD_BYTES,f);int extra=fgetc(f),bad=ferror(f);fclose(f);
    if(!bad && extra==EOF && game_card_validate(p,n))return 1;
    errno=0;card_fail(4);return -1;
}
static int commit(uint8_t *next)
{
    if(!game_card_validate(next,GAME_CARD_BYTES)){errno=0;return card_fail(5);}
    FILE *f=fopen(temp_path,"wb");if(!f)return card_fail(6);
    int ok=fwrite(next,1,GAME_CARD_BYTES,f)==GAME_CARD_BYTES;
    if(fflush(f))ok=0;
    if(ok && fsync(fileno(f)))ok=0;
    if(fclose(f))ok=0;
    if(!ok) {int e=errno;remove(temp_path);errno=e;return card_fail(7);}
    /* Do not discard the last valid main image until the staged file is durable. */
    FILE *old=fopen(card_path,"rb");
    if(old) {
        fclose(old);
        if(remove(backup_path) && errno!=ENOENT)return card_fail(8);
        if(rename(card_path,backup_path))return card_fail(9);
    }
    if(rename(temp_path,card_path)) {int e=errno;rename(backup_path,card_path);errno=e;return card_fail(10);}
    memcpy(image,next,GAME_CARD_BYTES);return 1;
}
int game_card_mount(const char *path)
{
    mount_error=0;game_card_unmount();if(!path || strlen(path)>=sizeof(card_path)){errno=0;return card_fail(1);}
    strcpy(card_path,path);snprintf(temp_path,sizeof(temp_path),"%s.tmp",path);snprintf(backup_path,sizeof(backup_path),"%s.bak",path);
    image=malloc(GAME_CARD_BYTES);if(!image)return card_fail(2);
    int status=load(card_path,image);
    if(status==1)return 1;
    /* A corrupt main is never silently reformatted or overwritten. */
    if(status<0) {game_card_unmount();return 0;}
    status=load(backup_path,image);
    if(status==1) {if(!rename(backup_path,card_path))return 1;card_fail(11);game_card_unmount();return 0;}
    if(status<0) {game_card_unmount();return 0;}
    fresh(image);
    if(commit(image))return 1;
    game_card_unmount();return 0;
}
void game_card_unmount(void) {free(image);image=NULL;}
int game_card_ready(void) {return image!=NULL;}
unsigned game_card_heap_bytes(void) {return image?GAME_CARD_BYTES:0;}
int game_card_format(void)
{
    if(!image)return 0;uint8_t *p=malloc(GAME_CARD_BYTES);if(!p)return 0;
    fresh(p);int ok=commit(p);free(p);return ok;
}
int game_card_entry(unsigned b,char name[21],unsigned *bytes)
{
    if(!image || b<1 || b>15 || image[b*128]!=0x51)return 0;
    if(name) {memcpy(name,image+b*128+10,20);name[20]=0;}
    if(bytes)*bytes=le32(image+b*128+4);return 1;
}
int game_card_find(const char *name)
{
    if(!name_valid(name))return 0;char found[21];
    for(unsigned b=1;b<=15;b++)if(game_card_entry(b,found,NULL) && !strcmp(name,found))return b;
    return 0;
}
static uint8_t *copy_image(void) {if(!image)return NULL;uint8_t *p=malloc(GAME_CARD_BYTES);if(p)memcpy(p,image,GAME_CARD_BYTES);return p;}
int game_card_create(const char *name,unsigned blocks)
{
    /* Silent Hill files occupy one block. Reject unsupported requests safely. */
    if(!image || !name_valid(name) || blocks!=1 || game_card_find(name))return 0;
    unsigned b;for(b=1;b<=15;b++)if((image[b*128]&0xf0)==0xa0)break;
    if(b>15)return 0;uint8_t *p=copy_image();if(!p)return 0;
    entry_make(p+b*128,0x51,8192,name);memset(p+b*8192,0,8192);
    int ok=commit(p);free(p);return ok?(int)b:0;
}
static int transfer(uint8_t *p,unsigned block,unsigned offset,void *buffer,unsigned n,int write)
{
    unsigned size;
    if(!buffer || !game_card_entry(block,NULL,&size) || offset>size || n>size-offset)return 0;
    while(offset>=8192) {unsigned next=link_of(p+block*128);if(next>=15)return 0;block=next+1;offset-=8192;}
    uint8_t *data=buffer;
    while(n) {
        unsigned chunk=8192-offset;if(chunk>n)chunk=n;
        if(write)memcpy(p+block*8192+offset,data,chunk);else memcpy(data,p+block*8192+offset,chunk);
        data+=chunk;n-=chunk;offset=0;
        if(n) {unsigned next=link_of(p+block*128);if(next>=15)return 0;block=next+1;}
    }
    return 1;
}
int game_card_read(unsigned b,unsigned o,void *out,unsigned n) {return image && transfer(image,b,o,out,n,0);}
int game_card_write(unsigned b,unsigned o,const void *in,unsigned n)
{
    uint8_t *p=copy_image();if(!p)return 0;
    int ok=transfer(p,b,o,(void*)in,n,1) && commit(p);free(p);return ok;
}
int game_card_erase(const char *name)
{
    unsigned b=game_card_find(name);if(!b)return 0;uint8_t *p=copy_image();if(!p)return 0;
    for(;;) {unsigned next=link_of(p+b*128);entry_make(p+b*128,0xa0,0,NULL);if(next==65535)break;b=next+1;}
    int ok=commit(p);free(p);return ok;
}
int game_card_rename(const char *from,const char *to)
{
    unsigned b=game_card_find(from);if(!b || !name_valid(to) || game_card_find(to))return 0;
    uint8_t *p=copy_image();if(!p)return 0;
    memset(p+b*128+10,0,21);memcpy(p+b*128+10,to,strlen(to));seal(p+b*128);
    int ok=commit(p);free(p);return ok;
}
