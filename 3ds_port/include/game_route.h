#ifndef SH_GAME_ROUTE_H
#define SH_GAME_ROUTE_H
#include <stdint.h>
#include <math.h>
/* Diagnostic only. Observe pose, emit normal pad bits; never mutate game state.
 * Alley center x=-62 is from original map0_s00 Cheryl/camera events. */
static inline uint32_t game_route_pad(int32_t x,int32_t z,int32_t yaw,unsigned *leg,unsigned *laps)
{
    static const int points[][2]={{-6,135},{-30,135},{-62,127},{-62,117},{-62,62},{-62,92}};
    /* The original spotted-Cheryl scene moves Harry past the street approach. */
    if(*leg<2 && x< -20*4096 && z<132*4096)*leg=2;
    int32_t dx=points[*leg][0]*4096-x,dz=points[*leg][1]*4096-z;
    if((int64_t)dx*dx+(int64_t)dz*dz<(int64_t)6144*6144) {
        if(++*leg==6){*leg=4;(*laps)++;}return 0;
    }
    int target=(int)(atan2f((float)dx,(float)dz)*651.898647f);
    int delta=((target-(yaw&4095)+2048)&4095)-2048;
    if(delta>48)return 1u<<4;
    if(delta< -48)return 1u<<5;
    return (1u<<6)|(1u<<11); /* Up + Square/run via original Joy */
}
#endif
