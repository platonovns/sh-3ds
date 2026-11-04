#include "psx_vram.h"
#include "psx_disc.h"
#include <string.h>

int psx_vram_rect_valid(PsxRect r)
{
    return r.w && r.h && (unsigned)r.x + r.w <= PSX_VRAM_WIDTH &&
           (unsigned)r.y + r.h <= PSX_VRAM_HEIGHT;
}
void psx_vram_init(PsxVram *v)
{
    if (v) { memset(v->words, 0, sizeof(v->words)); v->generation = 1; }
}
int psx_vram_load(PsxVram *v, PsxRect r, const void *src, size_t bytes)
{
    if (!v || !src || !psx_vram_rect_valid(r) || bytes < (size_t)r.w * r.h * 2) return PV_BOUNDS;
    const uint8_t *p = src;
    for (unsigned y = 0; y < r.h; ++y)
        for (unsigned x = 0; x < r.w; ++x, p += 2)
            v->words[(r.y + y) * PSX_VRAM_WIDTH + r.x + x] = (uint16_t)(p[0] | p[1] << 8);
    ++v->generation;
    return PV_OK;
}
int psx_vram_store(const PsxVram *v, PsxRect r, void *dst, size_t bytes)
{
    if (!v || !dst || !psx_vram_rect_valid(r) || bytes < (size_t)r.w * r.h * 2) return PV_BOUNDS;
    uint8_t *p = dst;
    for (unsigned y = 0; y < r.h; ++y)
        for (unsigned x = 0; x < r.w; ++x, p += 2) {
            uint16_t w = v->words[(r.y + y) * PSX_VRAM_WIDTH + r.x + x];
            p[0] = w; p[1] = w >> 8;
        }
    return PV_OK;
}
int psx_vram_move(PsxVram *v, PsxRect s, uint16_t x, uint16_t y)
{
    PsxRect d = {x, y, s.w, s.h};
    if (!v || !psx_vram_rect_valid(s) || !psx_vram_rect_valid(d)) return PV_BOUNDS;
    for (unsigned i = 0; i < s.h; ++i) {
        unsigned row = y > s.y ? s.h - 1 - i : i;
        memmove(v->words + (y + row) * PSX_VRAM_WIDTH + x,
                v->words + (s.y + row) * PSX_VRAM_WIDTH + s.x, s.w * 2u);
    }
    ++v->generation;
    return PV_OK;
}
uint32_t psx_vram_crc(const PsxVram *v)
{
    if (!v) return 0;
    uint8_t row[2048];
    uint32_t crc = 0;
    for (unsigned y = 0; y < PSX_VRAM_HEIGHT; ++y) {
        psx_vram_store(v, (PsxRect){0, y, 1024, 1}, row, sizeof(row));
        crc = PsxDisc_Crc32(crc, row, sizeof(row));
    }
    return crc;
}
int psx_region_valid(PsxTextureRegion r)
{
    unsigned entries = r.mode == 0 ? 16 : 256;
    return r.mode <= 2 && psx_vram_rect_valid(r.image) &&
           (r.mode == 2 || (unsigned)(r.clut & 63) * 16 + entries <= PSX_VRAM_WIDTH);
}
void psx_color_decode(uint16_t w, PsxTexel *o)
{
    for (unsigned c = 0; c < 3; ++c) {
        unsigned n = (w >> (c * 5)) & 31;
        o->rgba[c] = (uint8_t)((n << 3) | (n >> 2));
    }
    o->rgba[3] = w ? 255 : 0;
    o->stp = w >> 15; o->transparent = w == 0; o->word = w;
}
int psx_vram_texel(const PsxVram *v, PsxTextureRegion r, unsigned x, unsigned y, PsxTexel *o)
{
    if (!v || !o || !psx_region_valid(r) || y >= r.image.h ||
        x >= (unsigned)r.image.w * (4u >> r.mode)) return PV_BOUNDS;
    unsigned packed = 4u >> r.mode;
    uint16_t w = v->words[(r.image.y + y) * PSX_VRAM_WIDTH + r.image.x + x / packed];
    if (r.mode != 2) {
        unsigned bits = 4u << r.mode;
        unsigned index = (w >> ((x % packed) * bits)) & ((1u << bits) - 1);
        unsigned cx = (r.clut & 63) * 16, cy = (r.clut >> 6) & 511;
        w = v->words[cy * PSX_VRAM_WIDTH + cx + index];
    }
    psx_color_decode(w, o);
    return PV_OK;
}
int psx_vram_decode(const PsxVram *v, PsxTextureRegion r, void *rgba, size_t bytes)
{
    if (!v || !rgba || !psx_region_valid(r)) return PV_BOUNDS;
    unsigned width = r.image.w * (4u >> r.mode);
    if (bytes < (size_t)width * r.image.h * 4) return PV_BOUNDS;
    uint8_t *p = rgba;
    for (unsigned y = 0; y < r.image.h; ++y)
        for (unsigned x = 0; x < width; ++x, p += 4) {
            PsxTexel t;
            psx_vram_texel(v, r, x, y, &t);
            memcpy(p, t.rgba, 4);
        }
    return PV_OK;
}
