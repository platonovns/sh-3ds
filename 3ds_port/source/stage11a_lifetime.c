/* Snapshot-only accumulation probe. Main owns a 32-slot overwrite ring and the
 * first/record-boundary snapshots. No allocation, file I/O or growing list here.
 * Worker-owned state is copied under its existing lock, never formatted there.
 */
#include <3ds.h>
#include <malloc.h>
#include <string.h>
#include "stage11a_lifetime.h"
#include "game_profile.h"
#if defined(SH_STAGE11A_TRACEFIX)
#include "stage11a_pitch_trace.h"
#endif
#define CLOCK_HZ 268123480ull
enum { LT_BOOT,LT_TIMER,LT_CONTEXT,LT_BEGIN,LT_END,LT_MODE };
static Stage11aLifetime history[LT_HISTORY],first,boundary[2];
static uint32_t serial,used,head,enabled=
#if defined(SH_PLAYTEST)
    0,
#else
    1,
#endif
    have_first;
static uint32_t allocations[LT_ALLOC_APIS][4];
static uint64_t origin,next_tick,probe_total;
static CpuRecordContext latest;
static const char *const alloc_names[]={"malloc","calloc","realloc","free","memalign",
    "linearAlloc","linearMemAlign","linearFree","vramAlloc","vramAllocAt","vramMemAlign","vramMemAlignAt","vramFree"};
