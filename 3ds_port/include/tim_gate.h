#ifndef SH_TIM_GATE_H
#define SH_TIM_GATE_H
#include "psx_tim.h"
enum { TG_CRC = 1, TG_PARSE = 2, TG_BOUNDS = 4, TG_UPLOAD = 8, TG_VRAM = 16, TG_DECODE = 32 };
typedef struct {
    uint32_t file_id, bytes, crc, passed;
    int32_t status;
    PsxTim tim;
    PsxRect image_destination, clut_destination;
    uint32_t vram_crc, decoded_crc, generation, stp_texels, transparent_texels;
} TimResourceGate;
typedef struct {
    uint32_t crc, data_offset, rotation_bones, translation_bones, stride, bones;
    uint32_t active_mask, declared_bytes, frames, scale, root_y, passed;
} AnmAudit;
typedef struct {
    int32_t open_status, identity_status;
    uint32_t shadow_ok, first_failure, expected, actual;
    TimResourceGate resources[2];
    AnmAudit anm;
} TimGate;
const char *tim_gate_name(unsigned index);
void tim_gate_run(TimGate *gate, PsxVram *vram, const char *bin, const char *cue);
/* Public bounded ANM layout audit, not an animation consumer. */
int tim_gate_anm(PsxSource source, AnmAudit *out);
int tim_gate_decode_row(const PsxVram *vram, PsxTextureRegion region,
                         unsigned y, uint8_t *rgba, unsigned width);
int tim_gate_log(const TimGate *gate, const char *path);
#endif
