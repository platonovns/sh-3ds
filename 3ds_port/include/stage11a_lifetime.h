#ifndef SH_STAGE11A_LIFETIME_H
#define SH_STAGE11A_LIFETIME_H
#include <stdint.h>
#include <stdio.h>
#include "game_cpu_recorder.h"
#define LT_HISTORY 32u
#define LT_RENDER_WORDS 40u
#define LT_CACHE_WORDS 24u
#define LT_PROFILE_WORDS 48u
#define LT_SPU_WORDS 16u
#define LT_VOICE_WORDS 10u
#define LT_XA_WORDS 16u
#define LT_AUDIO_WORDS 14u
#define LT_RESOURCE_WORDS 10u
#define LT_ALLOC_APIS 13u
typedef struct {
    uint64_t tick,capture_ticks;
    uint32_t serial,reason,mode,thread_result,threads;
    CpuRecordContext context;
    uint32_t memory[9],render[LT_RENDER_WORDS],cache[LT_CACHE_WORDS];
    uint32_t profile[LT_PROFILE_WORDS],spu[LT_SPU_WORDS],voices[24][LT_VOICE_WORDS];
    uint32_t xa[LT_XA_WORDS],audio[LT_AUDIO_WORDS],resource[LT_RESOURCE_WORDS];
    uint32_t alloc[LT_ALLOC_APIS][4];
} Stage11aLifetime;
#ifdef __cplusplus
extern "C" {
#endif
void stage11a_lifetime_init(void);
void stage11a_lifetime_poll(const CpuRecordContext *context);
void stage11a_lifetime_boundary(unsigned start);
void stage11a_lifetime_report(FILE *out);
int stage11a_lifetime_toggle(void);
unsigned stage11a_lifetime_mode(void);
void stage11a_lifetime_alloc(unsigned api,uint32_t bytes,int failed);
void stage11a_lifetime_render(Stage11aLifetime *out);
void stage11a_lifetime_cache(uint32_t out[LT_CACHE_WORDS]);
void stage11a_lifetime_profile(uint32_t out[LT_PROFILE_WORDS]);
void stage11a_lifetime_spu(uint32_t out[LT_SPU_WORDS],uint32_t voices[24][LT_VOICE_WORDS]);
void stage11a_lifetime_xa(uint32_t out[LT_XA_WORDS]);
void stage11a_lifetime_audio(uint32_t out[LT_AUDIO_WORDS]);
void stage11a_lifetime_resource(uint32_t out[LT_RESOURCE_WORDS]);
void stage11a_lifetime_renderer(uint32_t out[8]);
void game_prof_lifetime_toggle(unsigned enabled);
void game_cpu_audit_lifetime_toggle(unsigned enabled);
#ifdef __cplusplus
}
#endif
#endif
