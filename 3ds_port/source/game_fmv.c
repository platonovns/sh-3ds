/* SPDX-License-Identifier: GPL-3.0-or-later */
/* SDK-only movie adapter. Worker owns disc/codec; main owns NDSP channel 1
 * and scanout. Channel 0/Core 2/SPU/callback ownership remain with game audio. */
#include <3ds.h>
#include <stdlib.h>
#include <string.h>
#include "game_fmv.h"
#include "game3ds.h"
#include "game_audio.h"
#include "game_xa.h"
#include "fmv_stream.h"
#include "fmv_mdec.h"
#define VIDEO_SLOTS 4u
#define AUDIO_SLOTS 8u
#define MOVIE_CHANNEL 1
#define MOVIE_STDIO_BYTES (16u*2352u)
enum { SLOT_FREE,SLOT_READY,SLOT_QUEUED };
typedef struct {uint32_t state,number;uint8_t rgb[FMV_RGB_BYTES];} VideoSlot;
typedef struct {uint32_t state,pts,frames;ndspWaveBuf wave;} AudioSlot;
typedef struct {
    uint32_t abort,suspended,done,error,clock,started,resumed;
    uint32_t vw,vr,aw,ar;
    uint32_t decoded,dropped,shown,underflows,worker_core_mask;
    uint64_t decode_ticks,decode_max;
    PsxDisc disc;
    FmvStream stream;
    VideoSlot video[VIDEO_SLOTS];
    AudioSlot audio[AUDIO_SLOTS];
    uint8_t disc_stdio[MOVIE_STDIO_BYTES];
    int16_t *pcm;
} Movie;
/* Offline ABI audit can read this from the ARM object without running a game. */
const uint32_t game_fmv_memory_budget[]={sizeof(Movie),AUDIO_SLOTS*FMV_AUDIO_FRAMES*4u,
    32u*2352u,32u*1024u,VIDEO_SLOTS,FMV_RGB_BYTES};
