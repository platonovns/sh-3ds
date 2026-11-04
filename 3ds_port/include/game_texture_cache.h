#ifndef SH_GAME_TEXTURE_CACHE_H
#define SH_GAME_TEXTURE_CACHE_H
#include "psx_vram.h"
#include <stdbool.h>
/* The moving Cafe dialogue exceeds 64 simultaneous keys (65 observed).
 * Finite 24 MiB maximum at 256x256 RGBA8; allocation stays lazy and LRU. */
#define GAME_TEXTURE_LIMIT 96u
typedef struct {
    uint32_t page, clut, age;
    bool occupied, dirty, pinned;
    /* Conservative union in 8x8 decoded tiles; palette writes cover all tiles. */
    uint8_t tx0,ty0,tx1,ty1;
} GameTextureEntry;
typedef struct {
    GameTextureEntry entries[GAME_TEXTURE_LIMIT];
    uint32_t clock, hits, misses, evictions, invalidations, uploads, active, peak;
    uint32_t pinned, peak_pinned;
    uint32_t comparisons;
    /* Slot+1, zero is empty. Key changes rebuild this small index; dirty and
     * pinned flags never change key identity. No extra texture allocations. */
    uint8_t index[256];
} GameTextureCache;
/* Pin every already-resident key needed by the submission before acquiring
 * misses. A slot cannot be replaced while any staged draw references it. */
void game_texture_begin(GameTextureCache *cache);
void game_texture_pin(GameTextureCache *cache, uint32_t page, uint32_t clut);
int game_texture_acquire(GameTextureCache *cache, uint32_t page, uint32_t clut, bool *upload);
/* Remove an unpinned entry when its backing allocation is reused. */
bool game_texture_discard(GameTextureCache *cache, unsigned slot);
/* Call at a synchronized VRAM write boundary. Includes packed image words and
 * the live palette, including horizontal wrap, independent of TIM lifetime. */
void game_texture_invalidate(GameTextureCache *cache, PsxRect rect);
#endif
