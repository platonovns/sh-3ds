#include "game_cpu_recorder_test.c"
#include "stage11a_perf.h"
/* No device backend in the filesystem/input recorder fixture. */
void stage11a_audio_boundary(unsigned start) {(void)start;}
void stage11a_audio_report(FILE *out) {(void)out;}
void stage11a_renderer_boundary(unsigned start) {(void)start;}
void stage11a_renderer_report(FILE *out) {(void)out;}
