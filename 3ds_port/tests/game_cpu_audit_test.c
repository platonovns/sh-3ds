#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <stdatomic.h>
#define SH_CPU_AUDIT_TEST 1
#include "../source/game_cpu_audit.c"
static _Thread_local uint64_t ticks;
static _Thread_local int processor;
static unsigned clock_calls, real_calls, freed, light_calls;
static int denied, pending;
static atomic_int writer_done;
struct MockThread { unsigned handle; };
static struct MockThread mock_thread={0x123};
int game_prof_enabled, game_prof_gte_sample;
void game_prof_enable(unsigned stride) { assert(stride==16);game_prof_enabled=1; }
uint64_t svcGetSystemTick(void) { if(!processor)clock_calls++;return ticks; }
int svcGetProcessorID(void) { return processor; }
Result svcGetThreadId(u32 *id,Handle h) { *id=h==CUR_THREAD_HANDLE?11:12;return 0; }
Result svcGetThreadPriority(s32 *p,Handle h) { (void)h;*p=0x30;return 0; }
Result svcGetThreadIdealProcessor(s32 *p,Handle h) { (void)h;*p=0;return 0; }
Result svcGetThreadAffinityMask(u8 *m,Handle h,s32 count)
{ (void)m;(void)h;assert(count==4);return (Result)0xF8C007F4; }
Result svcGetSystemInfo(s64 *v,u32 type,s32 param)
{ (void)type;(void)param;*v=0;return (Result)0xF8C007F4; }
Result svcGetProcessInfo(s64 *v,Handle h,u32 type)
{ assert(h==CUR_PROCESS_HANDLE && type==7);*v=4;return 0; }
Result APT_CheckNew3DS(bool *p) { *p=true;return 0; }
Result APT_GetAppCpuTimeLimit(u32 *p) { *p=0;return 0; }
Result threadJoin(Thread t,s64 timeout)
{ assert(t==&mock_thread);assert(timeout==0 || timeout==100000000);return pending?-1:0; }
void threadFree(Thread t) { assert(t==&mock_thread);freed++; }
Result __real_svcCreateThread(Handle *h,ThreadFunc ep,u32 arg,u32 *stack,s32 priority,s32 core)
{
    assert(ep && arg==123 && stack==(u32*)0x888);
    assert(priority==0x2f && core==-2);real_calls++;
    if(denied)return (Result)0xD8E007FD;
    *h=0x123;return 0;
}
Thread __real_threadCreate(ThreadFunc ep,void *arg,size_t stack,int priority,int core,bool detach)
{
    assert(ep && arg==(void*)123 && stack==24576 && !detach);
    Handle handle=0;Result rc=__wrap_svcCreateThread(&handle,ep,(uintptr_t)arg,(u32*)0x888,priority,core);
    return R_FAILED(rc)?NULL:&mock_thread;
}
Thread threadCreate(ThreadFunc ep,void *arg,size_t stack,int priority,int core,bool detach)
{ return __wrap_threadCreate(ep,arg,stack,priority,core,detach); }
void __real_Gfx_FlashlightUpdate(void) { light_calls++;ticks+=77; }
static void entry(void *arg) { assert(arg==(void*)123); }
static void read_report(char *buffer,size_t size)
{
    FILE *out=tmpfile();assert(out);game_cpu_audit_report(out);rewind(out);
    size_t n=fread(buffer,1,size-1,out);buffer[n]=0;assert(feof(out));fclose(out);
}
static void *writer(void *arg)
{
    (void)arg;processor=2;
    for(unsigned i=0;i<50000;i++) {
        ticks=1;uint64_t t=game_cpu_audit_begin(GCPU_XA);
        ticks=101;game_cpu_audit_end(GCPU_XA_STEP,t);
    }
    atomic_store(&writer_done,1);return NULL;
}
int main(void)
{
    assert(!game_cpu_audit_begin(GCPU_MAIN) && !clock_calls);
    Thread t=threadCreate(entry,(void*)123,24576,0x2f,-2,false);
    assert(t && real_calls==1 && attempts==1);
    assert(created[0].entry==(uint32_t)(uintptr_t)entry && created[0].stack==24576);
    assert(created[0].priority==0x2f && created[0].core==-2 && created[0].id==12);
    denied=1;
    assert(!threadCreate(entry,(void*)123,24576,0x2f,-2,false));
    assert(created[1].result==(Result)0xD8E007FD && !created[1].handle);
    /* No marker in a host test: init must never create a probe by itself. */
    ticks=1;game_cpu_audit_init(1);assert(attempts==2 && !probe_requested && !budget);
    assert(!core_reader && !observed[GCPU_MAIN].cores);
    core_reader=1;game_cpu_audit_enter(GCPU_MAIN); /* explicit host-only reader */
    for(unsigned i=0;i<9;i++) {
        ticks=1;uint64_t start=game_cpu_audit_begin(GCPU_SPU);
        ticks=500000001;game_cpu_audit_end(GCPU_SPU_BLOCK,start);
    }
    assert(timing[GCPU_SPU_BLOCK].high==1);
    assert((((uint64_t)timing[0].high<<32)|timing[0].low)==4500000000ull);
    __wrap_Gfx_FlashlightUpdate();assert(light_calls==1 && timing[GCPU_FLASHLIGHT_SETUP].low==77);
    pending=1;probes[2].thread=t;game_cpu_audit_poll();assert(!freed && probes[2].thread==t);
    pending=0;game_cpu_audit_poll();assert(freed==1 && !probes[2].thread);
    char report[16384];read_report(report,sizeof(report));
    assert(strstr(report,"cpu_scheduled_thread_ticks=UNAVAILABLE_STANDARD_3DS_SVC\n"));
    assert(strstr(report,"cpu_core_idle_ticks=UNAVAILABLE_STANDARD_3DS_SVC\n"));
    assert(strstr(report,"cpu_budget_policy=UNCHANGED\n"));
    assert(strstr(report,"cpu_affinity_query=UNAVAILABLE_RETAIL_STUB\n"));
    pthread_t w;assert(!pthread_create(&w,NULL,writer,NULL));
    unsigned snapshots=0;
    do {
        read_report(report,sizeof(report));
        if(strstr(report,"cpu_scope_xa_step_valid=1\n")) {
            unsigned calls,peak;double ms;
            assert(sscanf(strstr(report,"cpu_scope_xa_step="),"cpu_scope_xa_step=%u,%lf,%u",&calls,&ms,&peak)==3);
            assert(fabs(ms-calls*100000.0/SYSCLOCK_ARM11)<0.000051);
            snapshots++;
        }
    } while(!atomic_load(&writer_done));
    assert(!pthread_join(w,NULL));assert(snapshots);
    assert(timing[GCPU_XA_STEP].calls==50000 && timing[GCPU_XA_STEP].low==5000000);
    assert(observed[GCPU_XA].cores==4 && observed[GCPU_MAIN].cores==1);
    __atomic_store_n(&detailed_enabled,0,__ATOMIC_RELEASE);
    unsigned clocks=clock_calls;assert(!game_cpu_audit_begin(GCPU_MAIN));game_cpu_audit_poll();assert(clock_calls==clocks);
    puts("PASS: unchanged thread arguments/results, denied-core errors, no unsolicited probes, unknown affinity, 64-bit carry, concurrent snapshots, bounded probe cleanup, disabled clock overhead");
}
