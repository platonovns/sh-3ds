/* Deterministic IO-latency model around the actual transport and PCM pull.
 * Mixer deadlines continue during fread; no producer prefill between renders.
 * This reproduces scheduling pressure, not SD hardware or DSP firmware. */
#include "game_xa.h"
#include <vector>
#include <mutex>
#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <algorithm>
static std::mutex lock;
static uint64_t now,deadline=33333333,read_calls,read_bytes,played,missing,longest,gap,first,last;
static uint64_t first_missing,startup,blocks,steps;
static uint64_t pcm_hash=1469598103934665603ull;
static constexpr uint64_t Expected=129360;
static uint64_t latency,bandwidth,jitter;
static unsigned jitter_phase;
static std::vector<int16_t> audio;
extern "C" void game_xa_lock(){lock.lock();}
extern "C" void game_xa_unlock(){lock.unlock();}
extern "C" FILE *xa_test_fopen(const char *,const char *mode){return fopen(getenv("SH_XA_BIN"),mode);}
static void advance(uint64_t duration)
{
    uint64_t end=now+duration;
    while(deadline<=end && played<Expected) {
        int16_t pcm[1024]={};uint32_t n=game_xa_pull(pcm,512);++blocks;
        bool started=played!=0;
        if(n && !started)first=deadline;
        if(n)gap=0;
        played+=n;
        uint32_t lost=played<Expected?512-n:0;
        for(unsigned i=0;i<n*2;i++){pcm_hash^=static_cast<uint16_t>(pcm[i]);pcm_hash*=1099511628211ull;}
        if(lost) {
            if(started || n) {
                if(!missing)first_missing=deadline;
                missing+=lost;gap+=lost;longest=std::max(longest,gap);
            } else startup+=lost;
        }
        if(n || started)audio.insert(audio.end(),pcm,pcm+(played==Expected?n:512)*2);
        if(n)last=deadline+n*1000000000ull/44100;
        deadline=33333333+(++steps)*512*1000000000ull/44100;
    }
    now=end;
}
extern "C" size_t __real_fread(void *,size_t,size_t,FILE *);
extern "C" size_t __wrap_fread(void *out,size_t size,size_t count,FILE *f)
{
    ++read_calls;read_bytes+=size*count;
    advance(latency+size*count*1000000000ull/bandwidth);
    return __real_fread(out,size,count,f);
}
extern "C" size_t __wrap___fread_chk(void *out,size_t capacity,size_t size,size_t count,FILE *f)
{assert(!size || count<=capacity/size);return __wrap_fread(out,size,count,f);}
int main(int argc,char **argv)
{
    assert(argc==6 || argc==7);latency=strtoull(argv[1],nullptr,10)*1000000ull;
    bandwidth=strtoull(argv[2],nullptr,10);jitter=strtoull(argv[3],nullptr,10)*1000000ull;
    jitter_phase=argc==7?atoi(argv[6]):0;
    game_xa_start(39978,2,3,177);
    unsigned wakes=0;
    while(played<Expected && now<30000000000ull) {
        // Same one-sector worker as R4; optional bounded burst is a test arg.
        for(int i=0;i<atoi(argv[5]);i++){if(!game_xa_step())break;advance(300000);}
        advance(2000000+(jitter && ++wakes%23==jitter_phase?jitter:0));
    }
    assert(played==Expected);
    FILE *f=fopen(argv[4],"wb");assert(f);
    fwrite(audio.data(),2,audio.size(),f);fclose(f);
    printf("{\"expected_output_frames\":129360,\"supplied\":%llu,\"missing\":%llu,\"startup_wait_frames\":%llu,\"longest_gap_frames\":%llu,\"read_calls\":%llu,\"read_bytes\":%llu,\"duration_seconds\":%.9f,\"first_missing_ms\":%.6f,\"blocks\":%llu,\"supplied_pcm_hash\":\"%016llx\"}\n",
        (unsigned long long)played,(unsigned long long)missing,(unsigned long long)startup,(unsigned long long)longest,
        (unsigned long long)read_calls,(unsigned long long)read_bytes,(last-first)/1e9,first_missing/1e6,(unsigned long long)blocks,(unsigned long long)pcm_hash);
    game_xa_stop();game_xa_close();
}
