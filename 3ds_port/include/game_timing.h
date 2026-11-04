#ifndef SH_GAME_TIMING_H
#define SH_GAME_TIMING_H
#include <stdint.h>
/* Adapted from MainLoop's PC cumulative-Q12 clock and bounded cutscene debt.
 * Retain Stage 7's 15 Hz maximum step (273), including 24 Hz Cybil shots.
 * The PC desktop's tighter 136 cap discards time whenever 3DS falls below 30.
 * Both 30/60 modes use the same wall clock; pause is excluded at the source. */
typedef struct {uint32_t previous;int debt,started;} GameTiming;
static inline void game_timing_step(GameTiming *clock,uint32_t now,int scene,
    int fallback,int *dt,int *raw)
{
    uint32_t elapsed=clock->started ? now-clock->previous : (uint32_t)fallback;
    clock->started=1;clock->previous=now;
    int actual=elapsed>8192?8192:(int)elapsed;
    *raw=actual>273?273:actual;
    *dt=*raw;
    if(scene) {
        clock->debt+=actual-*dt;
        if(clock->debt>8192)clock->debt=8192;
        int pay=273-*dt;if(pay>clock->debt)pay=clock->debt;
        *dt+=pay;clock->debt-=pay;*raw=*dt;
    } else clock->debt=0;
}
#endif
