#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include "../source/stage11a_perf.c"
static void *writer(void *unused)
{
    (void)unused;
    for(unsigned i=0;i<100000;i++)stage11a_perf_add(S11_BLOCK,100000000u+i);
    return NULL;
}
int main(void)
{
    stage11a_perf_add(S11_WALL,1000);assert(!metrics[S11_WALL].calls);
    stage11a_perf_start();
    stage11a_perf_add(S11_BLOCK,3112907);stage11a_perf_add(S11_BLOCK,3112908);
    assert(metrics[S11_BLOCK].calls==2 && metrics[S11_BLOCK].misses==1);
    stage11a_perf_add(S11_WALL,((uint64_t)1<<34)+9);
    assert(bins[S11_WALL][255]==1 && metrics[S11_WALL].hi==4);
    stage11a_perf_queue(4);stage11a_perf_stop();
    stage11a_perf_add(S11_BLOCK,1);assert(metrics[S11_BLOCK].calls==2);
    stage11a_perf_start();stage11a_perf_add(S11_BLOCK,5);
    assert(metrics[S11_BLOCK].calls==1 && metrics[S11_BLOCK].max_lo==5 && !metrics[S11_BLOCK].misses);
    FILE *out=tmpfile();assert(out);stage11a_perf_stop();stage11a_perf_report(out);
    rewind(out);char line[8192];unsigned seen=0;
    while(fgets(line,sizeof(line),out)) {
        if(strstr(line,"stage11a_metric_spu_block=1,1,"))seen|=1;
        if(strstr(line,"stage11a_metric_wall=1,0,"))seen|=2; /* stale previous epoch is absent */
        if(strstr(line,"stage11a_queue_depth_after_submit=0,0,0,0,0"))seen|=4;
    }
    assert(seen==7);fclose(out);
    stage11a_perf_start();pthread_t thread;assert(!pthread_create(&thread,NULL,writer,NULL));
    for(unsigned i=0;i<16;i++) {out=tmpfile();assert(out);stage11a_perf_report(out);fclose(out);}
    assert(!pthread_join(thread,NULL));stage11a_perf_stop();
    assert(metrics[S11_BLOCK].calls==100000 && metrics[S11_BLOCK].misses==100000);
    uint64_t sum=((uint64_t)metrics[S11_BLOCK].hi<<32)|metrics[S11_BLOCK].lo;
    assert(sum==100000ull*100000000+99999ull*100000/2);
    puts("PASS: window epochs, overflow, 64-bit carry, exact max, deadline counts and concurrent snapshots");
}
