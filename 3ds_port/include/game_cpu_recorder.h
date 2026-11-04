#ifndef SH_GAME_CPU_RECORDER_H
#define SH_GAME_CPU_RECORDER_H
/* Deliberately absent from normal production builds. */
#if defined(SH_CPU_AUDIT_RECORDER)
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include "game_cpu_audit.h"
typedef struct {
    uint32_t game,map,room,flashlight,fps_mode,control_mode,lcd_frames;
    int32_t x,z,yaw,view[6];
} CpuRecordContext;
typedef struct {
    uint64_t ticks[GCPU_SCOPES];
    uint32_t calls[GCPU_SCOPES],valid;
} CpuRecordSnapshot;
void game_cpu_audit_snapshot(CpuRecordSnapshot *out);
void cpu_recorder_init(const char *directory,const char *build);
uint32_t cpu_recorder_input(uint32_t held,const CpuRecordContext *context);
void cpu_recorder_finish(const CpuRecordContext *context,const char *reason);
int cpu_recorder_label(char *out,size_t size);
void cpu_recorder_reference(FILE *out);
#endif
#endif
