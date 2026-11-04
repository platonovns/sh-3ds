/* Optional bounded profiling. Coarse phases always time when enabled; individual
 * GTE operations time only every Nth game frame to bound measurement overhead. */
#define GAME_PROFILE_IMPLEMENTATION 1
#include "game_profile.h"
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
#endif
#include "game3ds.h"
#if defined(SH_STAGE11A)
#include "stage11a_perf.h"
#endif
#include <string.h>
#include <inttypes.h>
#define TICKS_PER_MS 268123.480
#define WINDOW_FRAMES 120u
#define SLOW_SLOTS 8u
int game_prof_enabled,game_prof_gte_sample;
typedef struct { uint64_t ticks[GP_COUNT], count[GC_COUNT]; } Work;
typedef struct { unsigned frames,gte_frames; uint64_t total,work,worst;
    Work sum; uint64_t peak[GP_COUNT]; } Window;
typedef struct { unsigned state,player,file,map; int32_t x,z,yaw; } Context;
typedef struct { uint64_t wall; Work work; Context context;unsigned sampled; } Slow;
static Work current;
static uint32_t audio_ticks[GP_COUNT-GP_AUDIO_LOCK];
static Window window,recent;
static Context context;
static Slow slow[SLOW_SLOTS];
static Slow io_slow[4];
static uint64_t started;
static unsigned stride=16,frame_id,have_start;
typedef struct { unsigned used,map,room,cutscene,enemies,frames;Work sum;uint64_t wall,work; } Scene;
static Scene scenes[16];
static unsigned scene_map,scene_room,scene_cutscene,scene_enemies;
#if defined(SH_CPU_AUDIT_RECORDER)
static Window sample;
static unsigned sample_active;
void game_prof_sample_start(void) {memset(&sample,0,sizeof(sample));sample_active=1;}
void game_prof_sample_stop(void) {sample_active=0;}
/* Completed pad-to-pad frame scopes only; the boundary frame is not split.
 * Worker deltas are the existing frame-drained independent elapsed counters. */
static void sample_frame(uint64_t wall,uint64_t work)
{
    if(!sample_active)return;
#if defined(SH_STAGE11A)
    stage11a_perf_add(S11_WALL,wall);stage11a_perf_add(S11_WORK,work);
#endif
    sample.frames++;sample.gte_frames+=game_prof_gte_sample!=0;
    sample.total+=wall;sample.work+=work;
    if(wall>sample.worst)sample.worst=wall;
    for(unsigned i=0;i<GP_COUNT;i++) {
        sample.sum.ticks[i]+=current.ticks[i];
        if(current.ticks[i]>sample.peak[i])sample.peak[i]=current.ticks[i];
    }
    for(unsigned i=0;i<GC_COUNT;i++)sample.sum.count[i]+=current.count[i];
}
#endif
static uint64_t slow_rank(const Slow *s)
{
    uint64_t diagnostic=s->work.ticks[GP_VBLANK]+s->work.ticks[GP_REPORT]+s->work.ticks[GP_PAUSE];
    return s->wall>diagnostic?s->wall-diagnostic:0;
}
uint64_t game_prof_clock(void) { return game3ds_ticks(); }
void game_prof_enable(unsigned n) { stride=n?n:16; __atomic_store_n(&game_prof_enabled,1,__ATOMIC_RELEASE); }
void game_prof_add(unsigned category,uint64_t elapsed)
{ if(category<GP_COUNT) current.ticks[category]+=elapsed; }
void game_prof_audio_add(unsigned category,uint64_t elapsed)
{
    if(__atomic_load_n(&game_prof_enabled,__ATOMIC_ACQUIRE) && category>=GP_AUDIO_LOCK && category<GP_COUNT)
        __atomic_fetch_add(&audio_ticks[category-GP_AUDIO_LOCK],(uint32_t)elapsed,__ATOMIC_RELAXED);
}
void game_prof_scene(unsigned map,unsigned room,unsigned cutscene,unsigned enemies)
{scene_map=map;scene_room=room;scene_cutscene=cutscene;scene_enemies=enemies;}
void game_prof_count(unsigned counter,uint64_t value)
{ if(game_prof_enabled && counter<GC_COUNT) current.count[counter]+=value; }
void game_prof_context(unsigned state,unsigned player,int32_t x,int32_t z,int32_t yaw,
                       unsigned file,unsigned map)
{ context=(Context){state,player,file,map,x,z,yaw}; }
void game_prof_frame(void)
{
    if(!game_prof_enabled)return;
    uint64_t now=game_prof_clock();
    for(unsigned i=GP_AUDIO_LOCK;i<GP_COUNT;i++)
        current.ticks[i]+=__atomic_exchange_n(&audio_ticks[i-GP_AUDIO_LOCK],0,__ATOMIC_RELAXED);
    if(have_start) {
        uint64_t wall=now-started;
        uint64_t excluded=current.ticks[GP_VBLANK]+current.ticks[GP_REPORT]+current.ticks[GP_PAUSE];
        uint64_t work=wall>excluded?wall-excluded:0;
#if defined(SH_CPU_AUDIT_RECORDER)
        sample_frame(wall,work);
#endif
        window.frames++; window.gte_frames+=game_prof_gte_sample!=0;
        window.total+=wall;
        window.work+=work;
        if(context.state==11) {
            unsigned slot=0;
            for(;slot<16;slot++) {
                Scene *s=&scenes[slot];
                if(!s->used || (s->map==scene_map && s->room==scene_room &&
                    s->cutscene==scene_cutscene && s->enemies==scene_enemies))break;
            }
            if(slot<16) {
                Scene *s=&scenes[slot];s->used=1;s->map=scene_map;s->room=scene_room;
                s->cutscene=scene_cutscene;s->enemies=scene_enemies;s->frames++;
                s->wall+=wall;s->work+=work;
                for(unsigned i=0;i<GP_COUNT;i++)s->sum.ticks[i]+=current.ticks[i];
            }
        }
        if(wall>window.worst)window.worst=wall;
        for(unsigned i=0;i<GP_COUNT;i++) {
            window.sum.ticks[i]+=current.ticks[i];
            if(current.ticks[i]>window.peak[i])window.peak[i]=current.ticks[i];
        }
        for(unsigned i=0;i<GC_COUNT;i++)window.sum.count[i]+=current.count[i];
        if(context.state==11 && context.map>700 && context.player==0) {
            unsigned smallest=0;
            for(unsigned i=1;i<SLOW_SLOTS;i++)if(slow_rank(&slow[i])<slow_rank(&slow[smallest]))smallest=i;
            Slow candidate={wall,current,context,game_prof_gte_sample!=0};
            if(slow_rank(&candidate)>slow_rank(&slow[smallest]))slow[smallest]=candidate;
            if(current.count[GC_READS]) {
                unsigned least=0;
                for(unsigned i=1;i<4;i++)if(io_slow[i].work.ticks[GP_RESOURCE]<io_slow[least].work.ticks[GP_RESOURCE])least=i;
                if(current.ticks[GP_RESOURCE]>io_slow[least].work.ticks[GP_RESOURCE])
                    io_slow[least]=(Slow){wall,current,context,game_prof_gte_sample!=0};
            }
        }
        if(window.frames==WINDOW_FRAMES) {recent=window;memset(&window,0,sizeof(window));}
    }
    memset(&current,0,sizeof(current));
    have_start=1;started=now;
    game_prof_gte_sample=(frame_id++%stride)==0;
}
static const char *const categories[]={"update","gte_sampled","primitive","cache","decode",
        "upload_flush","submit","resource","io","sync","vblank","report",
        "map","npc","player","world","command","present","pause",
        "audio_lock","spu","xa_pcm","xa_worker","spu_voices_est","spu_reverb_est","spu_mix_est"};
