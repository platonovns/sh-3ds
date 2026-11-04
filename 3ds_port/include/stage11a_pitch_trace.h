#ifndef SH_STAGE11A_PITCH_TRACE_H
#define SH_STAGE11A_PITCH_TRACE_H
#include <stdint.h>
#include <stdio.h>
#define SH_PITCH_MIDI_WORDS 15u
typedef struct {uint32_t kind,channel,cc1,cc2,caller;} Stage11aPitchScope;
#ifdef __cplusplus
extern "C" {
#endif
Stage11aPitchScope stage11a_pitch_enter(unsigned kind,unsigned channel,unsigned cc1,unsigned cc2,uintptr_t caller);
void stage11a_pitch_leave(Stage11aPitchScope *saved);
void stage11a_pitch_midi_snapshot(unsigned voice,uint32_t out[SH_PITCH_MIDI_WORDS]);
unsigned game_spu_silent_fast_enabled(void);
int game_spu_silent_fast_toggle(void);
void game_spu_silent_fast_observe(uint32_t eligible,uint32_t used,uint32_t grouped,unsigned frames);
void game_spu_pitch_trace_report(FILE *out);
#ifdef __cplusplus
}
#endif
#define SH_PITCH_SCOPE(kind,ch,c1,c2) \
    Stage11aPitchScope sh_pitch_scope __attribute__((cleanup(stage11a_pitch_leave))) = \
        stage11a_pitch_enter(kind,ch,c1,c2,(uintptr_t)__builtin_return_address(0))
#endif
