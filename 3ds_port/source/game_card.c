/* Bounded PsyQ compatibility for original SH card state machines. */
#include "game.h"
#include "game_card.h"
#include "game_card_image.h"
#include "game3ds.h"
#include <psyq/libapi.h>
#include <string.h>
#include <stdio.h>
static struct {unsigned used,enabled,pending,desc;int spec,mode;void (*callback)(void);} events[16];
static struct {unsigned block,offset,size,flags;} handles[4];
static unsigned scan;
static unsigned selected_card=1;
static int select_error;
int game_card_select_error(void) {return select_error;}
static void card_path(unsigned card,char path[64])
{
    if(card==1)strcpy(path,"sdmc:/3ds/silenthill/memcard.mcr");
    else snprintf(path,64,"sdmc:/3ds/silenthill/memcard%u.mcr",card);
}
void game_card_set_initial(unsigned card) {if(card>=1 && card<=8)selected_card=card;}
int game_card_select(unsigned card)
{
    char path[64],old[64];
    select_error=0;
    if(card<1 || card>8){select_error=100;return 0;}
    for(unsigned i=0;i<4;i++)if(handles[i].block){select_error=200+i;return 0;}
    if(card==selected_card)return 1;
    card_path(selected_card,old);card_path(card,path);
    if(!game_card_mount(path)) {select_error=game_card_mount_error();if(!game_card_mount(old))select_error=300;return 0;}
    selected_card=card;scan=0;return 1;
}
/* This card event loop and all callbacks run synchronously on the game thread. */
int PsxEnterCriticalSection(void) {return 1;}
void PsxExitCriticalSection(void) {}
static const char *filename(const char *path)
{return path && !strncmp(path,"bu00:",5)?path+5:NULL;}
int PsxCard_OpenEvent(unsigned desc,int spec,int mode,void (*callback)(void))
{
    for(unsigned i=0;i<16;i++)if(!events[i].used) {
        events[i].used=1;events[i].desc=desc;events[i].spec=spec;
        events[i].mode=mode;events[i].callback=callback;return i+1;
    }
    return -1;
}
int CloseEvent(unsigned e) {if(!e || e>16)return 0;memset(&events[e-1],0,sizeof(events[0]));return 1;}
int EnableEvent(unsigned e) {if(!e || e>16 || !events[e-1].used)return 0;events[e-1].enabled=1;return 1;}
int DisableEvent(unsigned e) {if(!e || e>16)return 0;events[e-1].enabled=0;return 1;}
int TestEvent(unsigned e) {if(!e || e>16)return 0;unsigned pending=events[e-1].pending;events[e-1].pending=0;return pending!=0;}
void DeliverEvent(unsigned desc,int spec)
{
    for(unsigned i=0;i<16;i++)if(events[i].used && events[i].enabled && events[i].desc==desc && events[i].spec==spec) {
        if(events[i].mode==EvMdINTR && events[i].callback)events[i].callback();else events[i].pending=1;
    }
}
static void done(int ok) {DeliverEvent(SwCARD,ok?EvSpIOE:EvSpTIMOUT);DeliverEvent(HwCARD,ok?EvSpIOE:EvSpTIMOUT);}
void InitCARD(int mode) {char path[64];(void)mode;memset(events,0,sizeof(events));memset(handles,0,sizeof(handles));card_path(selected_card,path);game_card_mount(path);}
int StartCARD(void) {return 1;}
int StopCARD(void) {return 1;}
void _new_card(void) {}
int _card_info(int channel) {done(channel==0 && game_card_ready());return 1;}
int _card_clear(int channel) {done(channel==0 && game_card_ready());return 1;}
int _card_load(int channel) {done(channel==0 && game_card_ready());return 1;}
int _card_write(int channel,int frame,unsigned char *data)
{
    /* Original DeviceTest writes all FF to frame 0 as a presence probe; the
     * BIOS handles it specially. Never overwrite the raw card's MC header. */
    (void)data;done(channel==0 && frame==0 && game_card_ready());return 1;
}
int PsxFile_Open(char *path,unsigned flags)
{
    const char *name=filename(path);if(!name || !game_card_ready())return -1;
    unsigned i;for(i=0;i<4;i++)if(!handles[i].block)break;if(i==4)return -1;
    int b=game_card_find(name);
    if(flags&0x200) {if(b)return -1;b=game_card_create(name,flags>>16);}
    if(!b)return -1;
    unsigned size;game_card_entry(b,NULL,&size);
    handles[i].block=b;handles[i].offset=0;handles[i].size=size;handles[i].flags=flags;
    return 0x5000+i;
}
static int index_of(int h) {return h>=0x5000 && h<0x5004 && handles[h-0x5000].block?h-0x5000:-1;}
int PsxFile_Close(int h) {int i=index_of(h);if(i<0)return -1;memset(&handles[i],0,sizeof(handles[i]));return 0;}
int PsxFile_Seek(int h,int offset,int whence)
{
    int i=index_of(h);if(i<0)return -1;
    int64_t p=(whence==0?0:whence==1?handles[i].offset:handles[i].size)+(int64_t)offset;
    if(whence<0 || whence>2 || p<0 || p>handles[i].size)return -1;
    handles[i].offset=p;return p;
}
int PsxFile_Read(int h,void *buffer,int bytes)
{
    int i=index_of(h);if(i<0 || bytes<0 || !(handles[i].flags&1))return -1;
    int ok=game_card_read(handles[i].block,handles[i].offset,buffer,bytes);
    done(ok);if(!ok){game3ds_recoverable("card read",bytes);return -1;}handles[i].offset+=bytes;return bytes;
}
int PsxFile_Write(int h,void *buffer,int bytes)
{
    int i=index_of(h);if(i<0 || bytes<0 || !(handles[i].flags&2))return -1;
    int ok=game_card_write(handles[i].block,handles[i].offset,buffer,bytes);
    done(ok);if(!ok){game3ds_recoverable("card write",bytes);return -1;}handles[i].offset+=bytes;return bytes;
}
struct DIRENTRY *PsxCard_FirstFile(char *path,struct DIRENTRY *out)
{scan=filename(path)?1:16;return PsxCard_NextFile(out);}
struct DIRENTRY *PsxCard_NextFile(struct DIRENTRY *out)
{
    if(!out)return NULL;
    while(scan<=15) {char name[21];unsigned bytes;if(game_card_entry(scan++,name,&bytes)) {
        memset(out,0,sizeof(*out));strcpy(out->name,name);out->size=bytes;return out;
    }}
    return NULL;
}
int PsxCard_Format(char *path) {return filename(path) && game_card_format();}
int PsxCard_Erase(char *path) {const char *n=filename(path);return n && game_card_erase(n);}
int PsxCard_Rename(char *from,char *to) {const char *a=filename(from),*b=filename(to);return a && b && game_card_rename(a,b);}
