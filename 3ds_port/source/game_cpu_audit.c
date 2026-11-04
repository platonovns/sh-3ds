/* Read-only scheduling inventory; elapsed scopes are NOT scheduled CPU time.
 * No thread trampoline, priority/affinity changes, or CPU-budget changes. */
#include <3ds.h>
#include <inttypes.h>
#include <string.h>
#include "game_cpu_audit.h"
#include "game_profile.h"
#if defined(SH_CPU_AUDIT_RECORDER)
#include "game_cpu_recorder.h"
#endif
#define SLOTS 16u
typedef struct {
    uint32_t ready, handle, id, entry, stack;
    int32_t priority, core, detached, result;
} Created;
typedef struct { uint32_t id, cores; } Observed;
/* Every scope has exactly one writer. All shared words are atomic, including
 * the split 64-bit sum: ARM11 needs no 64-bit atomic library helpers. */
typedef struct { uint32_t sequence, low, high, calls, peak_us; } Timing;
static Created created[SLOTS];
static Observed observed[GCPU_THREADS];
static Timing timing[GCPU_SCOPES];
#if defined(SH_CPU_AUDIT_RECORDER)
void game_cpu_audit_snapshot(CpuRecordSnapshot *out)
{
    memset(out,0,sizeof(*out));
    for(unsigned i=0;i<GCPU_SCOPES;i++) {
        Timing *r=&timing[i];
        for(unsigned retry=0;retry<8;retry++) {
            unsigned a=__atomic_load_n(&r->sequence,__ATOMIC_ACQUIRE);
            if(a&1)continue;
            out->ticks[i]=((uint64_t)__atomic_load_n(&r->high,__ATOMIC_RELAXED)<<32)|
                __atomic_load_n(&r->low,__ATOMIC_RELAXED);
            out->calls[i]=__atomic_load_n(&r->calls,__ATOMIC_RELAXED);
            __atomic_thread_fence(__ATOMIC_ACQUIRE);
            if(a==__atomic_load_n(&r->sequence,__ATOMIC_RELAXED)) {
                out->valid|=1u<<i;break;
            }
        }
    }
}
#endif
static uint32_t attempts, detailed_enabled, initialized;
static uint64_t enabled_at;
static bool new3ds;
static Result model_result, budget_result, luma_result, kext_result;
static uint32_t budget;
static s64 luma_version;
static int marker, probe_requested;
static uint32_t core_reader, probe_mask;
#if defined(SH_STAGE11A_LIFETIME)
void game_cpu_audit_lifetime_toggle(unsigned enabled)
{__atomic_store_n(&detailed_enabled,enabled,__ATOMIC_RELEASE);}
#endif
static struct { Thread thread; uint32_t done; int core; } probes[4];
static const char *const names[]={"main","spu","xa","ndsp"};
static const char *const scope_names[]={"spu_block","spu_wait","xa_step","xa_wait","flashlight_setup","resolve"};
/* Retail SVC 0x0D/0x0F/0x11 are stubs. Never call them as measurements.
 * Luma's explicitly detected custom SVC executes this leaf reader in SVC mode.
 * It reads only MPIDR, with no kernel pointers, locks or state changes. */
#if defined(__arm__)
static int read_mpidr(void)
{
    uint32_t value;
    __asm__ volatile("mrc p15, 0, %0, c0, c0, 5" : "=r"(value));
    return value&3;
}
extern int game_cpu_mpidr_svc(void *reader);
__asm__(".pushsection .text.game_cpu_mpidr_svc,\"ax\",%progbits\n"
        ".align 2\n.arm\n.global game_cpu_mpidr_svc\n"
        ".type game_cpu_mpidr_svc,%function\n"
        "game_cpu_mpidr_svc:\nsvc 0x80\nbx lr\n"
        ".size game_cpu_mpidr_svc,.-game_cpu_mpidr_svc\n.popsection\n");
#endif
static int current_core(void)
{
    if(!__atomic_load_n(&core_reader,__ATOMIC_ACQUIRE))return -1;
#if defined(SH_CPU_AUDIT_TEST)
    return svcGetProcessorID(); /* host mock only, never a production SVC */
#elif defined(__arm__)
    return game_cpu_mpidr_svc(read_mpidr);
#else
    return -1;
#endif
}

