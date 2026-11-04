#ifndef SH_3DS_ENGINE_GATE_H
#define SH_3DS_ENGINE_GATE_H
#include <stdint.h>
/* Plain fixed-width C boundary: no game bool or libctru typedefs cross it. */
typedef struct {
    uint32_t memory_ok, scratch_ok, abi_ok, core_ok;
    uint32_t ram_bytes, scratch_bytes, pointer_bytes, bool_bytes;
    uint32_t gte_passed, gte_total, failed_test;
    int32_t actual, expected;
    uint32_t normal_before, normal_after, linear_before, linear_after;
} EngineGate;
void engine_gate_run(EngineGate *result);
#endif