unsigned stage11a_lifetime_mode(void) {return __atomic_load_n(&enabled,__ATOMIC_ACQUIRE);}
void stage11a_lifetime_alloc(unsigned api,uint32_t bytes,int failed)
{
#if defined(SH_PLAYTEST)
    (void)api;(void)bytes;(void)failed;
#else
    if(api>=LT_ALLOC_APIS)return;
    __atomic_fetch_add(&allocations[api][0],1,__ATOMIC_RELAXED);
    __atomic_fetch_add(&allocations[api][failed?2:1],1,__ATOMIC_RELAXED);
    __atomic_fetch_add(&allocations[api][3],bytes,__ATOMIC_RELAXED);
#endif
}
static void capture(Stage11aLifetime *s,unsigned reason)
{
    uint64_t start=svcGetSystemTick();
    memset(s,0,sizeof(*s));s->tick=start-origin;s->reason=reason;s->serial=++serial;
    s->context=latest;s->mode=stage11a_lifetime_mode();
    struct mallinfo m=mallinfo();
    s->memory[0]=m.arena;s->memory[1]=m.uordblks;s->memory[2]=m.fordblks;
    s->memory[3]=m.ordblks;s->memory[4]=m.keepcost;
    s->memory[5]=envGetHeapSize();s->memory[6]=linearSpaceFree();
    s->memory[7]=envGetLinearHeapSize();s->memory[8]=vramSpaceFree();
    s64 count=-1;s->thread_result=svcGetProcessInfo(&count,CUR_PROCESS_HANDLE,7);s->threads=(uint32_t)count;
    stage11a_lifetime_render(s);stage11a_lifetime_cache(s->cache);
    stage11a_lifetime_profile(s->profile);
    stage11a_lifetime_spu(s->spu,s->voices);stage11a_lifetime_xa(s->xa);
    stage11a_lifetime_audio(s->audio);stage11a_lifetime_resource(s->resource);
    for(unsigned a=0;a<LT_ALLOC_APIS;a++)for(unsigned i=0;i<4;i++)
        s->alloc[a][i]=__atomic_load_n(&allocations[a][i],__ATOMIC_RELAXED);
    s->capture_ticks=svcGetSystemTick()-start;probe_total+=s->capture_ticks;
    /* This one sparse observer stall is explicit, not claimed as game work. */
    if(game_prof_enabled)game_prof_add(GP_REPORT,s->capture_ticks);
}
static void remember(unsigned reason)
{
    capture(&history[head],reason);
    if(!have_first){first=history[head];have_first=1;}
    head=(head+1)%LT_HISTORY;if(used<LT_HISTORY)used++;
}
void stage11a_lifetime_init(void)
{
    if(origin)return;
    origin=svcGetSystemTick();next_tick=origin+10*CLOCK_HZ;
    /* Called once per application launch; never from Title/map reset. */
}
void stage11a_lifetime_poll(const CpuRecordContext *context)
{
    unsigned changed=context->game!=latest.game || context->map!=latest.map || context->room!=latest.room;
    latest=*context;
    uint64_t now=svcGetSystemTick();
    if(!have_first || changed || now>=next_tick) {
        remember(!have_first?LT_BOOT:changed?LT_CONTEXT:LT_TIMER);
        next_tick=now+10*CLOCK_HZ;
    }
}
void stage11a_lifetime_boundary(unsigned start)
{
    capture(&boundary[start?0:1],start?LT_BEGIN:LT_END);
}
int stage11a_lifetime_toggle(void)
{
    unsigned mode=!stage11a_lifetime_mode();
    __atomic_store_n(&enabled,mode,__ATOMIC_RELEASE);
    game_prof_lifetime_toggle(mode);game_cpu_audit_lifetime_toggle(mode);
    remember(LT_MODE);return (int)mode;
}
static void words(FILE *out,const char *label,const char *group,const uint32_t *p,unsigned n)
{
    fprintf(out,"lifetime_%s_%s=",label,group);
    for(unsigned i=0;i<n;i++)fprintf(out,"%s%lu",i?",":"",(unsigned long)p[i]);
    fputc('\n',out);
}
static void report_one(FILE *out,const char *label,const Stage11aLifetime *s)
{
    fprintf(out,"lifetime_%s_stamp=%lu,%lu,%.6f,%.6f,%lu,0x%08lX,%lu\n",label,
        (unsigned long)s->serial,(unsigned long)s->reason,s->tick/(CLOCK_HZ/1000.0),
        s->capture_ticks/(CLOCK_HZ/1000.0),(unsigned long)s->mode,(unsigned long)s->thread_result,(unsigned long)s->threads);
    const CpuRecordContext *c=&s->context;
    fprintf(out,"lifetime_%s_context=%lu,%lu,%lu,%lu,%lu,%lu,%ld,%ld,%ld",label,
        (unsigned long)c->game,(unsigned long)c->map,(unsigned long)c->room,(unsigned long)c->flashlight,
        (unsigned long)c->fps_mode,(unsigned long)c->control_mode,(long)c->x,(long)c->z,(long)c->yaw);
    for(unsigned i=0;i<6;i++){fprintf(out,",%ld",(long)c->view[i]);}
    fputc('\n',out);
    words(out,label,"memory",s->memory,9);words(out,label,"render",s->render,LT_RENDER_WORDS);
    words(out,label,"cache",s->cache,LT_CACHE_WORDS);words(out,label,"profile",s->profile,LT_PROFILE_WORDS);
    words(out,label,"spu",s->spu,LT_SPU_WORDS);words(out,label,"xa",s->xa,LT_XA_WORDS);
    words(out,label,"audio",s->audio,LT_AUDIO_WORDS);words(out,label,"resource",s->resource,LT_RESOURCE_WORDS);
    for(unsigned i=0;i<24;i++){char name[24];snprintf(name,sizeof(name),"voice_%02u",i);words(out,label,name,s->voices[i],LT_VOICE_WORDS);}
    for(unsigned i=0;i<LT_ALLOC_APIS;i++){char name[40];snprintf(name,sizeof(name),"alloc_%s",alloc_names[i]);words(out,label,name,s->alloc[i],4);}
}
void stage11a_lifetime_report(FILE *out)
{
    fprintf(out,"lifetime_schema=1\nlifetime_session=%016llX\nlifetime_history_capacity=%u\n"
        "lifetime_snapshot_bytes=%u\nlifetime_static_bytes=%u\nlifetime_history_used=%lu\n"
        "lifetime_probe_total_ms=%.6f\nlifetime_profile_mode=%u\n",
        (unsigned long long)origin,LT_HISTORY,(unsigned)sizeof(Stage11aLifetime),
        (unsigned)(sizeof(history)+sizeof(first)+sizeof(boundary)+sizeof(allocations)),
        (unsigned long)used,probe_total/(CLOCK_HZ/1000.0),stage11a_lifetime_mode());
    fputs("lifetime_stamp_schema=serial,reason,uptime_ms,probe_ms,profile_mode,thread_result,threads\n"
        "lifetime_reason_schema=boot:0,timer:1,context:2,window_begin:3,window_end:4,mode:5\n"
        "lifetime_memory_schema=arena,used,free_chunks_bytes,free_chunk_count,top_chunk,heap_budget,linear_free,linear_budget,vram_free\n"
        "lifetime_largest_allocation=UNAVAILABLE_NO_ALLOCATION_PROBE_top_chunk_is_not_largest\n"
        "lifetime_alloc_schema=observed_calls,successes,failures,requested_bytes_mod32\n"
        "lifetime_alloc_coverage=LINKER_EXTERNAL_CALLS_INTERNAL_ALIASES_MAY_BYPASS_DO_NOT_SUM_NESTED_APIS\n"
        "lifetime_voice_schema=pitch,env_level,env_phase,volmode_left,volmode_right,cur_addr,pitch_counter,env_counter,last_out,flags\n"
        "lifetime_voice_flags=released:1,ever_keyed:2,noise:4,pmon:8,reverb:16,endx:32,block_valid:64,frozen:128\n"
        "lifetime_spu_schema=resets,keyon_calls,keyoff_calls,released_mask,ever_keyed_count,pitch_nonzero,env_nonzero,frozen_count,silent_nonzero_pitch,cd_pending,endx,noise_mask,pmon_mask,reverb_mask,reverb_enabled,voice_capacity\n"
        "lifetime_xa_schema=epoch,active,paused,queued,capacity,rate,channels,starts,stops,raw,underflows,resampler_present,event_count,event_capacity,ring_in,ring_out\n"
        "lifetime_audio_schema=rendered,starves,drops,paused,running,started,init_result,max_render_us,queue_free,queue_queued,queue_playing,queue_done,queue_capacity,worker_present\n"
        "lifetime_profile_schema=recent_frames,gte_frames,wall_us,work_us,category_mean_us_in_existing_GP_order_then_counter_totals\n"
        "lifetime_resource_schema=span_count,span_capacity,cache_bytes,extra_bytes,cache_peak,preload_files,cache_hits,cache_misses,image_span_active,io_history_used\n"
        "lifetime_cache_schema=invalidate_calls,image_dirty_marks,clut_dirty_marks,both_dirty_marks,recent_presentations,wall_us,texture_us,submit_us,primitive_us,vblank_us,logical_frames,partial_flushes,packet_last,vertices_last,max_parts,native_dirty,feedback_invalidation_calls,feedback_ready_at_write,frame_captured,frame_valid,feedback_ready,feedback_world,feedback_trace_count,feedback_trace_capacity\n"
        "lifetime_render_schema=cache_active,cache_peak,occupied,pinned,dirty,clean,index_used,allocated_slots,lru_clock,hits,misses,comparisons,invalidations,uploads,evictions,vram_generation,feedback_generation,pending_draws,pending_primitives,pending_vertices,packet_peak,primitive_peak,batches_last,texture_bytes,readback_copies,draws_last,vertex_capacity,command_capacity,feedback_words,feedback_texture,peak_pinned,cache_capacity,renderer_textures,list_overflow,renderer_vertices,in_frame,pending_gpu,readback_generation,readback_valid,command_usage_ppm\n",out);
    report_one(out,"first",&first);report_one(out,"begin",&boundary[0]);report_one(out,"end",&boundary[1]);
    for(unsigned i=0;i<used;i++) {char label[24];snprintf(label,sizeof(label),"history_%02u",i);
        report_one(out,label,&history[(head+LT_HISTORY-used+i)%LT_HISTORY]);}
#if defined(SH_STAGE11A_TRACEFIX)
    game_spu_pitch_trace_report(out);
#endif
}