/* Preserve all arguments, TLS, entrypoint, return values and kernel errors. */
Result __real_svcCreateThread(Handle*,ThreadFunc,u32,u32*,s32,s32);
Result __wrap_svcCreateThread(Handle *out,ThreadFunc entry,u32 arg,u32 *stack,s32 priority,s32 core)
{
    Result rc=__real_svcCreateThread(out,entry,arg,stack,priority,core);
    unsigned i=__atomic_fetch_add(&attempts,1,__ATOMIC_RELAXED);
    if(i<SLOTS) {
        Created *r=&created[i];r->handle=R_SUCCEEDED(rc)?*out:0;
        r->entry=(uintptr_t)entry;r->priority=priority;r->core=core;r->result=rc;
        if(r->handle)svcGetThreadId(&r->id,r->handle);
        __atomic_store_n(&r->ready,1,__ATOMIC_RELEASE);
    }
    return rc;
}
Thread __real_threadCreate(ThreadFunc,void*,size_t,int,int,bool);
Thread __wrap_threadCreate(ThreadFunc entry,void *arg,size_t stack,int priority,int core,bool detached)
{
    /* Also runs before main(), when libctru creates APT's helper. */
    unsigned before=__atomic_load_n(&attempts,__ATOMIC_ACQUIRE);
    Thread t=__real_threadCreate(entry,arg,stack,priority,core,detached);
    unsigned end=__atomic_load_n(&attempts,__ATOMIC_ACQUIRE);
    for(unsigned i=before;i<end && i<SLOTS;i++) {
        Created *r=&created[i];
        if(!__atomic_load_n(&r->ready,__ATOMIC_ACQUIRE))continue;
        /* Current creators run sequentially on main. Do not dereference t:
         * a detached thread may have freed it before threadCreate returns. */
        if(r->priority!=priority || r->core!=core)continue;
        __atomic_store_n(&r->ready,0,__ATOMIC_RELEASE);
        r->entry=(uintptr_t)entry;r->stack=stack;r->detached=detached;
        __atomic_store_n(&r->ready,1,__ATOMIC_RELEASE);
        break;
    }
    return t;
}
void game_cpu_audit_enter(unsigned thread)
{
#if defined(SH_PLAYTEST)
    (void)thread;
#else
    if(thread>=GCPU_THREADS)return;
    Observed *r=&observed[thread];
    if(!__atomic_load_n(&r->id,__ATOMIC_RELAXED)) {
        u32 id=0;svcGetThreadId(&id,CUR_THREAD_HANDLE);
        __atomic_store_n(&r->id,id,__ATOMIC_RELEASE);
    }
    int core=current_core();
    if(core>=0 && core<4)__atomic_fetch_or(&r->cores,1u<<core,__ATOMIC_RELAXED);
#endif
}
uint64_t game_cpu_audit_begin(unsigned thread)
{
#if defined(SH_PLAYTEST)
    (void)thread;return 0;
#else
    if(!__atomic_load_n(&detailed_enabled,__ATOMIC_ACQUIRE))return 0;
    game_cpu_audit_enter(thread);
    return svcGetSystemTick();
#endif
}
void game_cpu_audit_end(unsigned scope,uint64_t start)
{
#if defined(SH_PLAYTEST)
    (void)scope;(void)start;
#else
    if(!start || scope>=GCPU_SCOPES)return;
    uint64_t elapsed=svcGetSystemTick()-start;
    Timing *r=&timing[scope];
    __atomic_fetch_add(&r->sequence,1,__ATOMIC_ACQ_REL);
    uint64_t sum=((uint64_t)__atomic_load_n(&r->high,__ATOMIC_RELAXED)<<32)|__atomic_load_n(&r->low,__ATOMIC_RELAXED);
    sum+=elapsed;
    __atomic_store_n(&r->low,(uint32_t)sum,__ATOMIC_RELAXED);
    __atomic_store_n(&r->high,(uint32_t)(sum>>32),__ATOMIC_RELAXED);
    __atomic_fetch_add(&r->calls,1,__ATOMIC_RELAXED);
    uint64_t us=elapsed*1000000/SYSCLOCK_ARM11;
    uint32_t peak=us>UINT32_MAX?UINT32_MAX:(uint32_t)us;
    if(peak>__atomic_load_n(&r->peak_us,__ATOMIC_RELAXED))__atomic_store_n(&r->peak_us,peak,__ATOMIC_RELAXED);
    __atomic_fetch_add(&r->sequence,1,__ATOMIC_RELEASE);
#endif
}
static void probe(void *arg)
{
    unsigned i=(uintptr_t)arg;
    probes[i].core=current_core();
    __atomic_store_n(&probes[i].done,1,__ATOMIC_RELEASE);
}
void __real_Gfx_FlashlightUpdate(void);
void __wrap_Gfx_FlashlightUpdate(void)
{
    uint64_t start=game_cpu_audit_begin(GCPU_MAIN);
    __real_Gfx_FlashlightUpdate();
    game_cpu_audit_end(GCPU_FLASHLIGHT_SETUP,start);
}
void game_cpu_audit_init(unsigned detailed)
{
    if(initialized)return;
    initialized=1;
    model_result=APT_CheckNew3DS(&new3ds);
    budget_result=APT_GetAppCpuTimeLimit(&budget);
    luma_result=svcGetSystemInfo(&luma_version,0x10000,0);
    s64 detect=0;kext_result=svcGetSystemInfo(&detect,0x20000,0);
    FILE *f=fopen("sdmc:/3ds/silenthill/stage10_cpu_audit.txt","rb");
    if(f) {
        char token[16]={0};size_t n=fread(token,1,sizeof(token)-1,f);fclose(f);
        remove("sdmc:/3ds/silenthill/stage10_cpu_audit.txt");
        marker=n==10 && !memcmp(token,"CPU_AUDIT\n",10)?1:-1;
    }
#if defined(SH_CPU_AUDIT_RECORDER)
    /* This separate, explicitly selected diagnostic build needs no SD marker. */
    marker=1;
#endif
    if(detailed || marker==1) {
        if(marker==1 && !game_prof_enabled)game_prof_enable(16);
        enabled_at=svcGetSystemTick();
        __atomic_store_n(&detailed_enabled,1,__ATOMIC_RELEASE);
    }
    /* Luma returns Result=1; Azahar returns Result=0, out=1 for this query.
     * Only the explicit hardware marker permits the supervisor-mode reader. */
    if(marker==1 && kext_result==1 && R_SUCCEEDED(luma_result))
        __atomic_store_n(&core_reader,1,__ATOMIC_RELEASE);
    game_cpu_audit_enter(GCPU_MAIN);
    probe_requested=marker==1;
    if(!probe_requested)return;
    /* One-shot permission test, not a utilization benchmark or game worker.
     * Leave a zero/unknown APT budget untouched; never wait without a bound. */
    for(unsigned i=0;i<(R_SUCCEEDED(model_result) && new3ds?4u:2u);i++) {
        probes[i].core=-1;
        if(i==1 && (R_FAILED(budget_result) || !budget))continue;
        probe_mask|=1u<<i;
        probes[i].thread=threadCreate(probe,(void*)(uintptr_t)i,4096,0x3e,i,false);
        if(probes[i].thread && R_SUCCEEDED(threadJoin(probes[i].thread,100000000))) {
            threadFree(probes[i].thread);probes[i].thread=NULL;
        }
        /* Keep a timed-out allocation until a later successful nonblocking
         * join. Never free a running thread or silently claim it executed. */
    }
}
void game_cpu_audit_poll(void)
{
    if(!__atomic_load_n(&detailed_enabled,__ATOMIC_ACQUIRE))return;
    game_cpu_audit_enter(GCPU_MAIN);
    for(unsigned i=0;i<4;i++)if(probes[i].thread && R_SUCCEEDED(threadJoin(probes[i].thread,0))) {
        threadFree(probes[i].thread);probes[i].thread=NULL;
    }
}
static void thread_report(FILE *out,unsigned index,Handle handle,u32 expected)
{
    u32 id=0;Result ir=svcGetThreadId(&id,handle);
    s32 priority=-1;
    Result pr=-1;
    bool valid=R_SUCCEEDED(ir) && (!expected || id==expected);
    if(valid) {
        pr=svcGetThreadPriority(&priority,handle);
    }
    fprintf(out,"cpu_thread_%u_runtime=%u,0x%08lX,%lu,0x%08lX,%ld\n",
        index,valid,(unsigned long)ir,(unsigned long)id,(unsigned long)pr,(long)priority);
}
void game_cpu_audit_report(FILE *out)
{
    if(!initialized)return;
    fprintf(out,"cpu_audit_schema=2\ncpu_timing_basis=ELAPSED_INCLUDING_PREEMPTION_AND_BLOCKING\n"
        "cpu_scheduled_thread_ticks=UNAVAILABLE_STANDARD_3DS_SVC\ncpu_core_idle_ticks=UNAVAILABLE_STANDARD_3DS_SVC\n"
        "cpu_affinity_policy=UNCHANGED\ncpu_budget_policy=UNCHANGED\ncpu_detailed=%lu\ncpu_marker=%d\n"
        "cpu_model_result=0x%08lX\ncpu_new3ds=%u\ncpu_apt_budget_result=0x%08lX\ncpu_apt_budget_percent=%lu\n"
        "cpu_luma_result=0x%08lX\ncpu_luma_version=0x%08lX\n",
        (unsigned long)detailed_enabled,marker,(unsigned long)model_result,new3ds,
        (unsigned long)budget_result,(unsigned long)budget,(unsigned long)luma_result,(unsigned long)luma_version);
    fprintf(out,"cpu_core_reader=%s\ncpu_kext_detect_result=0x%08lX\n"
        "cpu_affinity_query=UNAVAILABLE_RETAIL_STUB\n",
        core_reader?"LUMA_MPIDR_OPT_IN":"UNAVAILABLE_NO_OPT_IN_LUMA",(unsigned long)kext_result);
    s64 threads=-1;Result tr=svcGetProcessInfo(&threads,CUR_PROCESS_HANDLE,7);
    fprintf(out,"cpu_process_thread_count=0x%08lX,%" PRId64 "\n",(unsigned long)tr,(int64_t)threads);
    if(R_SUCCEEDED(luma_result))for(unsigned i=0;i<3;i++) {
        s64 value=0;Result rc=svcGetSystemInfo(&value,0x10001,i);
        fprintf(out,"cpu_luma_n3ds_%u=0x%08lX,%" PRId64 "\n",i,(unsigned long)rc,(int64_t)value);
    }
    fprintf(out,"cpu_thread_create_schema=handle,id,entry,stack,priority,core_argument,detached,kernel_result\n"
        "cpu_thread_runtime_schema=valid,id_result,id,priority_result,priority\n");
    thread_report(out,0,CUR_THREAD_HANDLE,observed[GCPU_MAIN].id);
    unsigned n=__atomic_load_n(&attempts,__ATOMIC_ACQUIRE);
    fprintf(out,"cpu_create_attempts=%u\ncpu_inventory_overflow=%u\n",n,n>SLOTS?n-SLOTS:0);
    for(unsigned i=0;i<n && i<SLOTS;i++) {
        const Created *r=&created[i];
        if(!__atomic_load_n(&r->ready,__ATOMIC_ACQUIRE))continue;
        fprintf(out,"cpu_thread_%u_create=0x%08lX,%lu,0x%08lX,%lu,%ld,%ld,%ld,0x%08lX\n",
            i+1,(unsigned long)r->handle,(unsigned long)r->id,(unsigned long)r->entry,(unsigned long)r->stack,
            (long)r->priority,(long)r->core,(long)r->detached,(unsigned long)r->result);
        if(r->handle)thread_report(out,i+1,r->handle,r->id);
    }
    for(unsigned i=0;i<GCPU_THREADS;i++)fprintf(out,"cpu_observed_%s=%lu,0x%lX\n",names[i],
        (unsigned long)__atomic_load_n(&observed[i].id,__ATOMIC_ACQUIRE),
        (unsigned long)__atomic_load_n(&observed[i].cores,__ATOMIC_RELAXED));
    fprintf(out,"cpu_probe_requested=%d\n",probe_requested);
    if(probe_requested)for(unsigned i=0;i<4;i++)fprintf(out,"cpu_probe_%u=%u,%lu,%d,%u\n",i,
        (unsigned)((probe_mask>>i)&1),(unsigned long)__atomic_load_n(&probes[i].done,__ATOMIC_ACQUIRE),probes[i].core,probes[i].thread!=NULL);
    double wall=detailed_enabled?(svcGetSystemTick()-enabled_at)*1000.0/SYSCLOCK_ARM11:0;
    fprintf(out,"cpu_elapsed_window_ms=%.4f\ncpu_scope_schema=calls,elapsed_ms,peak_us\n",wall);
    for(unsigned i=0;i<GCPU_SCOPES;i++) {
        Timing *r=&timing[i];unsigned valid=0,calls=0,peak=0;uint64_t sum=0;
        for(unsigned retry=0;retry<8;retry++) {
            unsigned a=__atomic_load_n(&r->sequence,__ATOMIC_ACQUIRE);
            if(a&1)continue;
            sum=((uint64_t)__atomic_load_n(&r->high,__ATOMIC_RELAXED)<<32)|__atomic_load_n(&r->low,__ATOMIC_RELAXED);
            calls=__atomic_load_n(&r->calls,__ATOMIC_RELAXED);peak=__atomic_load_n(&r->peak_us,__ATOMIC_RELAXED);
            __atomic_thread_fence(__ATOMIC_ACQUIRE);
            if(a==__atomic_load_n(&r->sequence,__ATOMIC_RELAXED)){valid=1;break;}
        }
        fprintf(out,"cpu_scope_%s_valid=%u\ncpu_scope_%s=%u,%.4f,%u\n",scope_names[i],valid,
            scope_names[i],calls,sum*1000.0/SYSCLOCK_ARM11,peak);
    }
}
