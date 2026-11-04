#include "psx_tim.h"
#include <string.h>
static uint16_t le16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }
static uint32_t le32(const uint8_t *p) { return le16(p) | (uint32_t)le16(p + 2) << 16; }
static int read_at(PsxSource s, uint32_t off, void *p, uint32_t n)
{
    if (!s.read || off > s.bytes || n > s.bytes - off) return PV_BOUNDS;
    return s.read(s.context, off, p, n) ? PV_IO : PV_OK;
}
static int block(PsxSource s, uint32_t off, PsxRect *r, uint32_t *payload, uint32_t *bytes, uint32_t *end)
{
    uint8_t h[12];
    int result = read_at(s, off, h, sizeof(h));
    if (result) return result;
    uint32_t length = le32(h);
    *r = (PsxRect){le16(h + 4), le16(h + 6), le16(h + 8), le16(h + 10)};
    if (!psx_vram_rect_valid(*r)) return PV_BOUNDS;
    *bytes = (uint32_t)r->w * r->h * 2;
    if (length != 12 + *bytes || length > s.bytes - off) return PV_FORMAT;
    *payload = off + 12; *end = off + length;
    return PV_OK;
}
int psx_tim_parse(PsxSource s, PsxTim *out)
{
    if (!out) return PV_BOUNDS;
    memset(out, 0, sizeof(*out));
    uint8_t h[8];
    int result = read_at(s, 0, h, sizeof(h));
    if (result) return result;
    if (le32(h) != 0x10 || (le32(h + 4) & ~15u)) return PV_FORMAT;
    PsxTim t = {0};
    t.flags = le32(h + 4); t.mode = t.flags & 7; t.has_clut = !!(t.flags & 8);
    if (t.mode > 2) return PV_MODE;
    uint32_t off = 8;
    if (t.has_clut) {
        result = block(s, off, &t.clut, &t.clut_offset, &t.clut_bytes, &off);
        if (result) return result;
        t.palette_entries = t.mode == 0 ? 16 : 256;
        if (t.mode == 2 || t.clut.x % 16 || t.clut.w % t.palette_entries) return PV_FORMAT;
        t.palette_count = t.clut.w / t.palette_entries * t.clut.h;
    }
    result = block(s, off, &t.image, &t.image_offset, &t.image_bytes, &off);
    if (result) return result;
    t.width = t.image.w * (4u >> t.mode); t.height = t.image.h; t.consumed = off;
    *out = t;
    return PV_OK;
}
static int upload_block(PsxVram *v, PsxSource s, uint32_t offset, PsxRect r)
{
    uint8_t row[2048];
    for (unsigned y = 0; y < r.h; ++y) {
        int result = read_at(s, offset + y * r.w * 2u, row, r.w * 2u);
        if (result) return result;
        result = psx_vram_load(v, (PsxRect){r.x, r.y + y, r.w, 1}, row, r.w * 2u);
        if (result) return result;
    }
    return PV_OK;
}
int psx_tim_upload(PsxVram *v, PsxSource s, const PsxTim *t, const PsxRect *image, const PsxRect *clut)
{
    if (!v || !t) return PV_BOUNDS;
    /* Revalidate metadata, so forged/stale structs cannot bypass parse bounds. */
    PsxTim checked;
    int result = psx_tim_parse(s, &checked);
    if (result) return result;
    if (memcmp(&checked, t, sizeof(checked))) return PV_FORMAT;
    PsxRect i = image ? *image : t->image, c = clut ? *clut : t->clut;
    if (!psx_vram_rect_valid(i) || i.w != t->image.w || i.h != t->image.h ||
        (t->has_clut && (!psx_vram_rect_valid(c) || c.x % 16 || c.w != t->clut.w || c.h != t->clut.h))) return PV_BOUNDS;
    /* Matches the game's image-then-CLUT LoadImage order. IO errors can leave
     * a partial upload; generation changes for each modified row. */
    result = upload_block(v, s, t->image_offset, i);
    if (!result && t->has_clut) result = upload_block(v, s, t->clut_offset, c);
    return result;
}
int psx_tim_region(const PsxTim *t, PsxRect i, PsxRect c, unsigned palette, PsxTextureRegion *out)
{
    if (!t || !out || t->mode > 2 || !psx_vram_rect_valid(i) ||
        i.w != t->image.w || i.h != t->image.h) return PV_BOUNDS;
    if (t->mode != 2) {
        unsigned entries = t->mode == 0 ? 16 : 256;
        if (!t->has_clut || !psx_vram_rect_valid(c) || c.x % 16 || c.w % entries ||
            c.w != t->clut.w || c.h != t->clut.h || palette >= (unsigned)c.w / entries * c.h) return PV_BOUNDS;
        unsigned per_row = c.w / entries;
        c.x += (palette % per_row) * entries; c.y += palette / per_row;
    }
    *out = (PsxTextureRegion){i, (uint16_t)((c.y << 6) | (c.x >> 4)), t->mode};
    return psx_region_valid(*out) ? PV_OK : PV_BOUNDS;
}
