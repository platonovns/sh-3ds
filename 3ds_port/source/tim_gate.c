#include "tim_gate.h"
#include "sh_disc.h"
#include "tim_reference.h"
#include <errno.h>
#include <string.h>
typedef struct { ShDisc *disc; ShDiscFile file; } ResourceSource;
static int resource_read(void *ctx, uint32_t offset, void *out, uint32_t bytes)
{
    ResourceSource *r = ctx;
    return ShDisc_Read(r->disc, &r->file, offset, out, bytes);
}
const char *tim_gate_name(unsigned index) { return index == 0 ? "2ZANKO80.TIM" : "FONT16.TIM"; }
static int check(TimGate *g, uint32_t id, uint32_t expected, uint32_t actual)
{
    if (expected == actual) return 1;
    if (!g->first_failure) { g->first_failure = id; g->expected = expected; g->actual = actual; }
    return 0;
}
int tim_gate_decode_row(const PsxVram *v, PsxTextureRegion r, unsigned y, uint8_t *rgba, unsigned width)
{
    if (!v || !rgba || !psx_region_valid(r) || width != (unsigned)r.image.w * (4u >> r.mode) || y >= r.image.h)
        return PV_BOUNDS;
    for (unsigned x = 0; x < width; ++x) {
        PsxTexel t;
        int result = psx_vram_texel(v, r, x, y, &t);
        if (result) return result;
        memcpy(rgba + x * 4, t.rgba, 4);
    }
    return PV_OK;
}
static uint16_t le16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }
static uint32_t le32(const uint8_t *p) { return le16(p) | (uint32_t)le16(p + 2) << 16; }
int tim_gate_anm(PsxSource s, AnmAudit *out)
{
    if (!out) return PV_BOUNDS;
    memset(out, 0, sizeof(*out));
    uint8_t h[20];
    if (!s.read || s.bytes < sizeof(h)) return PV_BOUNDS;
    if (s.read(s.context, 0, h, sizeof(h))) return PV_IO;
    AnmAudit a = {0};
    a.data_offset = le16(h); a.rotation_bones = h[2]; a.translation_bones = h[3];
    a.stride = le16(h + 4); a.bones = h[6]; a.active_mask = le32(h + 8);
    a.declared_bytes = le32(h + 12); a.frames = le16(h + 16); a.scale = h[18]; a.root_y = h[19];
    if (!a.bones || a.bones > 32 || !a.frames || a.data_offset < 20 + a.bones * 6 ||
        a.declared_bytes > s.bytes || a.data_offset > a.declared_bytes ||
        a.stride != a.rotation_bones * 9 + a.translation_bones * 3 ||
        a.data_offset + a.stride * a.frames != a.declared_bytes || a.scale > 12) return PV_BOUNDS;
    for (unsigned b = 0; b < a.bones; ++b) {
        uint8_t pose[6];
        if (s.read(s.context, 20 + b * 6, pose, 6)) return PV_IO;
        int parent = (int8_t)pose[0], rotation = (int8_t)pose[1], translation = (int8_t)pose[2];
        if (parent < -1 || parent >= (int)a.bones || rotation < -1 || rotation >= (int)a.rotation_bones ||
            translation < -1 || translation >= (int)a.translation_bones) return PV_BOUNDS;
    }
    a.passed = 1; *out = a;
    return PV_OK;
}
void tim_gate_run(TimGate *g, PsxVram *v, const char *bin, const char *cue)
{
    if (!g || !v) return;
    memset(g, 0, sizeof(*g)); psx_vram_init(v); g->shadow_ok = 1;
    PsxDisc disc;
    g->open_status = PsxDisc_Open(&disc, bin, cue);
    if (!check(g, 300, 0, g->open_status)) return;
    ShDisc sh;
    g->identity_status = ShDisc_Init(&sh, &disc);
    if (!check(g, 301, 0, g->identity_status)) { PsxDisc_Close(&disc); return; }
    for (unsigned i = 0; i < 2; ++i) {
        TimResourceGate *r = &g->resources[i];
        r->file_id = i ? 6 : 0;
        ResourceSource context = {&sh, {0}};
        r->status = ShDisc_Resolve(&sh, r->file_id, &context.file);
        if (!check(g, 310 + i * 20, 0, r->status)) continue;
        r->bytes = context.file.bytes;
        if (!check(g, 311 + i * 20, i ? 8448 : 77568, r->bytes)) continue;
        r->status = ShDisc_Checksum(&disc, context.file.lba, 0, r->bytes, &r->crc);
        if (!check(g, 312 + i * 20, 0, r->status) || !check(g, 313 + i * 20, tim_reference[i][0], r->crc)) continue;
        r->passed |= TG_CRC;
        PsxSource source = {resource_read, &context, r->bytes};
        r->status = psx_tim_parse(source, &r->tim);
        if (!check(g, 314 + i * 20, 0, r->status)) continue;
        r->passed |= TG_PARSE;
        PsxTim *t = &r->tim;
        r->image_destination = (PsxRect){640, i ? 256 : 0, t->image.w, t->image.h};
        r->clut_destination = (PsxRect){0, i ? 481 : 480, t->clut.w, t->clut.h};
        PsxTextureRegion region;
        r->status = psx_tim_region(t, r->image_destination, r->clut_destination, 0, &region);
        if (!check(g, 315 + i * 20, 0, r->status)) continue;
        r->passed |= TG_BOUNDS;
        r->status = psx_tim_upload(v, source, t, &r->image_destination, &r->clut_destination);
        if (!check(g, 316 + i * 20, 0, r->status)) continue;
        r->passed |= TG_UPLOAD; r->generation = v->generation;
        r->vram_crc = psx_vram_crc(v);
        if (!check(g, 317 + i * 20, tim_reference[i][1], r->vram_crc)) continue;
        r->passed |= TG_VRAM;
        uint8_t row[4096];
        if (!check(g, 318 + i * 20, 1, t->width <= sizeof(row) / 4)) continue;
        for (unsigned y = 0; y < t->height; ++y) {
            r->status = tim_gate_decode_row(v, region, y, row, t->width);
            if (r->status) break;
            r->decoded_crc = PsxDisc_Crc32(r->decoded_crc, row, t->width * 4);
            for (unsigned x = 0; x < t->width; ++x) {
                PsxTexel texel;
                psx_vram_texel(v, region, x, y, &texel);
                r->stp_texels += texel.stp; r->transparent_texels += texel.transparent;
            }
        }
        if (check(g, 319 + i * 20, 0, r->status) &&
            check(g, 350 + i, tim_reference[i][2], r->decoded_crc) &&
            check(g, 352 + i, tim_reference[i][3], r->stp_texels)) r->passed |= TG_DECODE;
    }
    ResourceSource context = {&sh, {0}};
    int result = ShDisc_Resolve(&sh, 19, &context.file);
    if (check(g, 360, 0, result)) {
        uint32_t crc = 0;
        result = ShDisc_Checksum(&disc, context.file.lba, 0, context.file.bytes, &crc);
        if (check(g, 361, 0, result) && check(g, 362, 0x6da30665, crc)) {
            result = tim_gate_anm((PsxSource){resource_read, &context, context.file.bytes}, &g->anm);
            g->anm.crc = crc;
            check(g, 363, 0, result);
        }
    }
    PsxDisc_Close(&disc);
}
int tim_gate_log(const TimGate *g, const char *path)
{
    FILE *f = fopen(path, "w");
    if (!f) return errno ? errno : EIO;
    int ok = fprintf(f, "Stage 3 Real TIM / PSX VRAM\nOpen=%ld identity=%ld shadow=%lu\n",
                     (long)g->open_status, (long)g->identity_status, (unsigned long)g->shadow_ok) >= 0;
    for (unsigned i = 0; i < 2; ++i) {
        const TimResourceGate *r = &g->resources[i]; const PsxTim *t = &r->tim;
        if (fprintf(f, "%s id=%lu bytes=%lu crc=%08lX stages=%02lX status=%ld\n"
                    "TIM flags=%lu mode=%lu CLUT=%lu logical=%lux%lu consumed=%lu\n"
                    "Image authored=%u,%u %ux%u words; destination=%u,%u\n"
                    "CLUT authored=%u,%u %ux%u; destination=%u,%u entries=%lu palettes=%lu\n"
                    "VRAM=%08lX generation=%lu decoded=%08lX STP=%lu transparent=%lu\n",
                    tim_gate_name(i), (unsigned long)r->file_id, (unsigned long)r->bytes,
                    (unsigned long)r->crc, (unsigned long)r->passed, (long)r->status,
                    (unsigned long)t->flags, (unsigned long)t->mode, (unsigned long)t->has_clut,
                    (unsigned long)t->width, (unsigned long)t->height, (unsigned long)t->consumed,
                    t->image.x, t->image.y, t->image.w, t->image.h, r->image_destination.x, r->image_destination.y,
                    t->clut.x, t->clut.y, t->clut.w, t->clut.h, r->clut_destination.x, r->clut_destination.y,
                    (unsigned long)t->palette_entries, (unsigned long)t->palette_count,
                    (unsigned long)r->vram_crc, (unsigned long)r->generation, (unsigned long)r->decoded_crc,
                    (unsigned long)r->stp_texels, (unsigned long)r->transparent_texels) < 0) ok = 0;
    }
    if (fprintf(f, "ANM audit=%lu offset=%lu stride=%lu frames=%lu bytes=%lu bones=%lu\n"
                   "First FAIL=%lu expected=%08lX actual=%08lX\nCPU result=%s\n",
                (unsigned long)g->anm.passed, (unsigned long)g->anm.data_offset, (unsigned long)g->anm.stride,
                (unsigned long)g->anm.frames, (unsigned long)g->anm.declared_bytes, (unsigned long)g->anm.bones,
                (unsigned long)g->first_failure, (unsigned long)g->expected, (unsigned long)g->actual,
                g->first_failure ? "FAIL" : "PASS") < 0) ok = 0;
    if (fflush(f)) ok = 0;
    if (fclose(f)) ok = 0;
    return ok ? 0 : EIO;
}
