/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SH_FMV_STREAM_H
#define SH_FMV_STREAM_H
#include "sh_disc.h"
#define FMV_WIDTH 320u
#define FMV_HEIGHT 208u
#define FMV_FPS 15u
#define FMV_RATE 37800u
#define FMV_AUDIO_FRAMES 2016u
#define FMV_FRAME_BYTES (9u*2016u)
#define FMV_RGB_BYTES (FMV_WIDTH*FMV_HEIGHT*3u)
typedef struct { uint32_t id,lba,sectors,frame_limit; const char *name; } FmvEntry;
typedef struct {
    PsxDisc *disc;
    FmvEntry entry;
    uint32_t cursor,frame,first_lba,decoded_audio,emitted_audio;
    uint32_t raw_sectors,video_sectors,audio_sectors,silent_sectors;
    int32_t history[2][2];
    uint8_t raw[2352],bits[FMV_FRAME_BYTES];
    int16_t pcm[FMV_AUDIO_FRAMES*2];
} FmvStream;
/* Callback consumes/copies PCM before returning; zero aborts, negative errors.
 * PTS is in 37800-Hz stereo frames. Silence is emitted for absent XA slots. */
typedef int (*FmvAudioSink)(void *,const int16_t *,uint32_t,uint32_t);
int fmv_entry(ShDisc *,uint32_t id,uint32_t requested_limit,FmvEntry *);
void fmv_stream_init(FmvStream *,PsxDisc *,const FmvEntry *);
/* 1 complete frame, 0 logical end, negative corrupt/I/O/abort. */
int fmv_next_frame(FmvStream *,FmvAudioSink,void *,uint32_t *number,uint32_t *bytes);
int fmv_finish_audio(FmvStream *,FmvAudioSink,void *);
uint32_t fmv_frame_sample(uint32_t number);
uint32_t fmv_duration_samples(const FmvEntry *);
#endif
