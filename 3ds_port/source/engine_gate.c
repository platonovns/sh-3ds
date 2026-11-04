#include "engine_gate.h"
#include "common.h"
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "main/rng.h"
#include "main/mem.h"
#include "main/fsmem.h"
#include "psx_memory.h"
#include <psx/inline_c.h>
#include <psx/gtereg.h>
#include <stddef.h>
#include <string.h>

#define ABI_SIZE(t, n) _Static_assert(sizeof(t) == (n), #t " size")
#define ABI_ALIGN(t, n) _Static_assert(_Alignof(t) == (n), #t " alignment")
#define ABI_OFFSET(t, f, n) _Static_assert(offsetof(t, f) == (n), #t "." #f)
ABI_SIZE(void*, 4);
ABI_SIZE(int, 4);
ABI_SIZE(long, 4);
ABI_SIZE(bool, 4); /* decomp enum, distinct from libctru's one-byte _Bool */
ABI_SIZE(EngineGate, 68); ABI_OFFSET(EngineGate, actual, 44);
ABI_SIZE(PAIR, 4);
ABI_SIZE(MATRIX, 32); ABI_ALIGN(MATRIX, 4); ABI_OFFSET(MATRIX, t, 20);
ABI_SIZE(SVECTOR, 8); ABI_ALIGN(SVECTOR, 2); ABI_OFFSET(SVECTOR, vz, 4);
ABI_SIZE(VECTOR, 16); ABI_ALIGN(VECTOR, 4);
ABI_SIZE(VECTOR3, 12); ABI_SIZE(SVECTOR3, 6);
ABI_SIZE(s_Pose, 20); ABI_OFFSET(s_Pose, rotation, 12);
ABI_SIZE(s_AnmBindPose, 6); ABI_ALIGN(s_AnmBindPose, 1);
ABI_SIZE(s_AnmHeader, 20); ABI_ALIGN(s_AnmHeader, 4);
ABI_OFFSET(s_AnmHeader, activeBones, 8);
ABI_OFFSET(s_AnmHeader, bindPoses, 20);
ABI_SIZE(s_FsMemBlock, 12); ABI_SIZE(s_FsMemState, 224);
ABI_OFFSET(s_FsMemBlock, next, 8);
ABI_SIZE(OT_TAG, 8); ABI_ALIGN(OT_TAG, 1);
ABI_SIZE(POLY_F3, 24); ABI_OFFSET(POLY_F3, x0, 12);
ABI_SIZE(s_Primitive, 20); ABI_ALIGN(s_Primitive, 2);
ABI_OFFSET(s_Primitive, field_6, 6);
ABI_SIZE(s_MeshHeader, 24); ABI_OFFSET(s_MeshHeader, primitives, 4);
ABI_SIZE(s_ModelHeader, 16); ABI_OFFSET(s_ModelHeader, meshHdrs, 12);
ABI_SIZE(s_LmHeader, 20); ABI_OFFSET(s_LmHeader, modelHdrs, 12);
ABI_SIZE(s_IpdCollSurface, 12); ABI_ALIGN(s_IpdCollSurface, 2);
ABI_SIZE(s_IpdCollSubcell, 10); ABI_SIZE(s_IpdHeader, 392);
ABI_OFFSET(s_IpdHeader, collisionData, 84);
_Static_assert(sizeof(s_GteScratchData) <= PSX_SCRATCHPAD_SIZE, "scratch capacity");

static void failure(EngineGate *r, uint32_t id, int32_t actual, int32_t expected)
{
    if (actual != expected && r->failed_test == 0) {
        r->failed_test = id;
        r->actual = actual;
        r->expected = expected;
    }
}

static void check(EngineGate *r, uint32_t id, int32_t actual, int32_t expected)
{
    ++r->gte_total;
    if (actual == expected) {
        ++r->gte_passed;
    } else
        failure(r, id, actual, expected);
}

