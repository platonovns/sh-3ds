#ifndef SH_GAME_PROFILE_H
#define SH_GAME_PROFILE_H
#include <stdint.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
enum GameProfileCategory { GP_UPDATE, GP_GTE, GP_PRIMITIVE, GP_CACHE, GP_DECODE,
    GP_UPLOAD, GP_SUBMIT, GP_RESOURCE, GP_IO, GP_SYNC, GP_VBLANK, GP_REPORT,
    GP_MAP, GP_NPC, GP_PLAYER, GP_WORLD, GP_COMMAND, GP_PRESENT, GP_PAUSE,
    GP_AUDIO_LOCK, GP_SPU, GP_XA_PCM, GP_XA_WORKER,
    GP_SPU_VOICES, GP_SPU_REVERB, GP_SPU_MIX, GP_COUNT };
enum GameProfileCounter { GC_GTE, GC_CACHE_PROBES, GC_DECODES, GC_UPLOADS,
    GC_UPLOAD_BYTES, GC_READS, GC_READ_BYTES, GC_RAW_READS, GC_RAW_BYTES, GC_RAW_SEEKS,
    GC_PRIMITIVES, GC_BATCHES, GC_DRAWS, GC_COUNT };
extern int game_prof_enabled, game_prof_gte_sample;
#if defined(SH_PLAYTEST) && !defined(GAME_PROFILE_IMPLEMENTATION)
#define game_prof_enabled 0
#define game_prof_gte_sample 0
#elif defined(SH_STAGE11A_LIFETIME) && !defined(GAME_PROFILE_IMPLEMENTATION)
/* Private lifetime builds rebuild every audio worker that reads this flag.
 * Main-only legacy objects never race with the main-thread toggle. */
#define game_prof_enabled (__atomic_load_n(&game_prof_enabled,__ATOMIC_ACQUIRE))
#endif
uint64_t game_prof_clock(void);
void game_prof_add(unsigned category, uint64_t elapsed);
/* Worker counters are independent elapsed work, not main-thread frame cost.
 * Atomic 32-bit deltas are drained every frame; no ARM11 64-bit atomics. */
void game_prof_audio_add(unsigned category, uint64_t elapsed);
void game_prof_count(unsigned counter, uint64_t value);
void game_prof_enable(unsigned gte_stride);
void game_prof_frame(void);
void game_prof_context(unsigned state, unsigned player_state, int32_t x, int32_t z,
                       int32_t yaw, unsigned file, unsigned map_frames);
void game_prof_scene(unsigned map, unsigned room, unsigned cutscene, unsigned enemies);
void game_prof_report(FILE *out);
#if defined(SH_CPU_AUDIT_RECORDER)
void game_prof_sample_start(void);
void game_prof_sample_stop(void);
void game_prof_sample_report(FILE *out);
#endif
static inline uint64_t game_prof_begin(void) { return game_prof_enabled ? game_prof_clock() : 0; }
static inline void game_prof_end(unsigned category,uint64_t start)
{ if(start && game_prof_enabled) game_prof_add(category,game_prof_clock()-start); }
#if defined(SH_PLAYTEST) && !defined(GAME_PROFILE_IMPLEMENTATION)
#define game_prof_frame() ((void)0)
#define game_prof_count(a,b) ((void)sizeof(+(a)),(void)sizeof(+(b)))
#define game_prof_add(a,b) ((void)sizeof(+(a)),(void)sizeof(+(b)))
#define game_prof_audio_add(a,b) ((void)sizeof(+(a)),(void)sizeof(+(b)))
#define game_prof_context(a,b,c,d,e,f,g) ((void)sizeof(+(a)),(void)sizeof(+(b)),(void)sizeof(+(c)),(void)sizeof(+(d)),(void)sizeof(+(e)),(void)sizeof(+(f)),(void)sizeof(+(g)))
#define game_prof_scene(a,b,c,d) ((void)sizeof(+(a)),(void)sizeof(+(b)),(void)sizeof(+(c)),(void)sizeof(+(d)))
#endif
#ifdef __cplusplus
}
struct GameProfileGteScope {
    uint64_t start;
    GameProfileGteScope():start(game_prof_gte_sample?game_prof_clock():0)
    { if(game_prof_enabled) game_prof_count(GC_GTE,1); }
    ~GameProfileGteScope() { if(start && game_prof_gte_sample) game_prof_add(GP_GTE,game_prof_clock()-start); }
};
#endif
#endif
