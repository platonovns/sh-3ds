#ifndef SH_GAME_MODERN_CONTROLS_H
#define SH_GAME_MODERN_CONTROLS_H
#include <stdint.h>
/* Movement intent consumed by the native player-state hook. C-stick bits
 * never enter this vector. A physical D-pad direction owns the whole vector. */
enum GameControlMode {GAME_CONTROL_TANK,GAME_CONTROL_MODERN,GAME_CONTROL_HYBRID};
static inline int game_control_vector(unsigned mode,uint32_t keys,int circle_x,int circle_y,int *x,int *z)
{
    *x=*z=0;
    if(mode==GAME_CONTROL_TANK || mode>GAME_CONTROL_HYBRID)return 0;
    if(keys&0xf0) {
        if(mode==GAME_CONTROL_HYBRID)return 0;
        *x=(int)((keys>>4)&1)-(int)((keys>>5)&1);
        *z=(int)((keys>>6)&1)-(int)((keys>>7)&1);
    } else if(circle_x*circle_x+circle_y*circle_y>=30*30) {
        *x=circle_x;*z=circle_y;
    }
    return *x || *z;
}
#endif
