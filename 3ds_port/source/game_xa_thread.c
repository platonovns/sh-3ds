/* SDK ABI only. Disc reads/decoding never run on the NDSP or game thread. */
#include <3ds.h>
#include "game_xa.h"
#include "game_audio.h"
#include "game_profile.h"
#include "game_cpu_audit.h"
static LightLock xa_lock;
static Thread xa_worker;
static uint32_t xa_running;
static uint32_t xa_created,xa_wakes;
static uint32_t xa_max_step_us,xa_max_active_gap_us;
void game_xa_lock(void) { LightLock_Lock(&xa_lock); }
void game_xa_unlock(void) { LightLock_Unlock(&xa_lock); }
static void worker(void *unused)
{
    (void)unused;
    game_cpu_audit_enter(GCPU_XA);
    uint64_t previous_active=0;
    while(__atomic_load_n(&xa_running,__ATOMIC_ACQUIRE)) {
        if(game_audio_lifecycle_paused()) {svcSleepThread(2000000);continue;}
        uint64_t audit=game_cpu_audit_begin(GCPU_XA);
        uint64_t begin=svcGetSystemTick();
        uint32_t active=game_xa_is_active();
        if(active && previous_active) {
            uint32_t us=(uint32_t)((begin-previous_active)*1000000/SYSCLOCK_ARM11);
            if(us>xa_max_active_gap_us)__atomic_store_n(&xa_max_active_gap_us,us,__ATOMIC_RELAXED);
        }
        previous_active=active?begin:0;
        __atomic_fetch_add(&xa_wakes,1,__ATOMIC_RELAXED);
        game_xa_step();
        if(active && game_prof_enabled)game_prof_audio_add(GP_XA_WORKER,svcGetSystemTick()-begin);
        if(active) {
            uint32_t us=(uint32_t)((svcGetSystemTick()-begin)*1000000/SYSCLOCK_ARM11);
            if(us>xa_max_step_us)__atomic_store_n(&xa_max_step_us,us,__ATOMIC_RELAXED);
        }
        game_cpu_audit_end(GCPU_XA_STEP,audit);
        uint64_t wait=game_cpu_audit_begin(GCPU_XA);
        svcSleepThread(2000000); /* bounded batches, including malformed streams */
        game_cpu_audit_end(GCPU_XA_WAIT,wait);
    }
}
int32_t game_xa_thread_init(void)
{
    LightLock_Init(&xa_lock);
    xa_running=1;
    xa_worker=threadCreate(worker,NULL,24*1024,0x2f,-2,false);
    if(!xa_worker){xa_running=0;return -1;}
    xa_created=1;
    return 0;
}
void game_xa_thread_shutdown(void)
{
    __atomic_store_n(&xa_running,0,__ATOMIC_RELEASE);
    if(xa_worker){threadJoin(xa_worker,UINT64_MAX);threadFree(xa_worker);xa_worker=NULL;}
    game_xa_cancel(XA_CANCEL_SHUTDOWN,0,0);game_xa_close();
}
void game_xa_thread_report(FILE *out)
{
    fprintf(out,"xa_worker_created=%lu\nxa_worker_running=%lu\nxa_worker_wakes=%lu\n",
        (unsigned long)xa_created,(unsigned long)__atomic_load_n(&xa_running,__ATOMIC_ACQUIRE),
        (unsigned long)__atomic_load_n(&xa_wakes,__ATOMIC_RELAXED));
    fprintf(out,"xa_worker_max_step_us=%lu\nxa_worker_max_active_gap_us=%lu\n",
        (unsigned long)__atomic_load_n(&xa_max_step_us,__ATOMIC_RELAXED),
        (unsigned long)__atomic_load_n(&xa_max_active_gap_us,__ATOMIC_RELAXED));
}