void engine_gate_run(EngineGate *r)
{
    /* No assets, filesystem, renderer, or game state machine. */
    memset(r, 0, sizeof(*r));
    r->ram_bytes = sizeof(g_PsxRam);
    r->scratch_bytes = sizeof(g_PsxScratchpad);
    r->pointer_bytes = sizeof(void*);
    r->bool_bytes = sizeof(bool);
    g_PsxRam[0] = g_PsxRam[PSX_RAM_SIZE - 1] = 0xff;
    g_PsxScratchpad[PSX_SCRATCHPAD_SIZE - 1] = 0xff;
    PsxMemory_Init();
    uint32_t dirty = 0;
    for (uint32_t i = 0; i < PSX_RAM_SIZE; ++i)
        dirty |= g_PsxRam[i];
    r->memory_ok = dirty == 0 && ((uintptr_t)g_PsxRam & 7) == 0 &&
        PSX_ADDR(0x80001234) == g_PsxRam + 0x1234 &&
        PSX_ADDR(0xa0001234) == PSX_ADDR(0x1234) &&
        PSX_ADDR(0x80200000) == g_PsxRam &&
        PsxMemory_IsSpanValid(0x801fffff, 0x100001) &&
        !PsxMemory_IsSpanValid(0x801fffff, 0x100002) &&
        !PsxMemory_IsSpanValid(0, UINT32_MAX);
    if (!r->memory_ok)
        failure(r, 201, dirty ? (int32_t)dirty : -1, 0);
    dirty = 0;
    for (uint32_t i = 0; i < PSX_SCRATCHPAD_SIZE; ++i)
        dirty |= g_PsxScratchpad[i];
    r->scratch_ok = dirty == 0 && ((uintptr_t)g_PsxScratchpad & 7) == 0 &&
        PSX_SCRATCH_ADDR(0x3fc) == g_PsxScratchpad + 0x3fc;
    if (!r->scratch_ok)
        failure(r, 202, dirty ? (int32_t)dirty : -1, 0);
    const uint32_t endian = 0x04030201;
    const unsigned char anm_bytes[20] = {0x34,0x12,2,3, 0x20,0,4,0,
        1,0,0,0, 0x80,0,0,0, 0x10,0,1,2};
    s_AnmHeader anm;
    memcpy(&anm, anm_bytes, sizeof(anm));
    r->abi_ok = *(const unsigned char*)&endian == 1 && anm.dataOffset == 0x1234 &&
        anm.activeBones == 1 && anm.fileSize == 0x80 && anm.keyframeCount == 16;
    /* Packed resource bitfields are tested from bytes, never assumed from ILP32. */
    s_Primitive primitive = {0};
    primitive.field_6.flags = 0x8507;
    s_IpdCollSurface surface = {0};
    const unsigned char surface_bits[2] = {0xb1, 0x15};
    memcpy((unsigned char*)&surface + 6, surface_bits, 2);
    r->abi_ok &= primitive.field_6.bits.field_6_0 == 7 &&
        primitive.field_6.bits.materialIdx == 5 && primitive.field_6.bits.isTransparent == 1 &&
        surface.groundType == 17 && surface.disableHeight == 5 &&
        surface.field_6_8 == 5 && surface.field_6_11 == 2;
    failure(r, 203, r->abi_ok, 1);

    /* Real game utilities are retained by live calls, not discarded after compile. */
    Rng_SetSeed(0);
    const uint32_t first = Rng_Rand32();
    const uint32_t second = Rng_Rand32();
    failure(r, 101, first, 1013904223);
    failure(r, 102, second, 1196435762);
    u32 words[] = {1,2,3,4};
    Mem_Move32(words + 1, words, 12);
    failure(r, 103, words[1], 1);
    failure(r, 104, words[2], 2);
    failure(r, 105, words[3], 3);
    Fs_InitializeMem(FS_MEM_BASE, FS_MEM_SIZE);
    void *block = Fs_AllocMem(17);
    failure(r, 106, (uintptr_t)block, (uintptr_t)FS_MEM_BASE);
    r->core_ok = first == 1013904223u && second == 1196435762u &&
        words[1] == 1 && words[2] == 2 && words[3] == 3 && block == FS_MEM_BASE;
    const int freed = Fs_FreeMem(block);
    r->core_ok &= freed;
    failure(r, 107, freed, 1);

    memset(&gteRegs, 0, sizeof(gteRegs));
    InitGeom();
    MATRIX identity = {{{4096,0,0}, {0,4096,0}, {0,0,4096}}, {10,20,1024}};
    SetRotMatrix(&identity);
    SetTransMatrix(&identity);
    SVECTOR vertex = {64,32,0,0};
    VECTOR transformed = {0};
    long flag = 0;
    RotTrans(&vertex, &transformed, &flag);
    check(r, 1, transformed.vx, 74);
    check(r, 2, transformed.vy, 52);
    check(r, 3, transformed.vz, 1024);
    check(r, 4, flag, 0);
    SetGeomOffset(160,120);
    SetGeomScreen(256);
    SetDQA(0);
    SetDQB(0); /* Isolate projection from InitGeom's default depth-cue clamp. */
    identity.t[0] = identity.t[1] = 0;
    SetTransMatrix(&identity);
    int sxy = 0;
    long p = 0;
    int depth = RotTransPers(&vertex, &sxy, &p, &flag);
    check(r, 5, (int16_t)sxy, 176);
    check(r, 6, (int16_t)((uint32_t)sxy >> 16), 128);
    check(r, 7, depth, 256); /* SZ3 >> 2, PsyQ wrapper contract */
    check(r, 8, flag, 0);
    check(r, 9, NormalClip(0, 16, 16 << 16), 256);
    MTC2(3, 9); MTC2(4, 10); MTC2(12, 11);
    doCOP2(0x0a00428); /* SQR sf=0 */
    check(r, 10, MFC2(25), 9);
    check(r, 11, MFC2(26), 16);
    check(r, 12, MFC2(27), 144);

    /* Exercise halfword-aligned SVECTOR input, legal for its ABI. */
    _Alignas(4) unsigned char storage[12] = {0};
    memcpy(storage + 2, &vertex, sizeof(vertex));
    depth = RotTransPers((SVECTOR*)(storage + 2), &sxy, &p, &flag);
    check(r, 13, (int16_t)sxy, 176);
    check(r, 14, depth, 256);

    identity.t[0] = -10;
    identity.t[1] = 20;
    SetTransMatrix(&identity);
    SVECTOR negative = {-64,-32,0,0};
    RotTrans(&negative, &transformed, &flag);
    check(r, 15, transformed.vx, -74);
    check(r, 16, transformed.vy, -12);
    check(r, 17, transformed.vz, 1024);

    identity.t[0] = identity.t[1] = 0;
    SetTransMatrix(&identity);
    SVECTOR v0 = {-64,0,0,0}, v1 = {0,0,0,0};
    long sxy0 = 0, sxy1 = 0, sxy2 = 0;
    depth = RotTransPers3(&v0, &v1, &vertex, &sxy0, &sxy1, &sxy2, &p, &flag);
    check(r, 18, depth, 256);
    check(r, 19, (int16_t)sxy0, 144);
    check(r, 20, (int16_t)sxy1, 160);
    check(r, 21, (int16_t)sxy2, 176);
    check(r, 22, (int16_t)((uint32_t)sxy2 >> 16), 128);
    check(r, 23, flag, 0);
}
