#ifndef SH_ORIENTATION_PATTERN_H
#define SH_ORIENTATION_PATTERN_H
#include <stdint.h>
#define ORIENTATION_EDGE 32u
/* Synthetic only. Four colored corners, readable TL/TR/BL/BR, a right arrow,
 * and unequal edge notches distinguish every square rotation/reflection. */
static inline void orientation_pattern_pixel(unsigned x, unsigned y, uint8_t out[4])
{
    static const uint8_t colors[4][3] = {{220,32,32},{24,180,48},{32,64,220},{240,208,24}};
    unsigned corner = (x >= 16) + 2 * (y >= 16);
    out[0] = colors[corner][0]; out[1] = colors[corner][1]; out[2] = colors[corner][2]; out[3] = 255;
    /* 3x5 T,L,B,R. Row bits run left to right, most significant first. */
    static const uint8_t glyph[4][5] = {{7,2,2,2,2},{4,4,4,4,7},{6,5,6,5,6},{6,5,6,5,5}};
    unsigned lx = x % 16, ly = y % 16;
    int mark = 0;
    if (ly >= 4 && ly < 9) {
        if (lx >= 3 && lx < 6) mark = !!(glyph[y < 16 ? 0 : 2][ly-4] & (4u >> (lx-3)));
        if (lx >= 8 && lx < 11) mark |= !!(glyph[x < 16 ? 1 : 3][ly-4] & (4u >> (lx-8)));
    }
    if ((y == 15 && x >= 5 && x <= 25) ||
        (x >= 22 && x <= 25 && (y == x - 10 || y == 40 - x))) mark = 1;
    if ((x == 0 && y < 3) || (y == 31 && x >= 28)) mark = 1;
    if (mark) out[0] = out[1] = out[2] = 255;
    /* Single black origin notch, deliberately unlike the opposite edge. */
    if (x == 1 && y == 1) out[0] = out[1] = out[2] = 0;
}
#endif
