#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../source/stage11a_lifetime.c"
#include "../source/game_cpu_recorder.c"
static uint64_t test_ticks=1000000;
static unsigned fake_voices=6,audit_on=1;
uint64_t svcGetSystemTick(void){test_ticks+=10;return test_ticks;}
uint64_t game3ds_ticks(void){return svcGetSystemTick();}
uint32_t svcGetProcessInfo(s64 *out,unsigned handle,unsigned type){assert(handle==1 && type==7);*out=6;return 0;}
uint32_t envGetHeapSize(void){return 32*1024*1024;}
uint32_t envGetLinearHeapSize(void){return 64*1024*1024;}
uint32_t linearSpaceFree(void){return 50*1024*1024;}
uint32_t vramSpaceFree(void){return 3*1024*1024;}
void stage11a_lifetime_render(Stage11aLifetime *out){out->render[2]=60;}
void stage11a_lifetime_cache(uint32_t out[LT_CACHE_WORDS]){out[0]=7;}
void stage11a_lifetime_spu(uint32_t out[LT_SPU_WORDS],uint32_t voices[24][LT_VOICE_WORDS]){out[8]=fake_voices;voices[0][0]=0x1000;}
void stage11a_lifetime_xa(uint32_t out[LT_XA_WORDS]){out[4]=16384;}
void stage11a_lifetime_audio(uint32_t out[LT_AUDIO_WORDS]){out[12]=4;}
void stage11a_lifetime_resource(uint32_t out[LT_RESOURCE_WORDS]){out[0]=1;out[1]=2;}
void game_cpu_audit_lifetime_toggle(unsigned on){audit_on=on;}
void game_cpu_audit_snapshot(CpuRecordSnapshot *out){memset(out,0,sizeof(*out));out->valid=63;}
void game_cpu_audit_report(FILE *out){fputs("cpu_test=1\n",out);}
void stage11a_audio_boundary(unsigned on){(void)on;}
void stage11a_renderer_boundary(unsigned on){(void)on;}
void stage11a_audio_report(FILE *out){(void)out;}
void stage11a_renderer_report(FILE *out){(void)out;}
static void chord(CpuRecordContext *c,unsigned key)
{
    assert(cpu_recorder_input(SELECT_BIT,c)==0);
    assert(cpu_recorder_input(SELECT_BIT|key,c)==0);
    assert(cpu_recorder_input(key,c)==0); /* release Select first cannot move Harry */
    assert(cpu_recorder_input(0,c)==0);
}
int main(int argc,char **argv)
{
    assert(argc==2);CpuRecordContext c={.game=11,.map=3,.room=23,.flashlight=1,.fps_mode=30};
    cpu_recorder_init(argv[1],"stage11a.0-lifetime-test");game_prof_enable(16);
    stage11a_lifetime_poll(&c);assert(have_first && used==1 && first.spu[8]==6);
    uint64_t initial_origin=origin;stage11a_lifetime_init();assert(origin==initial_origin);
    stage11a_lifetime_alloc(0,100,0);assert(allocations[0][0]==1 && allocations[0][3]==100);
    chord(&c,DOWN_BIT);assert(active);
    chord(&c,RIGHT_BIT);assert(stage11a_lifetime_mode()==1); /* no toggle inside a window */
    test_ticks+=268123480ull*30;c.lcd_frames+=900;
    chord(&c,DOWN_BIT);assert(!active && last_saved==1);
    assert(boundary[0].spu[8]==6 && boundary[1].spu[8]==6);
    for(unsigned i=0;i<100;i++){test_ticks+=11ull*268123480;fake_voices=24;stage11a_lifetime_poll(&c);}
    assert(used==LT_HISTORY && first.spu[8]==6 && history[(head+LT_HISTORY-1)%LT_HISTORY].spu[8]==24);
    c.game=7;stage11a_lifetime_poll(&c);assert(history[(head+LT_HISTORY-1)%LT_HISTORY].spu[8]==24);
    chord(&c,RIGHT_BIT);assert(!stage11a_lifetime_mode() && !audit_on && !game_prof_enabled);
    char label[64];assert(cpu_recorder_label(label,sizeof(label)) && strstr(label,"P0"));
    chord(&c,DOWN_BIT);test_ticks+=20ull*268123480;c.lcd_frames+=600;chord(&c,DOWN_BIT);
    assert(last_saved==2 && boundary[0].mode==0 && boundary[1].mode==0);
    chord(&c,RIGHT_BIT);assert(stage11a_lifetime_mode() && audit_on && game_prof_enabled);
    assert(!game_prof_gte_sample);
    puts("PASS: bounded lifetime ring, preserved cold snapshot, Title does not reset observed state, P1/P0 chord debounce, forbidden in-window toggle, recording while profiling OFF, allocator counters");
}
