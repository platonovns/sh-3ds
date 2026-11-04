#include <assert.h>
#define SH_CPU_AUDIT_RECORDER 1
#include "../source/game_cpu_audit.c"
static uint64_t now;
uint64_t svcGetSystemTick(void) {return now;}
int main(void)
{
    CpuRecordSnapshot a,b;
    game_cpu_audit_snapshot(&a);assert(a.valid==(1u<<GCPU_SCOPES)-1);
    now=0x100000010ull;game_cpu_audit_end(GCPU_RESOLVE,1);
    game_cpu_audit_snapshot(&b);
    assert(b.valid==a.valid && b.ticks[GCPU_RESOLVE]==0x10000000full && b.calls[GCPU_RESOLVE]==1);
    __atomic_store_n(&timing[GCPU_XA_STEP].sequence,1,__ATOMIC_RELEASE);
    game_cpu_audit_snapshot(&a);assert(!(a.valid&(1u<<GCPU_XA_STEP)));
    assert(a.valid&(1u<<GCPU_RESOLVE));
    puts("PASS: real SDK snapshot, split 64-bit carry, call counts and explicit unavailable in-flight snapshot");
}
