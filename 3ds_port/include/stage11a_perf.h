#ifndef SH_STAGE11A_PERF_H
#define SH_STAGE11A_PERF_H
#include <stdint.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
/* One writer per metric. The first six have bounded histograms. */
enum Stage11aMetric {
    S11_WALL, S11_WORK, S11_BLOCK, S11_RENDER, S11_MAIN_LOCK, S11_SPU_LOCK,
    S11_FLUSH, S11_NDSP, S11_ADVANCE, S11_DECODE, S11_INTERPOLATE,
    S11_ADSR, S11_VOLUME, S11_ACCUMULATE, S11_CD, S11_REVERB, S11_OUTPUT,
    S11_VOICE, S11_ACTIVE, S11_FROZEN, S11_NOISE, S11_PMON, S11_COUNT
};
void stage11a_perf_start(void);
void stage11a_perf_stop(void);
void stage11a_perf_add(unsigned metric,uint64_t ticks);
void stage11a_perf_queue(unsigned depth);
void stage11a_perf_report(FILE *out);
int stage11a_perf_active(void);
void stage11a_audio_boundary(unsigned start);
void stage11a_audio_report(FILE *out);
void stage11a_renderer_boundary(unsigned start);
void stage11a_renderer_report(FILE *out);
#ifdef __cplusplus
}
/* Optional sampled detail only. Its nested advance/decode scopes must not be
 * added together, and none are scheduled CPU-time measurements. */
struct Stage11aSpuScope {
    unsigned metric; uint64_t begin;
    Stage11aSpuScope(unsigned m,bool enabled,uint64_t (*clock)()):
        metric(m),begin(enabled?clock():0) {}
    ~Stage11aSpuScope();
};
#endif
#endif
