#ifndef SH_GAME_TEXTURE_DECODE_H
#define SH_GAME_TEXTURE_DECODE_H
#include "psx_vram.h"
#include <stdbool.h>
/* One upload's fixed palette snapshot. No persistent decoded-page cache. */
typedef struct { const PsxVram *vram; unsigned mode,px,py,coverage; uint32_t palette[256]; } GameTextureDecode;
bool game_texture_decode_init(GameTextureDecode *decode,const PsxVram *vram,uint32_t page,uint32_t clut);
bool game_texture_decode_row(void *context,unsigned y,uint8_t *rgba,unsigned width);
/* Exact 256x256 cache-page upload directly into PICA Morton order. */
bool game_texture_decode_tiled(const GameTextureDecode *decode,uint32_t *tiled);
bool game_texture_decode_tiles(const GameTextureDecode *decode,uint32_t *tiled,
                              unsigned x0,unsigned y0,unsigned x1,unsigned y1);
#endif
