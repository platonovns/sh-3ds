#ifndef SH_TIM_SELFTEST_H
#define SH_TIM_SELFTEST_H
#include "psx_tim.h"
typedef struct { uint32_t passed, total, first_failure, expected, actual; } TimSelftest;
void tim_selftest_run(PsxVram *vram, TimSelftest *result);
#endif
