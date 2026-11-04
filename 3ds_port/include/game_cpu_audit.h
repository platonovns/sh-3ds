#ifndef SH_GAME_CPU_AUDIT_H
#define SH_GAME_CPU_AUDIT_H
#include <stdint.h>
#include <stdio.h>
enum GameCpuThread { GCPU_MAIN, GCPU_SPU, GCPU_XA, GCPU_NDSP, GCPU_THREADS };
enum GameCpuScope { GCPU_SPU_BLOCK, GCPU_SPU_WAIT, GCPU_XA_STEP, GCPU_XA_WAIT,
    GCPU_FLASHLIGHT_SETUP, GCPU_RESOLVE, GCPU_SCOPES };
void game_cpu_audit_init(unsigned detailed);
void game_cpu_audit_poll(void);
void game_cpu_audit_enter(unsigned thread);
uint64_t game_cpu_audit_begin(unsigned thread);
void game_cpu_audit_end(unsigned scope, uint64_t start);
void game_cpu_audit_report(FILE *out);
#endif
