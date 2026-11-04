#ifndef SH_GAME_MAP_COLOR_H
#define SH_GAME_MAP_COLOR_H
#include <stdint.h>
/* Map image only. Markers and HUD are composed later. */
static inline uint16_t game_map_image_color(uint16_t pixel,unsigned brightness,unsigned invert)
{
    unsigned p=pixel^(invert?0xffffu:0u),v=brightness;
    return (uint16_t)((((p>>11)*v/10)<<11)|((((p>>5)&63)*v/10)<<5)|((p&31)*v/10));
}
/* Convert a cached RGB565 image in one pass. A 100% invert is an XOR;
 * other levels use tiny lookup tables instead of three divisions per pixel. */
static inline void game_map_convert(uint16_t *pixels,unsigned count,unsigned brightness,unsigned invert)
{
    if(brightness==10) {
        if(invert)for(unsigned i=0;i<count;i++)pixels[i]^=0xffffu;
        return;
    }
    uint16_t red[32],green[64],blue[32];
    for(unsigned i=0;i<32;i++) {red[i]=(uint16_t)((i*brightness/10)<<11);blue[i]=(uint16_t)(i*brightness/10);}
    for(unsigned i=0;i<64;i++)green[i]=(uint16_t)((i*brightness/10)<<5);
    for(unsigned i=0;i<count;i++) {
        unsigned p=pixels[i]^(invert?0xffffu:0u);
        pixels[i]=(uint16_t)(red[p>>11]|green[(p>>5)&63]|blue[p&31]);
    }
}
#endif
