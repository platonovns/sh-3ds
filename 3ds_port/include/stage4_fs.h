#ifndef SH_STAGE4_FS_H
#define SH_STAGE4_FS_H
#include "psx_vram.h"
/* Fixed-width HAL boundary; game structs and SDK types never cross it. */
typedef struct {
    uint32_t checkpoint, first_failure, file_id, detail;
    uint32_t reads, uploads, completed, ticks, vram_crc;
    const char *operation;
    uint32_t state, substate;
} Stage4FsResult;
enum { S4_BOOT, S4_FS_INIT, S4_FS_READ, S4_TIM_POSTLOAD, S4_VRAM, S4_FS_DONE };
void stage4_fs_run(Stage4FsResult *result, PsxVram *vram, const char *bin, const char *cue);
const char *stage4_checkpoint_name(uint32_t checkpoint);
void stage4_fs_fail(uint32_t code, const char *operation, uint32_t detail);
#ifdef SH_3DS_GAME
int stage4_fs_open_read_tim(void *data, uint32_t file_id);
#endif
#endif
