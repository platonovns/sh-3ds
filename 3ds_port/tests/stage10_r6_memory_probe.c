/* Development-only link wrappers. The allocator and allocation lifetimes are
 * unchanged; live SDK allocations are recorded in ordinary BSS, never linear. */
#include <3ds.h>
#include <stdint.h>
#include <stdio.h>
void *__real_linearAlloc(size_t size);
void *__real_linearMemAlign(size_t size,size_t alignment);
void __real_linearFree(void *ptr);
typedef struct {void *ptr;size_t requested,actual;uintptr_t caller;} Record;
static Record records[256];
static unsigned allocations,frees,overflow,live,peak_live;
static size_t live_bytes,peak_bytes;
static unsigned min_free=~0u,samples;
static void remember(void *ptr,size_t size,uintptr_t caller)
{
    if(!ptr)return;
    unsigned slot=256;
    for(unsigned i=0;i<256;i++) {
        if(records[i].ptr==ptr) {records[i].caller=caller;return;}
        if(!records[i].ptr && slot==256)slot=i;
    }
    if(slot==256){overflow++;return;}
    size_t actual=linearGetSize(ptr);
    records[slot]=(Record){ptr,size,actual,caller};allocations++;live++;live_bytes+=actual;
    if(live>peak_live)peak_live=live;
    if(live_bytes>peak_bytes)peak_bytes=live_bytes;
}
void *__wrap_linearAlloc(size_t size)
{void *p=__real_linearAlloc(size);remember(p,size,(uintptr_t)__builtin_return_address(0));return p;}
void *__wrap_linearMemAlign(size_t size,size_t alignment)
{void *p=__real_linearMemAlign(size,alignment);remember(p,size,(uintptr_t)__builtin_return_address(0));return p;}
void __wrap_linearFree(void *ptr)
{
    for(unsigned i=0;ptr && i<256;i++)if(records[i].ptr==ptr) {
        live_bytes-=records[i].actual;records[i].ptr=NULL;frees++;live--;break;
    }
    __real_linearFree(ptr);
}
void Game3ds_DevMemorySample(void)
{unsigned space=linearSpaceFree();if(space<min_free)min_free=space;samples++;}
void Game3ds_DevMemoryReport(FILE *out)
{
    Game3ds_DevMemorySample();
    fprintf(out,"r6_linear_live=%u\nr6_linear_peak_live=%u\nr6_linear_live_bytes=%u\nr6_linear_peak_bytes=%u\nr6_linear_allocations=%u\nr6_linear_frees=%u\nr6_linear_overflow=%u\nr6_linear_min_free=%u\nr6_linear_samples=%u\n",
        live,peak_live,(unsigned)live_bytes,(unsigned)peak_bytes,allocations,frees,overflow,min_free,samples);
    unsigned slot=0;
    for(unsigned i=0;i<256;i++)if(records[i].ptr)
        fprintf(out,"r6_linear_allocation_%u=%08lx,%u,%u\n",slot++,(unsigned long)records[i].caller,(unsigned)records[i].requested,(unsigned)records[i].actual);
}
