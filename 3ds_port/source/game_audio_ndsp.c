/* SDK ABI only. The game's enums and libctru enums never cross this file. */
#include <3ds.h>
#include <string.h>
#include "game_audio.h"
#include "game_xa.h"
#include "game_cpu_audit.h"
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
void stage11a_lifetime_audio(uint32_t out[LT_AUDIO_WORDS]);
#endif
#if defined(SH_STAGE11A)
#include "game_profile.h"
#include "stage11a_perf.h"
static uint32_t s11_worker_id;
static struct { uint32_t starves,dropped,rendered; } s11_health[2];
#endif

#define BLOCK_FRAMES 512u
#define BLOCKS 4u
#ifndef SH_STAGE11A_SPU_CORE
#define SH_STAGE11A_SPU_CORE (-2)
#endif
static LightLock core_lock;
static LightEvent wake;
static Thread worker;
static ndspWaveBuf buffers[BLOCKS];
static int16_t *pcm;
static uint32_t running, paused, started, rendered, nonzero, peak, starved, max_render_us;
static uint32_t ever_started,saved_dropped,pause_requests,resume_requests;
static int32_t init_result;
static aptHookCookie apt_cookie;
static uint32_t hook_installed;
static uint32_t audio_initialized;
int32_t game_audio_output_ready(void) { return started && pcm!=NULL; }
uint32_t game_audio_lifecycle_paused(void) {return (__atomic_load_n(&paused,__ATOMIC_ACQUIRE)&2u)!=0;}
#if defined(SH_STAGE11A_LIFETIME)
void stage11a_lifetime_audio(uint32_t out[LT_AUDIO_WORDS])
{
    out[0]=__atomic_load_n(&rendered,__ATOMIC_RELAXED);out[1]=__atomic_load_n(&starved,__ATOMIC_RELAXED);
    out[2]=started?ndspGetDroppedFrames():saved_dropped;out[3]=__atomic_load_n(&paused,__ATOMIC_ACQUIRE);
    out[4]=__atomic_load_n(&running,__ATOMIC_ACQUIRE);out[5]=started;out[6]=(uint32_t)init_result;
    out[7]=__atomic_load_n(&max_render_us,__ATOMIC_RELAXED);
    for(unsigned i=0;i<BLOCKS;i++){unsigned status=buffers[i].status;if(status<4)out[8+status]++;}
    out[12]=BLOCKS;out[13]=worker!=NULL;
}
#endif
#if defined(SH_STAGE11A)
void stage11a_audio_boundary(unsigned start)
{
    unsigned i=start?0:1;
    s11_health[i].starves=__atomic_load_n(&starved,__ATOMIC_RELAXED);
    s11_health[i].rendered=__atomic_load_n(&rendered,__ATOMIC_RELAXED);
    s11_health[i].dropped=started?ndspGetDroppedFrames():saved_dropped;
}
#endif
static void callback(void *unused) { (void)unused;game_cpu_audit_enter(GCPU_NDSP);LightEvent_Signal(&wake); }
void game_audio_lock(void) {
#if defined(SH_STAGE11A)
    uint64_t start=stage11a_perf_active() && game_prof_enabled?svcGetSystemTick():0;
#endif
    LightLock_Lock(&core_lock);
#if defined(SH_STAGE11A)
    if(start) {
        uint64_t elapsed=svcGetSystemTick()-start;
        uint32_t id=0;svcGetThreadId(&id,CUR_THREAD_HANDLE);
        stage11a_perf_add(id==__atomic_load_n(&s11_worker_id,__ATOMIC_ACQUIRE)?S11_SPU_LOCK:S11_MAIN_LOCK,elapsed);
    }
#endif
}
void game_audio_unlock(void) { LightLock_Unlock(&core_lock); }
static void audio_thread(void *unused)
{
    (void)unused;
    game_cpu_audit_enter(GCPU_SPU);
#if defined(SH_STAGE11A)
    uint32_t id=0;svcGetThreadId(&id,CUR_THREAD_HANDLE);
    __atomic_store_n(&s11_worker_id,id,__ATOMIC_RELEASE);
#endif
    unsigned next=0;
    while(__atomic_load_n(&running,__ATOMIC_ACQUIRE)) {
        if(!__atomic_load_n(&paused,__ATOMIC_ACQUIRE)) {
            unsigned queued=0;
            for(unsigned i=0;i<BLOCKS;i++)if(buffers[i].status==NDSP_WBUF_QUEUED || buffers[i].status==NDSP_WBUF_PLAYING)queued++;
            if(!queued && rendered)__atomic_fetch_add(&starved,1,__ATOMIC_RELAXED);
            for(unsigned i=0;i<BLOCKS;i++) {
                ndspWaveBuf *b=&buffers[next];
                if(b->status!=NDSP_WBUF_FREE && b->status!=NDSP_WBUF_DONE)break;
                uint64_t audit=game_cpu_audit_begin(GCPU_SPU);
                uint64_t start=svcGetSystemTick();
                game_spu_render(b->data_pcm16,BLOCK_FRAMES);
#if defined(SH_STAGE11A)
                if(stage11a_perf_active() && game_prof_enabled)stage11a_perf_add(S11_RENDER,svcGetSystemTick()-start);
#endif
                uint32_t us=(uint32_t)((svcGetSystemTick()-start)*1000000/SYSCLOCK_ARM11);
                if(us>max_render_us)__atomic_store_n(&max_render_us,us,__ATOMIC_RELAXED);
                uint32_t nz=0,pk=0;
                for(unsigned j=0;j<BLOCK_FRAMES*2;j++) {
                    int32_t v=b->data_pcm16[j];uint32_t a=(uint32_t)(v<0?-v:v);
                    if(a)nz++;
                    if(a>pk)pk=a;
                }
                __atomic_fetch_add(&nonzero,nz,__ATOMIC_RELAXED);
                if(pk>peak)__atomic_store_n(&peak,pk,__ATOMIC_RELAXED);
#if defined(SH_STAGE11A)
                uint64_t flush=stage11a_perf_active() && game_prof_enabled?svcGetSystemTick():0;
#endif
                DSP_FlushDataCache(b->data_pcm16,BLOCK_FRAMES*4);
#if defined(SH_STAGE11A)
                if(flush)stage11a_perf_add(S11_FLUSH,svcGetSystemTick()-flush);
                uint64_t submit=flush?svcGetSystemTick():0;
#endif
                ndspChnWaveBufAdd(0,b);
#if defined(SH_STAGE11A)
                if(submit)stage11a_perf_add(S11_NDSP,svcGetSystemTick()-submit);
                if(submit) {
                unsigned depth=0;
                for(unsigned q=0;q<BLOCKS;q++)if(buffers[q].status==NDSP_WBUF_QUEUED || buffers[q].status==NDSP_WBUF_PLAYING)depth++;
                stage11a_perf_queue(depth);
                }
#endif
                game_spu_xa_submitted(BLOCK_FRAMES,nz);
                __atomic_fetch_add(&rendered,BLOCK_FRAMES,__ATOMIC_RELAXED);
                next=(next+1)%BLOCKS;
                game_cpu_audit_end(GCPU_SPU_BLOCK,audit);
#if defined(SH_STAGE11A)
                if(stage11a_perf_active() && game_prof_enabled)stage11a_perf_add(S11_BLOCK,svcGetSystemTick()-start);
#endif
            }
        }
        uint64_t wait=game_cpu_audit_begin(GCPU_SPU);
        LightEvent_WaitTimeout(&wake,2000000);
        game_cpu_audit_end(GCPU_SPU_WAIT,wait);
    }
}
static void set_pause_bit(uint32_t bit,uint32_t on)
{
    if(on)__atomic_fetch_or(&paused,bit,__ATOMIC_RELEASE);
    else __atomic_fetch_and(&paused,~bit,__ATOMIC_RELEASE);
    if(started)ndspChnSetPaused(0,__atomic_load_n(&paused,__ATOMIC_ACQUIRE)!=0);
    game_xa_pause(__atomic_load_n(&paused,__ATOMIC_ACQUIRE)!=0);
    LightEvent_Signal(&wake);
}
void game_audio_pause(uint32_t on)
{
    if(on)pause_requests++;else resume_requests++;
    set_pause_bit(1,on);
}
static void apt_callback(APT_HookType type,void *unused)
{
    (void)unused;
    /* APT hooks must never wait on the NDSP or XA LightLocks: the lock owner
     * can be suspended during the HOME handoff. Stop software workers using
     * only an atomic flag; APT/libctru controls DSP during suspension. */
    if(type==APTHOOK_ONSUSPEND || type==APTHOOK_ONSLEEP)
        __atomic_fetch_or(&paused,2,__ATOMIC_RELEASE);
    if(type==APTHOOK_ONRESTORE || type==APTHOOK_ONWAKEUP)
        __atomic_fetch_and(&paused,~2u,__ATOMIC_RELEASE);
}
int32_t game_audio_init(void)
{
    LightLock_Init(&core_lock);LightEvent_Init(&wake,RESET_ONESHOT);
    game_spu_init();
    int32_t xa_result=game_xa_thread_init();audio_initialized=1;
    if(xa_result){init_result=-3;game_xa_disable_output();return init_result;}
    init_result=ndspInit();
    if(R_FAILED(init_result)){game_xa_disable_output();return init_result;}
    pcm=linearAlloc(BLOCKS*BLOCK_FRAMES*4);
    if(!pcm){ndspExit();init_result=-1;game_xa_disable_output();return init_result;}
    memset(pcm,0,BLOCKS*BLOCK_FRAMES*4);
    memset(buffers,0,sizeof(buffers));
    ndspSetOutputMode(NDSP_OUTPUT_STEREO);ndspSetClippingMode(NDSP_CLIP_NORMAL);
    ndspChnReset(0);ndspChnSetInterp(0,NDSP_INTERP_POLYPHASE);
    ndspChnSetRate(0,44100.0f);ndspChnSetFormat(0,NDSP_FORMAT_STEREO_PCM16);
    float mix[12]={1.0f,1.0f};ndspChnSetMix(0,mix);
    for(unsigned i=0;i<BLOCKS;i++){buffers[i].data_pcm16=pcm+i*BLOCK_FRAMES*2;buffers[i].nsamples=BLOCK_FRAMES;}
    started=running=1;ndspSetCallback(callback,NULL);
    worker=threadCreate(audio_thread,NULL,32*1024,0x18,SH_STAGE11A_SPU_CORE,false);
    if(!worker){game_audio_shutdown();init_result=-2;game_xa_disable_output();return init_result;}
    ever_started=1;
    aptHook(&apt_cookie,apt_callback,NULL);hook_installed=1;
    return 0;
}
void game_audio_shutdown(void)
{
    if(hook_installed){aptUnhook(&apt_cookie);hook_installed=0;}
    __atomic_store_n(&running,0,__ATOMIC_RELEASE);LightEvent_Signal(&wake);
    if(worker){threadJoin(worker,UINT64_MAX);threadFree(worker);worker=NULL;}
    game_xa_thread_shutdown();
    if(started){saved_dropped=ndspGetDroppedFrames();ndspSetCallback(NULL,NULL);ndspChnWaveBufClear(0);ndspChnReset(0);ndspExit();started=0;}
    if(pcm){linearFree(pcm);pcm=NULL;}
}
void game_audio_loader_report(FILE *out);
#if defined(SH_STAGE11A)
void stage11a_audio_report(FILE *out)
{
    fprintf(out,"stage11a_audio_window_schema=rendered_frames,queue_starves,ndsp_dropped_frames\n"
        "stage11a_spu_requested_core=%d\nstage11a_audio_window=%lu,%lu,%lu\n",
        SH_STAGE11A_SPU_CORE,
        (unsigned long)(s11_health[1].rendered-s11_health[0].rendered),
        (unsigned long)(s11_health[1].starves-s11_health[0].starves),
        (unsigned long)(s11_health[1].dropped-s11_health[0].dropped));
}
#endif
void game_audio_driver_report(FILE *out);
void game_audio_report(FILE *out)
{
    if(!audio_initialized){fprintf(out,"audio_initialized=0\n");return;}
    fprintf(out,"audio_initialized=1\n");
    fprintf(out,"audio_backend=SPU_EXACT_NDSP\naudio_ndsp_result=%ld\naudio_started=%lu\naudio_rate=44100\naudio_linear_bytes=%u\naudio_buffer_frames=%u\naudio_buffers=%u\naudio_rendered_frames=%lu\naudio_nonzero_samples=%lu\naudio_peak=%lu\naudio_queue_starves=%lu\naudio_max_render_us=%lu\naudio_ndsp_dropped=%lu\naudio_paused=%lu\naudio_music=ORIGINAL_KDT_SEQUENCER\n",
        (long)init_result,(unsigned long)started,BLOCKS*BLOCK_FRAMES*4,BLOCK_FRAMES,BLOCKS,
        (unsigned long)__atomic_load_n(&rendered,__ATOMIC_RELAXED),
        (unsigned long)__atomic_load_n(&nonzero,__ATOMIC_RELAXED),
        (unsigned long)__atomic_load_n(&peak,__ATOMIC_RELAXED),
        (unsigned long)__atomic_load_n(&starved,__ATOMIC_RELAXED),
        (unsigned long)__atomic_load_n(&max_render_us,__ATOMIC_RELAXED),
        (unsigned long)(started?ndspGetDroppedFrames():saved_dropped),(unsigned long)paused);
    fprintf(out,"audio_ever_started=%lu\naudio_pause_requests=%lu\naudio_resume_requests=%lu\n",
        (unsigned long)ever_started,(unsigned long)pause_requests,(unsigned long)resume_requests);
    game_audio_loader_report(out);
    game_audio_driver_report(out);
    game_xa_report(out);
    game_xa_thread_report(out);
    game_spu_audio_report(out);
}
