/* Offline oracle: original disc TIM -> private relocated VRAM -> texels. */
#include "psx_tim.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static uint16_t le16(const uint8_t *p){return p[0]|p[1]<<8;}
static uint32_t le32(const uint8_t *p){return le16(p)|((uint32_t)le16(p+2)<<16);}
static int memread(void *p,uint32_t off,void *dst,uint32_t n){memcpy(dst,(uint8_t*)p+off,n);return 0;}
static int read_disc(FILE *f,uint32_t lba,uint32_t off,void *dst,uint32_t n)
{
    uint8_t *p=dst;while(n){unsigned pos=off%2048, part=2048-pos;if(part>n)part=n;
        if(fseek(f,(long)((lba+off/2048)*2352+24+pos),SEEK_SET)||fread(p,1,part,f)!=part)return -1;
        off+=part;p+=part;n-=part;}return 0;
}
int main(int argc,char **argv)
{
    if(argc!=2)return 1;FILE *f=fopen(argv[1],"rb");if(!f)return 2;
    PsxVram *v=malloc(sizeof(*v));if(!v)return 3;
    for(unsigned id=1896;id<1915;id++) {
        uint8_t entry[12];if(read_disc(f,24,47388+id*12,entry,12))return 4;
        uint32_t word=le32(entry),lba=word&0x7ffff,size=((word>>19)&0xfff)*256;
        uint8_t *raw=malloc(size);if(!raw||read_disc(f,lba,0,raw,size))return 5;
        PsxSource source={memread,raw,size};PsxTim t;PsxTextureRegion region;
        if(psx_tim_parse(source,&t))return 6;PsxRect clut=t.clut;clut.x=0;clut.y=511;
        memset(v,0,sizeof(*v));
        if(psx_tim_upload(v,source,&t,NULL,&clut)||psx_tim_region(&t,t.image,clut,0,&region))return 7;
        for(unsigned y=0;y<t.height;y+=7)for(unsigned x=0;x<t.width;x+=7) {
            PsxTexel px;if(psx_vram_texel(v,region,x,y,&px))return 8;
            unsigned packed=4u>>t.mode, bits=4u<<t.mode;
            uint16_t value=le16(raw+t.image_offset+2*(y*t.image.w+x/packed));
            unsigned index=(value>>((x%packed)*bits))&((1u<<bits)-1);
            uint16_t expected=le16(raw+t.clut_offset+2*index);
            if(px.word!=expected){fprintf(stderr,"id %u x %u y %u\n",id,x,y);return 9;}
        }
        free(raw);
    }
    free(v);fclose(f);puts("PASS: 19 original TIMs and relocated CLUT texels");return 0;
}
