/* Run the production movie adapter, demux and decoder behind a fake SDK.
 * This tests ownership/control, not real DSP, LCD or SD-card performance. */
#include <3ds.h>
#include "game_fmv.h"
#include "fmv_stream.h"
#include <pthread.h>
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static pthread_t main_id;
typedef struct {pthread_t thread;void (*fn)(void *);void *user;} Worker;
static atomic_ullong tick;
static uint32_t scenario,polls,swaps,joined,cleared,freed,ended,linear_count,hooked,ndsp_paused=1;
static uint32_t started_tick,sleeping,resumed,seq,position,queue_head,queue_count,fallback;
static uint64_t audio_tick,remainder;
static ndspWaveBuf *queue[32];
static void (*hook)(APT_HookType,void *);static void *hook_user;
static uint8_t framebuffer[400*240*3];
static void update(void)
{
    uint64_t now=atomic_load(&tick),dt=now-audio_tick;audio_tick=now;
    if(ndsp_paused || !queue_count)return;
    uint64_t accum=remainder+dt*FMV_RATE;uint32_t frames=accum/SYSCLOCK_ARM11;remainder=accum%SYSCLOCK_ARM11;
    while(queue_count) {
        ndspWaveBuf *b=queue[queue_head];b->status=NDSP_WBUF_PLAYING;seq=b->sequence_id;
        uint32_t n=b->nsamples-position;if(n>frames)n=frames;
        position+=n;frames-=n;
        if(position==b->nsamples) {b->status=NDSP_WBUF_DONE;position=0;queue_head=(queue_head+1)%32;--queue_count;}
        else break;
    }
}
uint64_t svcGetSystemTick(void)
{
    if(scenario==12 && !pthread_equal(pthread_self(),main_id))usleep(25000);
    return atomic_load(&tick);
}
int svcGetProcessorID(void){return fallback?0:3;}
void svcSleepThread(int64_t ns)
{
    if(pthread_equal(pthread_self(),main_id))atomic_fetch_add(&tick,(uint64_t)ns*SYSCLOCK_ARM11/1000000000ull);
    usleep(100);
}
static void *start_worker(void *p){Worker *w=p;w->fn(w->user);return NULL;}
Thread threadCreate(void (*fn)(void *),void *user,unsigned stack,int pri,int core,bool detach)
{
    (void)stack;(void)pri;(void)detach;
    if(scenario==4)return NULL;
    if(scenario==5 && core==3){fallback=1;return NULL;}
    assert(core==3 || core==-2);Worker *w=malloc(sizeof(*w));assert(w);w->fn=fn;w->user=user;
    assert(!pthread_create(&w->thread,NULL,start_worker,w));return w;
}
void threadJoin(Thread p,uint64_t timeout){(void)timeout;Worker *w=p;assert(!pthread_join(w->thread,NULL));joined++;}
void threadFree(Thread p){free(p);}
void *linearAlloc(unsigned n){linear_count++;return malloc(n);}
void linearFree(void *p){assert(cleared && (!scenario || joined || scenario==4));assert(linear_count);--linear_count;freed++;free(p);}
void game_fmv_platform_begin(void){}
void game_fmv_platform_end(uint64_t began){(void)began;assert(cleared);ended++;}
void game3ds_recoverable(const char *operation,int32_t detail){(void)operation;(void)detail;}
int32_t game_audio_output_ready(void){return scenario!=9;}
void game_xa_stop(void){}
void aptHook(aptHookCookie *c,void (*fn)(APT_HookType,void *),void *user){c->active=1;hook=fn;hook_user=user;hooked++;}
void aptUnhook(aptHookCookie *c){assert(c->active);c->active=0;hooked--;hook=NULL;}
bool aptMainLoop(void)
{
    ++polls;update();
    if(scenario==2 && started_tick && !sleeping && !resumed && polls>200) {
        sleeping=1;hook(APTHOOK_ONSLEEP,hook_user);
        atomic_fetch_add(&tick,30ull*SYSCLOCK_ARM11);update();hook(APTHOOK_ONWAKEUP,hook_user);
        sleeping=0;resumed=1;
    }
    if(scenario==3 && polls>200)return false;
    assert(polls<200000);return true;
}
void hidScanInput(void){}
uint32_t hidKeysHeld(void)
{
    if(scenario==1 && (polls<20 || polls>200))return KEY_START;
    return 0;
}
uint8_t *gfxGetFramebuffer(int screen,int eye,u16 *w,u16 *h){assert(!screen && !eye);*w=240;*h=400;return framebuffer;}
void gfxFlushBuffers(void){}
void gfxSwapBuffers(void){++swaps;}
void gspWaitForVBlank(void){atomic_fetch_add(&tick,SYSCLOCK_ARM11/(scenario==11?5:60));usleep(100);}
void ndspChnSetPaused(int ch,bool on){assert(ch==1);update();ndsp_paused=on;audio_tick=atomic_load(&tick);if(!on)started_tick=1;}
void ndspChnReset(int ch){assert(ch==1);queue_head=queue_count=seq=position=0;remainder=0;ndsp_paused=1;}
void ndspChnSetInterp(int ch,int interp){assert(ch==1);(void)interp;}
void ndspChnSetRate(int ch,float rate){assert(ch==1 && rate==37800);}
void ndspChnSetFormat(int ch,int format){assert(ch==1);(void)format;}
void ndspChnSetMix(int ch,float *mix){assert(ch==1 && mix[0]==80.0f/127 && mix[1]==mix[0]);}
void ndspChnWaveBufAdd(int ch,ndspWaveBuf *buf)
{
    assert(ch==1 && queue_count<32);update();static uint16_t next_seq;
    buf->sequence_id=++next_seq;buf->status=NDSP_WBUF_QUEUED;
    queue[(queue_head+queue_count)%32]=buf;++queue_count;
}
void ndspChnWaveBufClear(int ch)
{
    assert(ch==1);assert(joined || scenario==4);queue_count=0;cleared++;
}
uint16_t ndspChnGetWaveBufSeq(int ch){assert(ch==1);update();return seq;}
uint32_t ndspChnGetSamplePos(int ch){assert(ch==1);update();return position;}
void DSP_FlushDataCache(void *p,unsigned n){assert(p && n<=FMV_AUDIO_FRAMES*4);}
int __real_PsxDisc_ReadRawSector(PsxDisc *,uint32_t,void *);
int __wrap_PsxDisc_ReadRawSector(PsxDisc *d,uint32_t lba,void *p)
{
    if(scenario==6 && lba>=0x2b72f && lba<0x2b72f+1190)return PD_IO;
    int r=__real_PsxDisc_ReadRawSector(d,lba,p);
    if(scenario==7 && lba==0x2b72f)((uint8_t *)p)[28]=2;
    if(scenario==8 && lba==0x2b72f)((uint8_t *)p)[60]=0;
    return r;
}
#include "../source/game_fmv.c"
int main(int argc,char **argv)
{
    assert(argc==2);scenario=strtoul(argv[1],NULL,0);main_id=pthread_self();
    /* Synthetic colors verify rotation, BGR and all four presentation edges. */
    uint8_t *pattern=calloc(1,FMV_RGB_BYTES);assert(pattern);
    const unsigned xy[4][2]={{0,0},{319,0},{0,207},{319,207}};
    for(unsigned i=0;i<4;i++) {
        unsigned offset=(xy[i][1]*320+xy[i][0])*3;pattern[offset]=10+i;pattern[offset+1]=20+i;pattern[offset+2]=30+i;
    }
    present(pattern);free(pattern);
    for(unsigned i=0;i<4;i++) {
        unsigned offset=((xy[i][0]+40)*240+239-(xy[i][1]+16))*3;
        assert(framebuffer[offset]==30+i && framebuffer[offset+1]==20+i && framebuffer[offset+2]==10+i);
    }
    assert(framebuffer[0]==0 && framebuffer[sizeof(framebuffer)-1]==0);swaps=0;atomic_store(&tick,0);
    int r=game_fmv_play(scenario==10?0:2056,0);
    int expected=scenario==1?GAME_FMV_SKIPPED:scenario==3?GAME_FMV_EXIT:
        (scenario==4 || (scenario>=6 && scenario<=10))?GAME_FMV_ERROR:GAME_FMV_DONE;
    assert(r==expected);assert(!linear_count && !hooked);
    if(scenario==0 || scenario==2 || scenario==5)assert(swaps>0 && joined && ended);
    if(scenario==2)assert(resumed);
    printf("scenario=%u result=%d frames=%u joined=%u cleared=%u freed=%u end=%u fallback=%u presentation=PASS PASS\n",scenario,r,swaps,joined,cleared,freed,ended,fallback);
    return 0;
}