static const char *const counters[]={"gte_ops","cache_probes","decodes","uploads","upload_bytes",
        "reads","read_bytes","raw_reads","raw_bytes","raw_seeks","primitives","batches","draws"};
#if defined(SH_STAGE11A_LIFETIME)
void game_prof_lifetime_toggle(unsigned enabled)
{
    __atomic_store_n(&game_prof_enabled,0,__ATOMIC_RELEASE);
    game_prof_gte_sample=0;have_start=0;memset(&current,0,sizeof(current));
    memset(&recent,0,sizeof(recent));memset(&window,0,sizeof(window));
    for(unsigned i=0;i<GP_COUNT-GP_AUDIO_LOCK;i++)__atomic_exchange_n(&audio_ticks[i],0,__ATOMIC_RELAXED);
    if(enabled)game_prof_enable(16);
}
void stage11a_lifetime_profile(uint32_t out[LT_PROFILE_WORDS])
{
    memset(out,0,LT_PROFILE_WORDS*4);out[0]=recent.frames;out[1]=recent.gte_frames;
    for(unsigned i=0;i<16;i++)out[43]+=scenes[i].used!=0;
    for(unsigned i=0;i<SLOW_SLOTS;i++)out[44]+=slow[i].wall!=0;
    for(unsigned i=0;i<4;i++)out[45]+=io_slow[i].wall!=0;
    out[46]=frame_id;out[47]=stride;
    if(!recent.frames)return;
    out[2]=(uint32_t)(recent.total/TICKS_PER_MS/recent.frames*1000);
    out[3]=(uint32_t)(recent.work/TICKS_PER_MS/recent.frames*1000);
    for(unsigned i=0;i<GP_COUNT;i++) {
        unsigned n=i==GP_GTE?recent.gte_frames:recent.frames;
        out[4+i]=n?(uint32_t)(recent.sum.ticks[i]/TICKS_PER_MS/n*1000):0;
    }
    for(unsigned i=0;i<GC_COUNT;i++)out[4+GP_COUNT+i]=(uint32_t)recent.sum.count[i];
}
#endif
#if defined(SH_CPU_AUDIT_RECORDER)
void game_prof_sample_report(FILE *out)
{
    fprintf(out,"sample_profile_basis=COMPLETED_PAD_FRAMES_INCLUSIVE_NESTED\n"
        "sample_profile_audio=INDEPENDENT_WORKER_ELAPSED\n"
        "sample_profile_frames=%u\nsample_profile_gte_frames=%u\n"
        "sample_profile_wall_ms=%.4f\nsample_profile_work_ms=%.4f\nsample_profile_worst_ms=%.4f\n",
        sample.frames,sample.gte_frames,sample.total/TICKS_PER_MS,
        sample.work/TICKS_PER_MS,sample.worst/TICKS_PER_MS);
    for(unsigned i=0;i<GP_COUNT;i++) {
        unsigned n=i==GP_GTE?sample.gte_frames:sample.frames;
        fprintf(out,"sample_profile_%s_total_ms=%.4f\nsample_profile_%s_mean_ms=%.4f\nsample_profile_%s_peak_ms=%.4f\n",
            categories[i],sample.sum.ticks[i]/TICKS_PER_MS,categories[i],
            n?sample.sum.ticks[i]/TICKS_PER_MS/n:0,categories[i],sample.peak[i]/TICKS_PER_MS);
    }
    for(unsigned i=0;i<GC_COUNT;i++)fprintf(out,"sample_profile_%s=%" PRIu64 "\n",counters[i],sample.sum.count[i]);
}
#endif
void game_prof_report(FILE *out)
{
    fprintf(out,"profile=%s\n",game_prof_enabled?"DETAILED":"OFF");
    if(!game_prof_enabled)return;
    fprintf(out,"profile_schema=3\nprofile_categories=INCLUSIVE_NESTED\nprofile_audio=INDEPENDENT_WORKER_ELAPSED\nprofile_spu_estimate=ONE_ROTATING_PCM_FRAME_PER_BLOCK\nprofile_work_excludes=VBLANK_REPORT_PAUSE\n");
    fprintf(out,"profile_frames=%u\nprofile_gte_stride=%u\nprofile_gte_frames=%u\nprofile_wall_ms=%.4f\nprofile_work_ms=%.4f\nprofile_worst_ms=%.4f\n",
        recent.frames,stride,recent.gte_frames,
        recent.frames?recent.total/TICKS_PER_MS/recent.frames:0,
        recent.frames?recent.work/TICKS_PER_MS/recent.frames:0,recent.worst/TICKS_PER_MS);
    for(unsigned i=0;i<GP_COUNT;i++) {
        unsigned n=i==GP_GTE?recent.gte_frames:recent.frames;
        fprintf(out,"profile_%s_ms=%.4f\nprofile_%s_peak_ms=%.4f\n",categories[i],
            n?recent.sum.ticks[i]/TICKS_PER_MS/n:0,categories[i],recent.peak[i]/TICKS_PER_MS);
    }
    for(unsigned i=0;i<GC_COUNT;i++)fprintf(out,"profile_%s_per_frame=%.3f\n",counters[i],
        recent.frames?(double)recent.sum.count[i]/recent.frames:0);
    for(unsigned i=0;i<16;i++)if(scenes[i].used) {
        const Scene *s=&scenes[i];
        fprintf(out,"profile_scene_%u=%u,%u,%u,%u,%u,%.4f,%.4f",i,
            s->map,s->room,s->cutscene,s->enemies,s->frames,
            s->wall/TICKS_PER_MS/s->frames,s->work/TICKS_PER_MS/s->frames);
        for(unsigned j=0;j<GP_COUNT;j++)fprintf(out,",%.4f",s->sum.ticks[j]/TICKS_PER_MS/s->frames);
        fputc('\n',out);
    }
    fprintf(out,"profile_slow_schema=3\n");
    fprintf(out,"profile_slow_rank=WORK_MINUS_VBLANK_AND_REPORT\n");
    for(unsigned i=0;i<SLOW_SLOTS+4;i++) {
        const Slow *s=i<SLOW_SLOTS?&slow[i]:&io_slow[i-SLOW_SLOTS];
        if(!s->wall)continue;
        fprintf(out,"profile_%s_%u=%u,%d,%d,%d,%u,%.3f,%u",i<SLOW_SLOTS?"slow":"io_slow",
            i<SLOW_SLOTS?i:i-SLOW_SLOTS,s->context.map,s->context.x,
            s->context.z,s->context.yaw,s->context.file,s->wall/TICKS_PER_MS,s->sampled);
        for(unsigned j=0;j<GP_COUNT;j++)fprintf(out,",%.3f",s->work.ticks[j]/TICKS_PER_MS);
        for(unsigned j=0;j<GC_COUNT;j++)fprintf(out,",%" PRIu64,s->work.count[j]);
        fputc('\n',out);
    }
    fprintf(out,"profile_complete=1\n");
}
