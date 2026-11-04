#include "tim_gate.h"
#include "tim_selftest.h"
#include "psx_disc.h"
#include "sh_disc.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static PsxVram vram;
static int fault;
int __real_ShDisc_Resolve(ShDisc *, uint32_t, ShDiscFile *);
int __wrap_ShDisc_Resolve(ShDisc *disc, uint32_t id, ShDiscFile *out)
{
    return fault == 4 && id == 0 ? PD_NOT_FOUND : __real_ShDisc_Resolve(disc, id, out);
}
size_t __real_fread(void *, size_t, size_t, FILE *);
size_t __wrap_fread(void *p, size_t size, size_t count, FILE *file)
{
    long pos = ftell(file);
    if (fault == 2 && pos == 64 * 2352) return 0;
    size_t n = __real_fread(p, size, count, file);
    long off = fault == 1 ? 25 * 2352 + 31 : 64 * 2352 + 24 + 544;
    if ((fault == 1 || fault == 3) && pos <= off && off - pos < (long)(size * n))
        ((uint8_t *)p)[off - pos] ^= 1;
    return n;
}
typedef struct { uint8_t bytes[128]; unsigned size; } Memory;
static int read_memory(void *ctx, uint32_t off, void *out, uint32_t bytes)
{
    Memory *m = ctx;
    if (off > m->size || bytes > m->size - off) return -1;
    memcpy(out, m->bytes + off, bytes); return 0;
}
static void fuzz(void)
{
    Memory m = {{0}, 128};
    PsxSource s = {read_memory, &m, m.size};
    uint32_t state = 42;
    for (unsigned i = 0; i < 10000; ++i) {
        for (unsigned j = 0; j < m.size; ++j) {
            state = state * 1664525u + 1013904223u;
            m.bytes[j] = state >> 24;
        }
        if (i % 2) { m.bytes[0] = 16; m.bytes[1] = m.bytes[2] = m.bytes[3] = 0; }
        PsxTim t;
        if (psx_tim_parse(s, &t) == 0) psx_tim_upload(&vram, s, &t, NULL, NULL);
        AnmAudit a; tim_gate_anm(s, &a);
    }
    /* Header claims frames outside extent, plus short/missing header. */
    AnmAudit a;
    assert(tim_gate_anm((PsxSource){read_memory, &m, 19}, &a) == PV_BOUNDS);
    assert(tim_gate_anm((PsxSource){NULL, &m, 128}, &a) == PV_BOUNDS);
}
int main(int argc, char **argv)
{
    assert(argc == 3);
    TimSelftest tests;
    tim_selftest_run(&vram, &tests);
    if (tests.first_failure) fprintf(stderr, "selftest %u expected=%u actual=%u\n", tests.first_failure, tests.expected, tests.actual);
    assert(tests.total == tests.passed && !tests.first_failure);
    TimGate gate;
    tim_gate_run(&gate, &vram, argv[1], argv[2]);
    assert(!gate.first_failure && gate.resources[0].passed == 63 && gate.resources[1].passed == 63 && gate.anm.passed);
    assert(tim_gate_log(&gate, "3ds_port/reports/tim-pc.log") == 0);
    assert(tim_gate_log(&gate, "/no-such-stage3-directory/log.txt") != 0);
    _Static_assert(sizeof(TimGate) == 312, "Metadata boundary");
    _Static_assert(sizeof(PsxTim) == 64, "TIM metadata boundary");
    printf("{\"synthetic_passed\":%u,\"synthetic_total\":%u,\"gate_words\":[", tests.passed, tests.total);
    for (unsigned i = 0; i < sizeof(gate) / 4; ++i) {
        uint32_t n; memcpy(&n, (uint8_t *)&gate + i * 4, 4);
        printf("%s%u", i ? "," : "", n);
    }
    printf("],");
    tim_gate_run(&gate, &vram, "/missing-stage3.bin", argv[2]);
    assert(gate.first_failure == 300 && gate.open_status == PD_NOT_FOUND);
    for (fault = 1; fault <= 4; ++fault) {
        tim_gate_run(&gate, &vram, argv[1], argv[2]);
        assert(gate.first_failure == (fault == 1 ? 301u : fault == 2 ? 312u : fault == 3 ? 313u : 310u));
        assert(!gate.resources[0].passed);
    }
    fault = 0;
    fuzz();
    printf("\"negative_cases\":[\"missing BIN\",\"unsupported identity\",\"resource not found\",\"resource short IO\","
           "\"resource CRC\",\"log open failure\",\"truncated TIM at every byte\",\"invalid CLUT\","
           "\"invalid image\",\"forged metadata\",\"ANM bounds\"],\"fuzz_inputs\":10000}\n");
    return 0;
}
