#ifndef SH_GAME_XA_H
#define SH_GAME_XA_H
#include <stdint.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Fixed-width ABI shared by SDK thread glue and game/codec translation units. */
void game_xa_lock(void);
void game_xa_unlock(void);
int32_t game_xa_thread_init(void);
void game_xa_thread_shutdown(void);
void game_xa_pause(uint32_t paused);
void game_xa_disable_output(void);
void game_xa_start(uint32_t lba,uint32_t file,uint32_t channel,uint32_t ticks60);
void game_xa_stop(void);
enum {
    XA_CANCEL_ORIGINAL=1, XA_CANCEL_SKIP=2, XA_CANCEL_GAMEPLAY=3,
    XA_CANCEL_ROOM=4, XA_CANCEL_TITLE=5, XA_CANCEL_SHUTDOWN=6,
    XA_CANCEL_CD_SEEK=7, XA_CANCEL_CD_PAUSE=8, XA_CANCEL_ERROR=9,
    XA_CANCEL_WATCHDOG=10
};
enum { XA_NOTE_REQUEST=1, XA_NOTE_PRELOAD=2, XA_NOTE_DRIVER=3,
       XA_NOTE_CD=4, XA_NOTE_ACTIVE=5, XA_NOTE_WATCHDOG=6 };
void game_xa_cancel(uint32_t reason,uint32_t context0,uint32_t context1);
void game_xa_note(uint32_t event,uint32_t a,uint32_t b,uint32_t c);
void game_xa_thread_report(FILE *out);
uint32_t game_xa_step(void); /* Worker only. Never called by render/game threads. */
void game_xa_close(void);    /* After joining worker. */
uint32_t game_xa_pull(int16_t *pcm,uint32_t frames); /* Mixer only; never I/O. */
uint32_t game_xa_elapsed60(void);
uint32_t game_xa_status(void);
uint32_t game_xa_is_active(void);
uint32_t game_xa_draining(void); /* Source or decoded PCM still pending. */
uint32_t game_xa_ready(void); /* Real PCM reached SPU, not merely a queued ID. */
void game_xa_mix(uint32_t ll,uint32_t lr,uint32_t rr,uint32_t rl);
void game_xa_report(FILE *out);
int game_xa_decode(const uint8_t *sector2336,int16_t *pcm,int32_t history[2][2]);
#ifdef __cplusplus
}
#endif
#endif
