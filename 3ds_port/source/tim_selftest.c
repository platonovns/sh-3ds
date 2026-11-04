#include "tim_selftest.h"
#include <string.h>
typedef struct { uint8_t bytes[1100]; uint32_t size, fail_offset; } Fixture;
static void w16(uint8_t *p, unsigned n) { p[0] = n; p[1] = n >> 8; }
static void w32(uint8_t *p, unsigned n) { w16(p, n); w16(p + 2, n >> 16); }
static int read_fixture(void *ctx, uint32_t offset, void *out, uint32_t bytes)
{
    Fixture *f = ctx;
    if (offset > f->size || bytes > f->size - offset || offset == f->fail_offset) return -1;
    memcpy(out, f->bytes + offset, bytes); return 0;
}
static void make_fixture(Fixture *f, unsigned mode, unsigned palettes)
{
    memset(f, 0, sizeof(*f)); f->fail_offset = UINT32_MAX;
    w32(f->bytes, 0x10); w32(f->bytes + 4, mode | (mode < 2 ? 8 : 0));
    unsigned off = 8;
    if (mode < 2) {
        unsigned entries = mode ? 256 : 16, count = entries * palettes;
        w32(f->bytes + off, 12 + count * 2); w16(f->bytes + off + 4, 16);
        w16(f->bytes + off + 6, 480); w16(f->bytes + off + 8, entries);
        w16(f->bytes + off + 10, palettes);
        for (unsigned i = 0; i < count; ++i) w16(f->bytes + off + 12 + i * 2, i);
        off += 12 + count * 2;
    }
    w32(f->bytes + off, 16); w16(f->bytes + off + 4, 200); w16(f->bytes + off + 6, 100);
    w16(f->bytes + off + 8, 2); w16(f->bytes + off + 10, 1);
    w16(f->bytes + off + 12, mode == 0 ? 0x3210 : mode == 1 ? 0x0100 : 0x001f);
    w16(f->bytes + off + 14, mode == 0 ? 0x7654 : mode == 1 ? 0xff80 : 0x8000);
    f->size = off + 16;
}
static void test(TimSelftest *t, uint32_t expected, uint32_t actual)
{
    ++t->total;
    if (expected == actual) ++t->passed;
    else if (!t->first_failure) {
        t->first_failure = t->total; t->expected = expected; t->actual = actual;
    }
}
void tim_selftest_run(PsxVram *v, TimSelftest *t)
{
    memset(t, 0, sizeof(*t));
    Fixture f;
    PsxTim tim;
    PsxTextureRegion region;
    uint8_t rgba[32], out[8];
    for (unsigned mode = 0; mode < 3; ++mode) {
        make_fixture(&f, mode, 1); PsxSource s = {read_fixture, &f, f.size};
        test(t, 0, psx_tim_parse(s, &tim)); test(t, mode, tim.mode);
        test(t, 2 * (4u >> mode), tim.width); test(t, 1, tim.height);
        test(t, mode < 2, tim.has_clut);
        psx_vram_init(v);
        test(t, 0, psx_tim_upload(v, s, &tim, NULL, NULL));
        test(t, 0, psx_tim_region(&tim, tim.image, tim.clut, 0, &region));
        memset(f.bytes, 0xee, f.size); /* Decode must not retain TIM pointers. */
        test(t, 0, psx_vram_decode(v, region, rgba, sizeof(rgba)));
        test(t, mode == 2 ? 255 : 0, rgba[0]);
        test(t, mode == 2 ? 255 : 0, rgba[3]);
        for (unsigned x = 0; x < tim.width; ++x) {
            PsxTexel decoded;
            test(t, 0, psx_vram_texel(v, region, x, 0, &decoded));
            unsigned expected = mode == 0 ? x : mode == 1 ? (x < 2 ? x : x == 2 ? 128 : 255) : x == 0 ? 0x1f : 0x8000;
            test(t, expected, decoded.word);
        }
        test(t, PV_BOUNDS, psx_vram_decode(v, region, rgba, 1));
        test(t, PV_BOUNDS, psx_vram_texel(v, region, tim.width, 0, &(PsxTexel){0}));
    }
    PsxTexel pixel;
    psx_color_decode(0, &pixel); test(t, 1, pixel.transparent); test(t, 0, pixel.stp);
    psx_color_decode(0x8000, &pixel); test(t, 0, pixel.transparent); test(t, 1, pixel.stp); test(t, 255, pixel.rgba[3]);
    psx_color_decode(0x03e0, &pixel); test(t, 255, pixel.rgba[1]); test(t, 0, pixel.rgba[0]);
    psx_color_decode(0x7c00, &pixel); test(t, 255, pixel.rgba[2]);
    psx_color_decode(0x4210, &pixel); test(t, 132, pixel.rgba[0]);
    make_fixture(&f, 0, 2); PsxSource s = {read_fixture, &f, f.size};
    test(t, 0, psx_tim_parse(s, &tim)); test(t, 2, tim.palette_count);
    psx_vram_init(v); test(t, 0, psx_tim_upload(v, s, &tim, NULL, NULL));
    test(t, 0, psx_tim_region(&tim, tim.image, tim.clut, 1, &region));
    test(t, 0, psx_vram_texel(v, region, 1, 0, &pixel)); test(t, 17, pixel.word);
    test(t, PV_BOUNDS, psx_tim_region(&tim, tim.image, tim.clut, 2, &region));
    /* Multiple palettes horizontally as well as vertically. */
    w16(f.bytes + 16, 32); w16(f.bytes + 18, 1);
    test(t, 0, psx_tim_parse(s, &tim)); test(t, 2, tim.palette_count);
    test(t, 0, psx_tim_upload(v, s, &tim, NULL, NULL));
    test(t, 0, psx_tim_region(&tim, tim.image, tim.clut, 1, &region));
    test(t, 0, psx_vram_texel(v, region, 1, 0, &pixel)); test(t, 17, pixel.word);
    uint8_t red[2] = {31, 0}; uint32_t generation = v->generation;
    test(t, 0, psx_vram_load(v, (PsxRect){33, 480, 1, 1}, red, 2));
    test(t, generation + 1, v->generation);
    test(t, 0, psx_vram_texel(v, region, 1, 0, &pixel)); test(t, 31, pixel.word);
    const uint8_t words[8] = {1,0,2,0,3,0,4,0};
    test(t, 0, psx_vram_load(v, (PsxRect){10,10,2,2}, words, 8));
    test(t, 0, psx_vram_move(v, (PsxRect){10,10,2,2}, 11,11));
    test(t, 0, psx_vram_store(v, (PsxRect){11,11,2,2}, out, 8)); test(t, 0, memcmp(words, out, 8));
    test(t, 0, psx_vram_move(v, (PsxRect){11,11,2,2}, 10,10));
    test(t, 0, psx_vram_store(v, (PsxRect){10,10,2,2}, out, 8)); test(t, 0, memcmp(words, out, 8));
    generation = v->generation;
    test(t, PV_BOUNDS, psx_vram_load(v, (PsxRect){1023,511,2,1}, words, 8));
    test(t, PV_BOUNDS, psx_vram_move(v, (PsxRect){10,10,2,2}, 1023,511));
    test(t, PV_BOUNDS, psx_vram_store(v, (PsxRect){0,0,2,2}, out, 7));
    test(t, generation, v->generation);
    make_fixture(&f, 1, 1); s.bytes = f.size;
    test(t, 0, psx_tim_parse(s, &tim));
    PsxRect bad = {1023,511,2,2};
    test(t, PV_BOUNDS, psx_tim_upload(v, s, &tim, &bad, NULL)); test(t, generation, v->generation);
    for (uint32_t n = 0; n < f.size; ++n) {
        s.bytes = n; test(t, 1, psx_tim_parse(s, &tim) != PV_OK);
    }
    s.bytes = f.size;
    w32(f.bytes, 0x110); test(t, PV_FORMAT, psx_tim_parse(s, &tim)); w32(f.bytes, 0x10);
    w32(f.bytes + 4, 0x19); test(t, PV_FORMAT, psx_tim_parse(s, &tim));
    w32(f.bytes + 4, 3); test(t, PV_MODE, psx_tim_parse(s, &tim)); w32(f.bytes + 4, 9);
    w32(f.bytes + 8, 0xffffffff); test(t, PV_FORMAT, psx_tim_parse(s, &tim)); w32(f.bytes + 8, 524);
    w16(f.bytes + 12, 1023); test(t, PV_BOUNDS, psx_tim_parse(s, &tim)); w16(f.bytes + 12, 16);
    w16(f.bytes + 12, 17); test(t, PV_FORMAT, psx_tim_parse(s, &tim)); w16(f.bytes + 12, 16);
    w16(f.bytes + 14, 512); test(t, PV_BOUNDS, psx_tim_parse(s, &tim)); w16(f.bytes + 14, 480);
    w16(f.bytes + 16, 255); test(t, PV_FORMAT, psx_tim_parse(s, &tim)); w16(f.bytes + 16, 256);
    w16(f.bytes + 536, 1024); test(t, PV_BOUNDS, psx_tim_parse(s, &tim)); w16(f.bytes + 536, 200);
    test(t, 0, psx_tim_parse(s, &tim));
    f.fail_offset = tim.image_offset;
    test(t, PV_IO, psx_tim_upload(v, s, &tim, NULL, NULL));
    f.fail_offset = tim.clut_offset; generation = v->generation;
    test(t, PV_IO, psx_tim_upload(v, s, &tim, NULL, NULL));
    test(t, generation + 1, v->generation); /* Partial image write invalidates. */
    f.fail_offset = 0; test(t, PV_IO, psx_tim_parse(s, &tim));
    f.fail_offset = UINT32_MAX; test(t, 0, psx_tim_parse(s, &tim));
    ++tim.image_offset; test(t, PV_FORMAT, psx_tim_upload(v, s, &tim, NULL, NULL));
}
