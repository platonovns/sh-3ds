#ifndef SH_TEXTURE_LAYOUT_H
#define SH_TEXTURE_LAYOUT_H

#include <stddef.h>
#include <stdint.h>

/* tex3ds-compatible Morton order, top-down source rows, no physical Y flip.
 * PICA Texture2D sampling already uses memory y = H-1-floor(V*H).
 * Therefore source (x,y) maps to U=x/W, V=1-y/H at texel edges.
 * GPU_RGBA8 bytes are A,B,G,R on little-endian ARM. */
static inline size_t texture3ds_offset(unsigned width, unsigned height,
                                       unsigned x, unsigned y)
{
    (void)height;
    const unsigned ty = y;
    unsigned morton = 0;
    for (unsigned bit = 0; bit < 3; ++bit) {
        morton |= ((x >> bit) & 1) << (2 * bit);
        morton |= ((ty >> bit) & 1) << (2 * bit + 1);
    }
    return (((size_t)(ty / 8) * (width / 8) + x / 8) * 64 + morton) * 4;
}

static inline void texture3ds_write_rgba8(uint8_t *dst, const uint8_t *src)
{
    dst[0] = src[3];
    dst[1] = src[2];
    dst[2] = src[1];
    dst[3] = src[0];
}

/* Aligned streaming row. The independent offset function above remains the
 * reference; this factors its repeated Morton work out of the inner loop. */
static inline void texture3ds_write_row(uint32_t *dst,unsigned physical_width,
                                       unsigned y,const uint32_t *rgba,unsigned width)
{
    static const unsigned spread[8]={0,1,4,5,16,17,20,21};
    unsigned row=(y>>3)*(physical_width>>3)*64+2*spread[y&7];
    for(unsigned x=0;x<width;x++)dst[row+(x>>3)*64+spread[x&7]]=__builtin_bswap32(rgba[x]);
}

#endif
