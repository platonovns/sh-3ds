#ifndef SH_PSX_GAME_PIXEL_H
#define SH_PSX_GAME_PIXEL_H
#include "psx_vram.h"
#include <string.h>
/* Game-specific PICA representation. The canonical VRAM word is unchanged. */
static inline void psx_game_pixel(uint16_t word, uint8_t rgba[4])
{
    unsigned r=word&31,g=(word>>5)&31,b=(word>>10)&31;
    rgba[0]=(r<<3)|(r>>2);rgba[1]=(g<<3)|(g>>2);rgba[2]=(b<<3)|(b>>2);
    /* Three coverage classes, independent of vertex alpha/ABR: zero discards,
     * STP blends only for semi-transparent commands, other words overwrite. */
    rgba[3]=!word?0:(word&0x8000)?128:255;
}
#endif
