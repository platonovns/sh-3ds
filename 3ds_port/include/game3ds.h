#ifndef SH_GAME3DS_H
#define SH_GAME3DS_H
#include <stdint.h>
#include <stdio.h>
#include "stage4_fs.h"
/* Shared ABI contains no SDK/game enum or bool. */
void game3ds_run(Stage4FsResult *result, PsxVram *vram);
void game3ds_observe(uint32_t state, uint32_t step, uint32_t fs_state, uint32_t fs_step);
void game3ds_halt(uint32_t code, const char *operation, uint32_t detail) __attribute__((noreturn));
uint32_t game3ds_wait_vblank(void);
uint32_t game3ds_read_pad(void);
void game3ds_read_analog(int *cx,int *cy,int *rx,int *ry);
uint32_t game3ds_control_mode(void);
uint32_t Game3ds_CanPause(void);
void Game3ds_PadPoll(void);
void Game3ds_CameraLook(void *matrix);
int Game3ds_FeedbackDecay(unsigned period);
uint32_t Game3ds_FadeState(void);
void Game3ds_BeginUpdate(uint32_t state);
void game3ds_status_begin(void);
uint32_t game3ds_take_title_request(void);
uint32_t game3ds_fps_limit(void);
uint32_t game3ds_q12_clock(void);
void Game3ds_FpsLimit(unsigned fps);
void game3ds_combat_phase(uint32_t phase,uint32_t character,uint32_t control,uint32_t animation,uint32_t attack);
uint32_t game3ds_debug_enabled(void);
void game3ds_model_observe(uint32_t character,uint32_t packet_bytes,uint32_t fade);
void game3ds_visibility_observe(uint32_t slot,const int32_t *row);
void game3ds_gpu_sync(void);
void game3ds_gpu_begin_draw(void);
void game3ds_gpu_end_draw(void);
void game3ds_gpu_extent(uint32_t *width,uint32_t *height);
uint32_t game3ds_gpu_display(void);
void game3ds_gpu_clip(int *left,int *top,int *right,int *bottom);
void game3ds_gpu_frame_complete(void);
void game3ds_vram_target_begin(unsigned x,unsigned y,unsigned w,unsigned h,unsigned view_width);
void game3ds_vram_target_end(void);
void game3ds_feedback_capture(uint32_t width,uint32_t height);
void Game3ds_FeedbackInvalidate(uint32_t x,uint32_t y,uint32_t width,uint32_t height);
int game3ds_gpu_readback(uint32_t x,uint32_t y,uint32_t width,uint32_t height,uint16_t *out,uint32_t stride);
int game3ds_gpu_resolve(uint32_t x,uint32_t y,uint32_t width,uint32_t height,uint32_t out_width,uint32_t out_height,uint16_t *out,uint32_t stride);
void game3ds_gpu_rect(const float *vertices, uint32_t count, uint32_t page, uint32_t clut, uint32_t textured, uint32_t blend);
void game3ds_gpu_dirty(void);
void game3ds_gpu_dirty_rect(uint32_t x, uint32_t y, uint32_t w, uint32_t h);
void game3ds_vram_textured_rect(unsigned x,unsigned y,unsigned w,unsigned h,unsigned page,unsigned clut,unsigned u,unsigned v,unsigned semi,unsigned dither);
uint64_t game3ds_ticks(void);
uint32_t game3ds_vblank_clock(void);
uint32_t game3ds_hblank_clock(void);
void game3ds_primitive_ticks(uint64_t ticks);
void game3ds_packet_observe(uint32_t bytes,uint32_t capacity,uint32_t buffer);
void *Game3ds_PacketBegin(unsigned buffer);
void Game3ds_PacketBounds(uintptr_t *base,unsigned *capacity);
void Game3ds_PacketCheck(const void *packet,unsigned bytes);
void Game3ds_PacketValidate(void);
void game3ds_timestep(uint32_t dt, uint32_t raw_dt);
void game3ds_animation_observe(uint32_t state, uint32_t upper, uint32_t lower_anim,
                               uint32_t upper_anim, uint32_t lower_frame, uint32_t upper_frame);
void game3ds_player_observe(int32_t x, int32_t z, int32_t yaw, uint32_t state, uint32_t pad,
                           uint32_t step0, uint32_t step1, uint32_t event);
void game3ds_progress(const char *phase, uint32_t detail);
void Game3ds_Progress(const char *phase, uint32_t detail);
void Game3ds_MapBind(uint32_t map);
void game3ds_map_observe(uint32_t map, uint32_t room, int32_t health, uint32_t control_disabled);
void game3ds_inventory_observe(uint32_t count,uint32_t equipped,uint32_t selected,uint32_t pickups,const uint32_t *slots);
void game3ds_media_skip(uint32_t kind, uint32_t id, uint32_t offset);
int stage4_fs_game_open(Stage4FsResult *result, PsxVram *vram, const char *bin, const char *cue);
void stage4_fs_game_close(void);
void stage4_fs_game_observe(void);
void stage4_fs_game_allow_span(uint32_t file, void *data, uint32_t capacity);
void stage4_fs_game_image_span(const void *data, uint32_t bytes);
void stage4_fs_game_cache_enable(int enabled);
void stage4_fs_game_preload(const char *tag);
int stage4_fs_presentation_read(uint32_t file, void **out, uint32_t *size);
int Game3ds_LowerDraw(uint16_t *pixels);
void game3ds_lower_backlight_observe(unsigned game,unsigned sys,unsigned cutscene,unsigned disabled,unsigned has_map);
void game3ds_lower_backlight_tick(void);
void Game3ds_LowerCounter(uint16_t *pixels,const char *text);
uint32_t Game3ds_LowerHoldTransition(void);
uint32_t Game3ds_LowerOwner(unsigned display,unsigned start);
uint32_t Game3ds_CanOpenPause(void);
void game3ds_recoverable(const char *operation, int32_t detail);
void stage4_fs_game_report(FILE *out);
#endif
