#ifndef SH_PSX_VRAM_H
#define SH_PSX_VRAM_H
#include <stddef.h>
#include <stdint.h>
#define PSX_VRAM_WIDTH 1024u
#define PSX_VRAM_HEIGHT 512u
enum { PV_OK = 0, PV_BOUNDS = -20, PV_FORMAT = -21, PV_IO = -22, PV_MODE = -23 };
typedef struct { uint16_t x, y, w, h; } PsxRect;
typedef struct {
    uint16_t words[PSX_VRAM_WIDTH * PSX_VRAM_HEIGHT];
    /* Global conservative invalidation token; consumers must flush on wrap.
     * Changes on every write, including partial streaming uploads. */
    uint32_t generation;
} PsxVram;
typedef struct {
    PsxRect image; /* Word coordinates/extent, matching PsyQ RECT16. */
    uint16_t clut; /* getClut encoding: y<<6 | x/16. */
    uint8_t mode;  /* 0=4-bit, 1=8-bit, 2=16-bit. */
} PsxTextureRegion;
typedef struct { uint8_t rgba[4], stp, transparent; uint16_t word; } PsxTexel;
void psx_vram_init(PsxVram *vram);
int psx_vram_rect_valid(PsxRect rect);
int psx_vram_load(PsxVram *vram, PsxRect rect, const void *little_endian_words, size_t bytes);
int psx_vram_store(const PsxVram *vram, PsxRect rect, void *little_endian_words, size_t bytes);
/* Overlap-safe snapshot semantics, bounded to one 1024-word stack row. */
int psx_vram_move(PsxVram *vram, PsxRect source, uint16_t x, uint16_t y);
uint32_t psx_vram_crc(const PsxVram *vram);
int psx_region_valid(PsxTextureRegion region);
void psx_color_decode(uint16_t word, PsxTexel *out);
/* Reads the palette from VRAM, independently of the original TIM lifetime. */
int psx_vram_texel(const PsxVram *vram, PsxTextureRegion region, unsigned x, unsigned y, PsxTexel *out);
/* Top-down RGBA8 diagnostic mapping: 0000 transparent; all other texels opaque.
 * STP is retained in VRAM and PsxTexel, never represented as ordinary alpha. */
int psx_vram_decode(const PsxVram *vram, PsxTextureRegion region, void *rgba, size_t bytes);
#endif
