/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SH_GAME_FMV_H
#define SH_GAME_FMV_H
#include <stdint.h>
enum { GAME_FMV_DONE=0,GAME_FMV_SKIPPED=1,GAME_FMV_EXIT=2,GAME_FMV_ERROR=-1 };
/* Blocking presentation only. The original caller owns progression. */
int32_t game_fmv_play(uint32_t file_id,uint32_t frame_limit);
void game_fmv_platform_begin(void);
void game_fmv_platform_end(uint64_t began);
#endif
