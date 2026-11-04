#ifndef SH_GAME_AUDIO_H
#define SH_GAME_AUDIO_H
#include <stdint.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
int32_t game_audio_init(void);
int32_t game_audio_output_ready(void);
void game_audio_shutdown(void);
void game_audio_pause(uint32_t paused);
uint32_t game_audio_lifecycle_paused(void);
void game_audio_lock(void);
void game_audio_unlock(void);
void game_audio_report(FILE *out);
void game_audio_tick(void);
uint32_t game_audio_xa_pending(void);
uint32_t game_audio_xa_ticks(void);
void game_audio_xa_cancel(uint32_t reason,uint32_t context0,uint32_t context1);
void game_spu_audio_report(FILE *out);
void game_spu_xa_submitted(uint32_t frames,uint32_t nonzero);
void game_spu_init(void);
void game_spu_render(int16_t *out, uint32_t frames);
void game_audio_cd_close(void);
#ifdef __cplusplus
}
#endif
#endif