static uint32_t load(const uint32_t *p){return __atomic_load_n(p,__ATOMIC_ACQUIRE);}
static void put(uint32_t *p,uint32_t v){__atomic_store_n(p,v,__ATOMIC_RELEASE);}
static int yield(Movie *m)
{
    if(load(&m->abort))return 0;
    svcSleepThread(1000000);return !load(&m->abort);
}
static int audio_sink(void *user,const int16_t *pcm,uint32_t frames,uint32_t pts)
{
    Movie *m=user;AudioSlot *a=&m->audio[m->aw];
    while(load(&a->state)!=SLOT_FREE || load(&m->suspended))if(!yield(m))return 0;
    if(load(&m->abort))return 0;
    memcpy(m->pcm+m->aw*FMV_AUDIO_FRAMES*2,pcm,frames*4u);
    a->pts=pts;a->frames=frames;put(&a->state,SLOT_READY);
    m->aw=(m->aw+1)%AUDIO_SLOTS;return 1;
}
static void decode_worker(void *user)
{
    Movie *m=user;m->worker_core_mask=1u<<svcGetProcessorID();
    mdec_ctx_t ctx;mdec_init(&ctx,FMV_WIDTH,FMV_HEIGHT);
    while(!load(&m->abort)) {
        VideoSlot *v=&m->video[m->vw];
        while(load(&v->state)!=SLOT_FREE || load(&m->suspended))if(!yield(m))goto done;
        uint32_t no,bytes;int r=fmv_next_frame(&m->stream,audio_sink,m,&no,&bytes);
        if(r==0) {
            r=fmv_finish_audio(&m->stream,audio_sink,m);
            if(r<0 && !load(&m->abort))put(&m->error,(uint32_t)-r);
            break;
        }
        if(r<0){if(!load(&m->abort))put(&m->error,(uint32_t)-r);break;}
        /* Decode every frame at normal speed. If late by a complete frame,
         * keep demux/audio moving and omit obsolete intra frames entirely. */
        if(fmv_frame_sample(no)+FMV_RATE/FMV_FPS<load(&m->clock)) {__atomic_fetch_add(&m->dropped,1,__ATOMIC_RELAXED);continue;}
        uint64_t t=svcGetSystemTick();
        r=mdec_decode_frame(&ctx,m->stream.bits,bytes,v->rgb);
        t=svcGetSystemTick()-t;m->decode_ticks+=t;if(t>m->decode_max)m->decode_max=t;
        if(r!=(int)(FMV_WIDTH*FMV_HEIGHT/256u)){put(&m->error,100);break;}
        ++m->decoded;v->number=no;put(&v->state,SLOT_READY);m->vw=(m->vw+1)%VIDEO_SLOTS;
    }
done:
    put(&m->done,1);
}
static void apt_hook(APT_HookType type,void *user)
{
    Movie *m=user;
    if(type==APTHOOK_ONSUSPEND || type==APTHOOK_ONSLEEP) {
        put(&m->suspended,1);
    }
    if(type==APTHOOK_ONRESTORE || type==APTHOOK_ONWAKEUP) {
        put(&m->suspended,0);put(&m->resumed,1);
    }
}
static void present(const uint8_t *rgb)
{
    u16 width,height;uint8_t *fb=gfxGetFramebuffer(GFX_TOP,GFX_LEFT,&width,&height);
    /* libctru's RGB8 framebuffer is rotated BGR. One-to-one 320x208 pixels,
     * centered at (40,16) in 400x240, preserves the source's movie window. */
    memset(fb,0,(size_t)width*height*3u);
    /* Discard spatial detail: eight edge-region averages per side. Detect
     * letterbox rows before sampling so black bars never tint the glow. */
    unsigned black[FMV_HEIGHT],top=FMV_HEIGHT,bottom=0;
    for(unsigned y=0;y<FMV_HEIGHT;y++) {
        black[y]=1;
        for(unsigned x=0;x<FMV_WIDTH;x+=19)for(unsigned c=0;c<3;c++)
            if(rgb[(y*FMV_WIDTH+x)*3u+c]>3)black[y]=0;
        if(!black[y]) {if(top==FMV_HEIGHT)top=y;bottom=y+1;}
    }
    unsigned colors[2][8][3]={{{0}}};
    if(bottom>top)for(unsigned band=0;band<8;band++) {
        unsigned y0=top+(bottom-top)*band/8,y1=top+(bottom-top)*(band+1)/8;
        if(y1<=y0)y1=y0+1;
        unsigned count=0;
        for(unsigned y=y0;y<y1 && y<bottom;y++)if(!black[y]) {
            for(unsigned x=0;x<40;x++)for(unsigned c=0;c<3;c++) {
                colors[0][band][c]+=rgb[(y*FMV_WIDTH+x)*3u+c];
                colors[1][band][c]+=rgb[(y*FMV_WIDTH+FMV_WIDTH-40u+x)*3u+c];
            }
            count+=40;
        }
        if(count)for(unsigned side=0;side<2;side++)for(unsigned c=0;c<3;c++)
            colors[side][band][c]=colors[side][band][c]*65u/(count*100u);
    }
    for(unsigned y=0;y<FMV_HEIGHT;y++) {
        unsigned color[2][3]={{0}};
        if(!black[y] && bottom>top) {
            /* Sample centers lie halfway through each of eight bands. */
            int pos=(int)((y-top)*256u/(bottom-top))-16;
            unsigned a=pos<0?0:(unsigned)pos/32,frac=pos<0?0:(unsigned)pos%32;
            if(a>7){a=7;frac=0;}
            unsigned b=a<7?a+1:a;
            for(unsigned side=0;side<2;side++)for(unsigned c=0;c<3;c++)
                color[side][c]=(colors[side][a][c]*(32-frac)+colors[side][b][c]*frac)/32;
        }
        for(unsigned side=0;side<2;side++)for(unsigned x=0;x<40;x++) {
            uint8_t *d=fb+(((side?360u:0u)+x)*240u+239u-(y+16u))*3u;
            d[0]=(uint8_t)color[side][2];d[1]=(uint8_t)color[side][1];d[2]=(uint8_t)color[side][0];
        }
        for(unsigned x=0;x<FMV_WIDTH;x++) {
            const uint8_t *p=rgb+(y*FMV_WIDTH+x)*3u;
            uint8_t *d=fb+((x+40u)*240u+239u-(y+16u))*3u;
            d[0]=p[2];d[1]=p[1];d[2]=p[0];
            if(!black[y] && (x<2 || x>=FMV_WIDTH-2)) {
                unsigned blend=(x==0 || x==FMV_WIDTH-1)?2u:1u;
                unsigned side=x<2?0:1;
                for(unsigned c=0;c<3;c++)d[2-c]=(uint8_t)((p[c]*(4-blend)+color[side][c]*blend)/4);
            }
        }
    }
    gfxFlushBuffers();gfxSwapBuffers();gspWaitForVBlank();
}
static uint32_t feed_audio(Movie *m)
{
    /* Return slots only after DSP ownership ends; sequence IDs identify the
     * playback position even when several buffers finish between polls. */
    uint32_t queued=0;
    for(unsigned i=0;i<AUDIO_SLOTS;i++) {
        AudioSlot *a=&m->audio[i];
        if(load(&a->state)==SLOT_QUEUED && a->wave.status==NDSP_WBUF_DONE) {
            uint32_t end=a->pts+a->frames;
            if(end>load(&m->clock))put(&m->clock,end);
            put(&a->state,SLOT_FREE);
        }
    }
    /* Queue in stream order, rather than physical ring-array order. */
    for(unsigned i=0;i<AUDIO_SLOTS;i++) {
        AudioSlot *a=&m->audio[m->ar];if(load(&a->state)!=SLOT_READY)break;
        unsigned slot=m->ar;memset(&a->wave,0,sizeof(a->wave));
        a->wave.data_pcm16=m->pcm+slot*FMV_AUDIO_FRAMES*2u;a->wave.nsamples=a->frames;
        DSP_FlushDataCache(a->wave.data_pcm16,a->frames*4u);
        ndspChnWaveBufAdd(MOVIE_CHANNEL,&a->wave);put(&a->state,SLOT_QUEUED);
        m->ar=(m->ar+1)%AUDIO_SLOTS;
    }
    for(unsigned i=0;i<AUDIO_SLOTS;i++)if(load(&m->audio[i].state)==SLOT_QUEUED)++queued;
    return queued;
}
static uint32_t audio_clock(Movie *m)
{
    /* Sample position is relative to the current wave buffer. Read the
     * sequence twice so a DSP boundary cannot pair a new offset with old PTS. */
    for(unsigned retry=0;retry<3;retry++) {
        uint16_t seq=ndspChnGetWaveBufSeq(MOVIE_CHANNEL);
        uint32_t pos=ndspChnGetSamplePos(MOVIE_CHANNEL);
        if(seq!=ndspChnGetWaveBufSeq(MOVIE_CHANNEL))continue;
        for(unsigned i=0;i<AUDIO_SLOTS;i++) {
            AudioSlot *a=&m->audio[i];
            if(load(&a->state)==SLOT_QUEUED && a->wave.sequence_id==seq) {
                if(pos>a->frames)pos=a->frames;
                uint32_t t=a->pts+pos;if(t>load(&m->clock))put(&m->clock,t);
            }
        }
        break;
    }
    return load(&m->clock);
}
static void report(Movie *m,int result)
{
    FILE *f=fopen("sdmc:/3ds/silenthill/fmv_last.txt","w");if(!f)return;
    fprintf(f,"fmv_schema=1\nfile=%lu\nresult=%d\nlimit=%lu\ndecoded=%lu\nshown=%lu\ndropped=%lu\nerror=%lu\nclock_samples=%lu\nrate=37800\nunderflows=%lu\nworker_core_mask=%lu\ndecode_mean_us=%llu\ndecode_max_us=%llu\nheap_movie=%u\nlinear_pcm=%u\ndisc_cache_peak=%lu\n",
        (unsigned long)m->stream.entry.id,result,(unsigned long)m->stream.entry.frame_limit,
        (unsigned long)m->decoded,(unsigned long)m->shown,(unsigned long)m->dropped,
        (unsigned long)load(&m->error),(unsigned long)load(&m->clock),(unsigned long)m->underflows,
        (unsigned long)m->worker_core_mask,
        (unsigned long long)(m->decoded?m->decode_ticks*1000000/SYSCLOCK_ARM11/m->decoded:0),
        (unsigned long long)(m->decode_max*1000000/SYSCLOCK_ARM11),
        (unsigned)sizeof(*m),(unsigned)(AUDIO_SLOTS*FMV_AUDIO_FRAMES*4u),(unsigned long)m->disc.cache_peak_bytes);
    fclose(f);
}
int32_t game_fmv_play(uint32_t id,uint32_t limit)
{
    if(!game_audio_output_ready()){game3ds_recoverable("FMV audio",0);return GAME_FMV_ERROR;}
    Movie *m=calloc(1,sizeof(*m));if(!m){game3ds_recoverable("FMV allocation",0);return GAME_FMV_ERROR;}
    m->stream.entry.id=id;
    Thread worker=NULL;aptHookCookie cookie;int hooked=0,began=0,channel=0,result=GAME_FMV_ERROR;
    uint64_t begin_tick=0;ShDisc sh;FmvEntry entry;
    int r=PsxDisc_OpenBuffered(&m->disc,"sdmc:/3ds/silenthill/sh1.bin","sdmc:/3ds/silenthill/sh1.cue",m->disc_stdio,sizeof(m->disc_stdio));
    if(r)goto cleanup;
    r=ShDisc_Init(&sh,&m->disc);if(r)goto cleanup;
    r=fmv_entry(&sh,id,limit,&entry);if(r)goto cleanup;
    fmv_stream_init(&m->stream,&m->disc,&entry);
    m->pcm=linearAlloc(AUDIO_SLOTS*FMV_AUDIO_FRAMES*4u);if(!m->pcm){put(&m->error,102);goto cleanup;}
    game_fmv_platform_begin();begin_tick=svcGetSystemTick();began=1;
    game_xa_stop();
    ndspChnReset(MOVIE_CHANNEL);channel=1;ndspChnSetPaused(MOVIE_CHANNEL,true);
    ndspChnSetInterp(MOVIE_CHANNEL,NDSP_INTERP_POLYPHASE);
    ndspChnSetRate(MOVIE_CHANNEL,FMV_RATE);ndspChnSetFormat(MOVIE_CHANNEL,NDSP_FORMAT_STEREO_PCM16);
    float mix[12]={80.0f/127.0f,80.0f/127.0f};ndspChnSetMix(MOVIE_CHANNEL,mix);
    aptHook(&cookie,apt_hook,m);hooked=1;
    worker=threadCreate(decode_worker,m,32*1024,0x30,3,false);
    if(!worker)worker=threadCreate(decode_worker,m,32*1024,0x30,-2,false);
    if(!worker){put(&m->error,103);goto cleanup;}
    uint32_t armed=0,last_clock=0,was_empty=0;
    uint64_t progress=svcGetSystemTick();
    for(;;) {
        if(!aptMainLoop()){result=GAME_FMV_EXIT;break;}
        game3ds_lower_backlight_tick();
        hidScanInput();uint32_t held=hidKeysHeld();
        if(!(held&KEY_START))armed=1;
        else if(armed){result=GAME_FMV_SKIPPED;break;}
        if(load(&m->suspended)){progress=svcGetSystemTick();svcSleepThread(1000000);continue;}
        if(load(&m->error))break;
        uint32_t queued=feed_audio(m);
        VideoSlot *v=&m->video[m->vr];
        if(!load(&m->started) && (queued>=3 || load(&m->done)) && load(&v->state)==SLOT_READY) {
            present(v->rgb);++m->shown;put(&v->state,SLOT_FREE);m->vr=(m->vr+1)%VIDEO_SLOTS;
            put(&m->started,1);ndspChnSetPaused(MOVIE_CHANNEL,false);progress=svcGetSystemTick();
        }
        if(load(&m->started)) {
            uint32_t now=audio_clock(m);
            if(now!=last_clock){last_clock=now;progress=svcGetSystemTick();}
            if(!queued && now<fmv_duration_samples(&entry) && !was_empty)++m->underflows;
            was_empty=!queued;
            v=&m->video[m->vr];
            if(load(&v->state)==SLOT_READY && now>=fmv_frame_sample(v->number)) {
                if(now<fmv_frame_sample(v->number)+FMV_RATE/FMV_FPS) {present(v->rgb);++m->shown;}
                else __atomic_fetch_add(&m->dropped,1,__ATOMIC_RELAXED);
                put(&v->state,SLOT_FREE);m->vr=(m->vr+1)%VIDEO_SLOTS;
            }
            if(now>=fmv_duration_samples(&entry)){result=GAME_FMV_DONE;break;}
        }
        if(__atomic_exchange_n(&m->resumed,0,__ATOMIC_ACQ_REL))progress=svcGetSystemTick();
        if(svcGetSystemTick()-progress>10ull*SYSCLOCK_ARM11){put(&m->error,101);break;}
        svcSleepThread(1000000);
    }
cleanup:
    put(&m->abort,1);
    if(worker){threadJoin(worker,UINT64_MAX);threadFree(worker);}
    if(hooked)aptUnhook(&cookie);
    if(channel){ndspChnSetPaused(MOVIE_CHANNEL,true);ndspChnWaveBufClear(MOVIE_CHANNEL);ndspChnReset(MOVIE_CHANNEL);}
    if(began) {
        for(unsigned i=0;i<30 && result==GAME_FMV_SKIPPED;i++) {
            if(!aptMainLoop()){result=GAME_FMV_EXIT;break;}
            hidScanInput();if(!(hidKeysHeld()&KEY_START))break;gspWaitForVBlank();
        }
        game_fmv_platform_end(begin_tick);
    }
    if(r && !load(&m->error))put(&m->error,(uint32_t)-r);
    if(result==GAME_FMV_ERROR)game3ds_recoverable("FMV",(int32_t)load(&m->error));
    report(m,result);if(m->pcm)linearFree(m->pcm);PsxDisc_Close(&m->disc);free(m);return result;
}
