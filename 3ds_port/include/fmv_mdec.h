/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SH_FMV_MDEC_H
#define SH_FMV_MDEC_H
#include <stdint.h>
#include <stddef.h>
/* Movie-only fork, fixed 320x208 MDEC v2, RGB24 output. Single decode owner.
 * API is retained for byte comparison against the unmodified PC decoder. */
typedef struct {int width,height,output_signed;} mdec_ctx_t;
void mdec_init(mdec_ctx_t *,int width,int height);
/* Returns 260 macroblocks on success; negative on malformed/truncated VLC. */
int mdec_decode_frame(mdec_ctx_t *,const uint8_t *,size_t,uint8_t *rgb);
#endif
