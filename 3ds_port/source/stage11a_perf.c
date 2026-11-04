/* Bounded recording-window statistics, no allocation or I/O in measurement paths.
 * All shared fields use 32-bit atomics; no ARM11 64-bit atomic helper is needed.
 * Each metric has exactly one writer. Main starts/stops epochs and reads only.
 */
#include "stage11a_perf.h"
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
#endif
#include <string.h>
#define BINS 256u
#define DISTRIBUTIONS 6u
#define TICKS_PER_MS 268123.480
typedef struct {
    uint32_t seq,epoch,calls,lo,hi,max_lo,max_hi,misses;
} Metric;
static Metric metrics[S11_COUNT];
static uint32_t bins[DISTRIBUTIONS][BINS],queue[5];
static uint32_t active_epoch,next_epoch,queue_epoch,queue_seq;
static const char *const names[]={"wall","work","spu_block","spu_render",
    "main_lock","spu_lock","dsp_flush","ndsp_submit","advance_inclusive",
    "adpcm_nested","interpolation","adsr","volume","accumulate","cd_mix","reverb",
    "output","voice_visits","voice_env_nonzero","frozen_visits","noise_visits","pmon_visits"};
static uint32_t width_us(unsigned metric) {return metric<2?1000u:100u;}
int stage11a_perf_active(void) {return __atomic_load_n(&active_epoch,__ATOMIC_ACQUIRE)!=0;}
void stage11a_perf_start(void)
{
    /* No concurrent reset of worker-owned storage: each writer clears its own
     * metric lazily on the next observation of the new epoch. */
    if(++next_epoch==0)++next_epoch;
    __atomic_store_n(&active_epoch,next_epoch,__ATOMIC_RELEASE);
}
void stage11a_perf_stop(void) {__atomic_store_n(&active_epoch,0,__ATOMIC_RELEASE);}
void stage11a_perf_add(unsigned id,uint64_t ticks)
{
#if defined(SH_STAGE11A_LIFETIME)
    if(!stage11a_lifetime_mode())return;
#endif
    uint32_t epoch=__atomic_load_n(&active_epoch,__ATOMIC_ACQUIRE);
    if(!epoch || id>=S11_COUNT)return;
    Metric *m=&metrics[id];
    __atomic_fetch_add(&m->seq,1,__ATOMIC_ACQ_REL);
    if(__atomic_load_n(&m->epoch,__ATOMIC_RELAXED)!=epoch) {
        __atomic_store_n(&m->calls,0,__ATOMIC_RELAXED);
        __atomic_store_n(&m->lo,0,__ATOMIC_RELAXED);__atomic_store_n(&m->hi,0,__ATOMIC_RELAXED);
        __atomic_store_n(&m->max_lo,0,__ATOMIC_RELAXED);__atomic_store_n(&m->max_hi,0,__ATOMIC_RELAXED);
        __atomic_store_n(&m->misses,0,__ATOMIC_RELAXED);
        if(id<DISTRIBUTIONS)for(unsigned i=0;i<BINS;i++)__atomic_store_n(&bins[id][i],0,__ATOMIC_RELAXED);
        __atomic_store_n(&m->epoch,epoch,__ATOMIC_RELAXED);
    }
    uint64_t sum=((uint64_t)__atomic_load_n(&m->hi,__ATOMIC_RELAXED)<<32)|__atomic_load_n(&m->lo,__ATOMIC_RELAXED);
    sum+=ticks;
    __atomic_store_n(&m->lo,(uint32_t)sum,__ATOMIC_RELAXED);__atomic_store_n(&m->hi,(uint32_t)(sum>>32),__ATOMIC_RELAXED);
    uint64_t peak=((uint64_t)__atomic_load_n(&m->max_hi,__ATOMIC_RELAXED)<<32)|__atomic_load_n(&m->max_lo,__ATOMIC_RELAXED);
    if(ticks>peak) {
        __atomic_store_n(&m->max_lo,(uint32_t)ticks,__ATOMIC_RELAXED);
        __atomic_store_n(&m->max_hi,(uint32_t)(ticks>>32),__ATOMIC_RELAXED);
    }
    __atomic_fetch_add(&m->calls,1,__ATOMIC_RELAXED);
    if(id==S11_BLOCK && ticks>3112907u) /* floor(512*268123480/44100) */
        __atomic_fetch_add(&m->misses,1,__ATOMIC_RELAXED);
    if(id<DISTRIBUTIONS) {
        /* Exact rational bucket boundaries; clamp before multiplication so
         * unusually long stalls cannot overflow the 64-bit numerator. */
        uint64_t divisor=(uint64_t)width_us(id)*268123480u;
        unsigned b=ticks>=(divisor*(BINS-1)+999999u)/1000000u?BINS-1:
            (unsigned)(ticks*1000000u/divisor);
        __atomic_fetch_add(&bins[id][b],1,__ATOMIC_RELAXED);
    }
    __atomic_fetch_add(&m->seq,1,__ATOMIC_RELEASE);
}
void stage11a_perf_queue(unsigned depth)
{
    uint32_t epoch=__atomic_load_n(&active_epoch,__ATOMIC_ACQUIRE);
    if(!epoch)return;
    __atomic_fetch_add(&queue_seq,1,__ATOMIC_ACQ_REL);
    if(__atomic_load_n(&queue_epoch,__ATOMIC_RELAXED)!=epoch) {
        for(unsigned i=0;i<5;i++)__atomic_store_n(&queue[i],0,__ATOMIC_RELAXED);
        __atomic_store_n(&queue_epoch,epoch,__ATOMIC_RELAXED);
    }
    if(depth>4)depth=4;
    __atomic_fetch_add(&queue[depth],1,__ATOMIC_RELAXED);
    __atomic_fetch_add(&queue_seq,1,__ATOMIC_RELEASE);
}
void stage11a_perf_report(FILE *out)
{
    fprintf(out,"stage11a_schema=1\nstage11a_variant=CONTROL_INSTRUMENTED\n"
        "stage11a_spu_detail=%u\nstage11a_basis=ELAPSED_INCLUDING_PREEMPTION_AND_BLOCKING\n"
        "stage11a_boundary=COMPLETED_OBSERVATIONS_CALLS_MAY_STRADDLE_WINDOW\n"
        "stage11a_detail_basis=ONE_ROTATING_PCM_FRAME_EVERY_16_BLOCKS_NESTED_SCOPES\n"
        "stage11a_metric_schema=valid,calls,total_ms,max_ms,block_budget_exceedances\n"
        "stage11a_hist_schema=bin_width_us,counts_0_through_255_last_is_overflow\n"
        "stage11a_stats_bytes=%u\n",SH_STAGE11A_SPU_DETAIL,(unsigned)(sizeof(metrics)+sizeof(bins)+sizeof(queue)+16));
    for(unsigned id=0;id<S11_COUNT;id++) {
        Metric *m=&metrics[id];uint32_t seq=0,epoch=0,calls=0,lo=0,hi=0,ml=0,mh=0,misses=0,valid=0;
        uint32_t copy[BINS];
        for(unsigned retry=0;retry<8;retry++) {
            seq=__atomic_load_n(&m->seq,__ATOMIC_ACQUIRE);if(seq&1)continue;
            epoch=__atomic_load_n(&m->epoch,__ATOMIC_RELAXED);
            calls=__atomic_load_n(&m->calls,__ATOMIC_RELAXED);
            lo=__atomic_load_n(&m->lo,__ATOMIC_RELAXED);hi=__atomic_load_n(&m->hi,__ATOMIC_RELAXED);
            ml=__atomic_load_n(&m->max_lo,__ATOMIC_RELAXED);mh=__atomic_load_n(&m->max_hi,__ATOMIC_RELAXED);
            misses=__atomic_load_n(&m->misses,__ATOMIC_RELAXED);
            if(id<DISTRIBUTIONS)for(unsigned b=0;b<BINS;b++)copy[b]=__atomic_load_n(&bins[id][b],__ATOMIC_RELAXED);
            __atomic_thread_fence(__ATOMIC_ACQUIRE);
            if(seq==__atomic_load_n(&m->seq,__ATOMIC_RELAXED)){valid=1;break;}
        }
        if(epoch!=next_epoch){calls=lo=hi=ml=mh=misses=0;if(id<DISTRIBUTIONS)memset(copy,0,sizeof(copy));}
        fprintf(out,"stage11a_metric_%s=%u,%lu,%.6f,%.6f,%lu\n",names[id],(unsigned)valid,
            (unsigned long)calls,(((uint64_t)hi<<32)|lo)/TICKS_PER_MS,
            (((uint64_t)mh<<32)|ml)/TICKS_PER_MS,(unsigned long)misses);
        if(id<DISTRIBUTIONS && valid) {
            fprintf(out,"stage11a_hist_%s=%lu",names[id],(unsigned long)width_us(id));
            for(unsigned b=0;b<BINS;b++)fprintf(out,",%lu",(unsigned long)copy[b]);
            fputc('\n',out);
        }
    }
    unsigned qvalid=0;uint32_t qcopy[5]={0};
    for(unsigned retry=0;retry<8;retry++) {
        unsigned seq=__atomic_load_n(&queue_seq,__ATOMIC_ACQUIRE);if(seq&1)continue;
        unsigned epoch=__atomic_load_n(&queue_epoch,__ATOMIC_RELAXED);
        for(unsigned i=0;i<5;i++)qcopy[i]=epoch==next_epoch?__atomic_load_n(&queue[i],__ATOMIC_RELAXED):0;
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if(seq==__atomic_load_n(&queue_seq,__ATOMIC_RELAXED)){qvalid=1;break;}
    }
    fprintf(out,"stage11a_queue_valid=%u\nstage11a_queue_depth_after_submit=",qvalid);
    for(unsigned i=0;i<5;i++)fprintf(out,"%s%lu",i?",":"",(unsigned long)qcopy[i]);
    fputc('\n',out);
}
