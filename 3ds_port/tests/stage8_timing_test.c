#include "game_timing.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    const unsigned rates[]={15,24,30,45,60};
    for(unsigned rate=0;rate<sizeof(rates)/sizeof(rates[0]);rate++) {
        unsigned hz=rates[rate];
        GameTiming c={0,0,1};int dt,raw;unsigned sum=0;
        for(unsigned i=1;i<=hz*60;i++) {
            game_timing_step(&c,i*4096/hz,0,0,&dt,&raw);
            assert(dt>0 && dt<=273);sum+=dt;
        }
        /* A sub-60 scene must keep the same rate of simulation time. */
        assert(sum<=60*4096 && sum>=60*4095);
    }
    GameTiming c={0,0,1};int dt,raw;
    game_timing_step(&c,4096,0,0,&dt,&raw);assert(dt==273 && raw==273 && !c.debt);
    game_timing_step(&c,8192,1,0,&dt,&raw);assert(dt==273 && raw==273 && c.debt>0);
    for(unsigned i=1;i<200;i++) {
        game_timing_step(&c,8192+i*68,1,0,&dt,&raw);assert(dt<=273 && raw==dt && c.debt<=8192);
    }
    game_timing_step(&c,c.previous,0,0,&dt,&raw);assert(!dt && !raw && !c.debt);
    c.previous=0xfffffff0u;c.started=1;
    game_timing_step(&c,52,0,0,&dt,&raw);assert(dt==68 && raw==68);
    puts("Stage 8 cumulative Q12, 30/60 pacing input, hitch cap, scene debt and wrap PASS");
}
