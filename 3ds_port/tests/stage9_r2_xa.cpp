/* Host transport/codec integration; reads the user's BIN without extracting it. */
#include "game_xa.h"
#include "PsyX_XAStream.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <vector>
#include <thread>
#include <atomic>
static std::mutex lock;
extern "C" void game_xa_lock(void){lock.lock();}
extern "C" void game_xa_unlock(void){lock.unlock();}
extern "C" FILE *xa_test_fopen(const char *,const char *mode){return fopen(getenv("SH_XA_BIN"),mode);}
struct Item {unsigned id,lba,ticks,file,channel;};
static uint64_t hash(const int16_t *p,unsigned frames,uint64_t h)
{for(unsigned i=0;i<frames*2;i++){h^=static_cast<uint16_t>(p[i]);h*=1099511628211ull;}return h;}
static uint64_t play(const Item &a,unsigned game_fps)
{
    game_xa_start(a.lba,a.file,a.channel,a.ticks);
    for(int i=0;i<6;i++)game_xa_step();
    unsigned played=0,rendered=0,query=0;
    uint64_t h=1469598103934665603ull;
    int16_t pcm[1024];
    while(game_xa_elapsed60()<=a.ticks+32) {
        game_xa_step();
        unsigned n=game_xa_pull(pcm,512);
        h=hash(pcm,n,h);played+=n;rendered+=512;
        if(rendered>=query){assert(game_xa_status()==0x22 || game_xa_status()==2);query+=44100/game_fps;}
        assert(rendered<(a.ticks+40)*735);
    }
    /* Authored integer vblank lengths may round past the final EOF sector.
     * Never read the following line to manufacture those final samples. */
    assert(played<=a.ticks*735 && played+2352>=a.ticks*735);
    game_xa_stop();assert(game_xa_pull(pcm,512)==0);
    return h;
}
int main(int argc,char **argv)
{
    assert(argc==2);
    FILE *f=fopen(argv[1],"r");assert(f);
    std::vector<Item> items;Item a;
    while(fscanf(f,"%u %u %u %u %u",&a.id,&a.lba,&a.ticks,&a.file,&a.channel)==5)items.push_back(a);
    fclose(f);assert(items.size()==726);
    FILE *bin=fopen(getenv("SH_XA_BIN"),"rb");assert(bin);
    unsigned checked=0;
    for(const auto &item:items) {
        uint8_t raw[2352];assert(!fseek(bin,static_cast<long>(item.lba)*2352,SEEK_SET));
        assert(fread(raw,1,sizeof(raw),bin)==sizeof(raw));
        assert(raw[15]==2 && !memcmp(raw+16,raw+20,4));
        assert(raw[16]==item.file && raw[17]==item.channel && (raw[18]&0x64)==0x64);
        assert(raw[19]==1); /* Verify disc reality, do not assume it in transport. */
        int32_t history[2][2]={};int16_t pcm[4032];
        assert(game_xa_decode(raw+16,pcm,history)==4032);++checked;
    }
    fclose(bin);
    printf("PASS: %u original XA requests match raw Form2/filter/coding headers\n",checked);
    /* Compare matrix output against the same decoded/resampled disc sector,
     * using signed wide reference arithmetic. Equality between channels or
     * repeatable hashes alone cannot detect negative half-wave destruction. */
    {
        const auto &voice=items[12];assert(voice.id==13);
        FILE *disc=fopen(getenv("SH_XA_BIN"),"rb");assert(disc);
        uint8_t raw[2352];assert(!fseek(disc,static_cast<long>(voice.lba)*2352,SEEK_SET));
        assert(fread(raw,1,sizeof(raw),disc)==sizeof(raw));fclose(disc);
        int32_t history[2][2]={};int16_t decoded[4032],reference[4704],actual[4704];
        assert(game_xa_decode(raw+16,decoded,history)==4032);
        auto stream=PsyX_XAStream_Create();PsyX_XAStream_Reset(stream);
        assert(PsyX_XAStream_Push(stream,decoded,2016,37800,2));
        assert(PsyX_XAStream_Pop44100Stereo(stream,reference,2352)==2352);
        PsyX_XAStream_Destroy(stream);
        unsigned negative=0,positive=0;
        for(auto v:reference){negative+=v<0;positive+=v>0;}
        assert(negative && positive);
        const unsigned gains[][4]={{128,0,128,0},{127,0,127,0},{0,128,0,128},
                                  {79,79,79,79},{255,255,255,255},{0,0,0,0}};
        for(const auto &gain:gains) {
            game_xa_mix(gain[0],gain[1],gain[2],gain[3]);
            game_xa_start(voice.lba,voice.file,voice.channel,voice.ticks);game_xa_step();
            assert(!game_xa_pull(actual,512)); // No playback before the bounded reserve.
            assert(!game_xa_ready());game_xa_step();
            assert(game_xa_pull(actual,2352)==2352);
            for(unsigned i=0;i<2352;i++)for(unsigned ch=0;ch<2;ch++) {
                int64_t value=(static_cast<int64_t>(reference[i*2])*gain[ch]+
                    static_cast<int64_t>(reference[i*2+1])*gain[ch?2:3])>>7;
                value=value>32767?32767:(value< -32768?-32768:value);
                assert(actual[i*2+ch]==value);
            }
            game_xa_stop();
        }
        game_xa_mix(127,0,127,0);
        puts("PASS: signed CD matrix matches independent reference for both polarities and six gain/routing cases");
    }
    for(unsigned i=0;i<37;i++) {
        auto h30=play(items[i],30),h60=play(items[i],60),h12=play(items[i],12);
        assert(h30==h60 && h30==h12);
        printf("line %u frames=%u pcm=%016llx identical at 30/60/12 FPS\n",items[i].id,items[i].ticks*735,(unsigned long long)h30);
    }
    a=items[0];game_xa_start(a.lba,a.file,a.channel,a.ticks);assert(game_xa_draining());game_xa_step();
    assert(!game_xa_ready()); /* Decoding/enqueue alone is not audible readiness. */
    int16_t pcm[1024];assert(!game_xa_pull(pcm,512));
    assert(game_xa_elapsed60()==0);game_xa_step();assert(game_xa_pull(pcm,512)==512);
    assert(game_xa_ready());
    auto elapsed=game_xa_elapsed60();game_xa_pause(1);
    for(int i=0;i<20;i++){assert(!game_xa_pull(pcm,512));assert(!game_xa_step());}
    assert(game_xa_elapsed60()==elapsed);game_xa_pause(0);assert(game_xa_pull(pcm,512)==512);
    game_xa_stop();assert(!game_xa_pull(pcm,512));assert(!game_xa_ready());assert(!game_xa_draining());
    /* Malformed/wrong filter must terminate with an error and release watchdog. */
    game_xa_start(a.lba,255,255,a.ticks);
    for(int i=0;i<9;i++)game_xa_step();
    assert(game_xa_status()==3 && game_xa_elapsed60()>a.ticks+32 && !game_xa_draining());
    assert(play(items[1],30));
    /* Matrix: mono sums both inputs; original stereo preserves each side. */
    game_xa_mix(79,79,79,79);
    game_xa_start(a.lba,a.file,a.channel,a.ticks);game_xa_step();
    game_xa_step();
    assert(game_xa_pull(pcm,512)==512);for(int i=0;i<512;i++)assert(pcm[i*2]==pcm[i*2+1]);
    game_xa_mix(127,0,127,0);
    /* Concurrent start/stop while reads/decode are in flight: stale epochs
     * cannot refill the ring after stop or replace the subsequent line. */
    std::atomic<bool> running{true};
    std::thread producer([&]{while(running)game_xa_step();});
    for(int i=0;i<100;i++) {
        game_xa_start(a.lba,a.file,a.channel,a.ticks);
        game_xa_pull(pcm,512);game_xa_stop();assert(!game_xa_pull(pcm,512));
    }
    running=false;producer.join();
    assert(play(items[2],60));
    game_xa_disable_output();game_xa_start(a.lba,a.file,a.channel,a.ticks);
    assert(game_xa_status()==3 && game_xa_elapsed60()>a.ticks+32 && !game_xa_step());
    game_xa_report(stdout);game_xa_close();
    puts("PASS: bounded streaming, exact timing, pause/resume, matrix, cancel, bad filter, concurrent seek/stop");
}
