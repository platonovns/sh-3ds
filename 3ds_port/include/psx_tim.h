#ifndef SH_PSX_TIM_H
#define SH_PSX_TIM_H
#include "psx_vram.h"
/* Bounded reader, from memory fixtures or a Stage 2 ShDisc resource. The reader
 * returns 0 on success. No source pointer or host-width long in disk layout. */
typedef int (*PsxReadAt)(void *context, uint32_t offset, void *out, uint32_t bytes);
typedef struct { PsxReadAt read; void *context; uint32_t bytes; } PsxSource;
typedef struct {
    uint32_t flags, mode, has_clut, width, height, consumed;
    PsxRect image, clut;
    uint32_t image_offset, image_bytes, clut_offset, clut_bytes;
    uint32_t palette_entries, palette_count;
} PsxTim;
/* Same TIM_IMAGE mode/crect/caddr/prect/paddr contract as OpenTIM/ReadTIM,
 * with validated offsets and an explicit extent instead of unsafe pointers. */
int psx_tim_parse(PsxSource source, PsxTim *out);
/* NULL destinations preserve authored coordinates. Overrides change x/y only,
 * matching Fs_QueuePostLoadTim's descriptor relocations. */
int psx_tim_upload(PsxVram *vram, PsxSource source, const PsxTim *tim,
                   const PsxRect *image_destination, const PsxRect *clut_destination);
int psx_tim_region(const PsxTim *tim, PsxRect image_destination,
                   PsxRect clut_destination, unsigned palette, PsxTextureRegion *out);
#endif
