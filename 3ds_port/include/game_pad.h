#ifndef SH_GAME_PAD_H
#define SH_GAME_PAD_H
#include <stdint.h>
/* libctru HID bits -> original PSX digital pad bits. Circle Pad is a digital
 * D-pad alternative with libctru's threshold; no camera-relative remapping. */
static inline uint16_t game_pad_buttons(uint32_t keys)
{
    if(keys&0xf0u)keys&=~0xf0000000u; /* D-pad wins over Circle Pad. */
    uint16_t buttons=0;
    if (keys&(1u<<3)) buttons|=1u<<3;
    if (keys&(1u<<2)) buttons|=1u<<0;
    if (keys&((1u<<6)|(1u<<30))) buttons|=1u<<4;
    if (keys&((1u<<4)|(1u<<28))) buttons|=1u<<5;
    if (keys&((1u<<7)|(1u<<31))) buttons|=1u<<6;
    if (keys&((1u<<5)|(1u<<29))) buttons|=1u<<7;
    if (keys&(1u<<14)) buttons|=1u<<8;  /* ZL -> L2/view */
    if (keys&(1u<<15)) buttons|=1u<<9;  /* ZR -> R2/aim */
    if (keys&(1u<<9)) buttons|=1u<<10;
    if (keys&(1u<<8)) buttons|=1u<<11;
    if (keys&(1u<<10)) buttons|=1u<<12;
    if (keys&(1u<<0)) buttons|=1u<<13;
    if (keys&(1u<<1)) buttons|=1u<<14;
    if (keys&(1u<<11)) buttons|=1u<<15;
    return buttons;
}
#endif
