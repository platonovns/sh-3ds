#include "game_profile.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t ticks;
static unsigned clock_calls;
uint64_t game3ds_ticks(void) { clock_calls++;return ticks; }
int main(void)
{
    game_prof_frame();assert(!clock_calls);
    game_prof_enable(16);game_prof_frame();
    for(unsigned i=0;i<120;i++) {
        game_prof_context(11,0,1,2,3,1190,1000+i);
        game_prof_scene(1,0,1,1);
        game_prof_add(GP_UPDATE,300000);game_prof_add(GP_VBLANK,200000);
        game_prof_audio_add(GP_SPU,100000);
        if(game_prof_gte_sample)game_prof_add(GP_GTE,100000);
        game_prof_count(GC_GTE,2000);ticks+=1000000;game_prof_frame();
    }
    for(unsigned i=0;i<9;i++) {
        game_prof_scene(0,0,0,0);
        game_prof_context(11,0,1,2,3,2043,5000+i);
        game_prof_add(GP_REPORT,3000000);ticks+=3100000;game_prof_frame();
    }
    FILE *out=tmpfile();assert(out);game_prof_report(out);rewind(out);
    char report[32768]={0};assert(fread(report,1,sizeof(report)-1,out)>0);fclose(out);
    assert(strstr(report,"profile_frames=120\n"));
    assert(strstr(report,"profile_gte_frames=8\n"));
    assert(strstr(report,"profile_gte_sampled_ms=0.3730\n"));
    assert(strstr(report,"profile_work_ms=2.9837\n"));
    assert(strstr(report,"profile_spu_ms=0.3730\n"));
    assert(strstr(report,"profile_scene_0=1,0,1,1,120,"));
    assert(strstr(report,"profile_gte_ops_per_frame=2000.000\n"));
    assert(strstr(report,"profile_complete=1\n"));
    assert(strstr(report,"profile_slow_rank=WORK_MINUS_VBLANK_AND_REPORT\n"));
    assert(strstr(report,"profile_slow_0=1000,"));assert(!strstr(report,",2043,"));
    game_prof_enabled=0;unsigned before=clock_calls;game_prof_frame();assert(clock_calls==before);
    puts("PASS: disabled clock overhead, sampled GTE normalization, pacing/work separation and bounded report");
}
