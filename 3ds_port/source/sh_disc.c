#include "sh_disc.h"
#ifdef SH_3DS_GAME
#include "game_io.h"
#endif
#include <string.h>
#include "disc_gate.h"
#define SH_IDENTITY_ONLY
#include "disc_reference.h"

static uint32_t le32(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

int ShDisc_ReadBytes(PsxDisc *d, uint32_t lba, uint32_t off, void *out, uint32_t bytes)
{
    if (!d || !d->file || (!out && bytes) || (uint64_t)lba * 2048 + off + bytes > (uint64_t)d->sectors * 2048) return PD_RANGE;
    uint8_t sector[2048], *p = out;
    lba += off / 2048; off %= 2048;
    while (bytes) {
        int result = PsxDisc_ReadDataSector(d, lba++, sector);
        if (result != PD_OK) return result;
        uint32_t n = 2048 - off;
        if (n > bytes) n = bytes;
        memcpy(p, sector + off, n);
#ifdef SH_3DS_GAME
        game_io_data(n);
#endif
        p += n; bytes -= n; off = 0;
    }
    return PD_OK;
}

int ShDisc_Checksum(PsxDisc *d, uint32_t lba, uint32_t off, uint32_t bytes, uint32_t *crc)
{
    if (!crc) return PD_RANGE;
    uint8_t data[2048];
    uint32_t sum = 0;
    while (bytes) {
        uint32_t n = bytes > sizeof(data) ? sizeof(data) : bytes;
        int r = ShDisc_ReadBytes(d, lba, off, data, n);
        if (r != PD_OK) return r;
        sum = PsxDisc_Crc32(sum, data, n);
        bytes -= n; off += n;
    }
    *crc = sum;
    return PD_OK;
}

static int record(PsxDisc *d, const uint8_t *r, ShDiscFile *out)
{
    uint32_t lba = le32(r + 2), bytes = le32(r + 10);
    if (r[1] || r[26] || r[27] || (r[25] & 0x80) ||
        r[2] != r[9] || r[3] != r[8] || r[4] != r[7] || r[5] != r[6] ||
        r[10] != r[17] || r[11] != r[16] || r[12] != r[15] || r[13] != r[14] ||
        (uint64_t)lba * 2048 + bytes > (uint64_t)d->sectors * 2048) return PD_FORMAT;
    *out = (ShDiscFile){lba, bytes};
    return PD_OK;
}

int ShDisc_FindIso(PsxDisc *d, const char *path, ShDiscFile *out)
{
    if (!d || !path || !out) return PD_RANGE;
    uint8_t sector[2048];
    int r = PsxDisc_ReadDataSector(d, 16, sector);
    if (r != PD_OK) return r;
    if (memcmp(sector, "\1CD001\1", 7) || sector[156] < 34) return PD_FORMAT;
    ShDiscFile dir;
    r = record(d, sector + 156, &dir);
    if (r != PD_OK) return r;
    if (!strncmp(path, "cdrom:", 6)) path += 6;
    while (*path == '\\' || *path == '/') ++path;
    for (unsigned depth = 0; depth < 8 && *path; ++depth) {
        const char *end = path;
        while (*end && *end != '\\' && *end != '/') ++end;
        size_t len = (size_t)(end - path);
        if (!len || len > 64 || dir.bytes > 1024 * 1024) return PD_FORMAT;
        int found = 0;
        for (uint32_t off = 0; off < dir.bytes && !found; off += 2048) {
            r = PsxDisc_ReadDataSector(d, dir.lba + off / 2048, sector);
            if (r != PD_OK) return r;
            uint32_t limit = dir.bytes - off < 2048 ? dir.bytes - off : 2048;
            for (uint32_t pos = 0; pos < limit && sector[pos]; ) {
                const uint8_t *e = sector + pos;
                uint32_t n = e[0];
                if (n < 34 || pos + n > limit || 33u + e[32] > n) return PD_FORMAT;
                if (e[32] == len && !memcmp(e + 33, path, len)) {
                    if ((*end && !(e[25] & 2)) || (!*end && (e[25] & 2))) return PD_FORMAT;
                    r = record(d, e, &dir);
                    if (r != PD_OK) return r;
                    found = 1; break;
                }
                pos += n;
            }
        }
        if (!found) return PD_NOT_FOUND;
        if (!*end) { *out = dir; return PD_OK; }
        path = end + 1;
    }
    return PD_FORMAT;
}

int ShDisc_Init(ShDisc *s, PsxDisc *d)
{
    if (!s || !d || !d->file) return PD_RANGE;
    memset(s, 0, sizeof(*s)); s->disc = d;
    strcpy(s->detected, "unknown image");
    ShDiscFile exe = {0, 0};
    if (ShDisc_FindIso(d, "SLUS_007.07;1", &exe) == PD_OK)
        strcpy(s->detected, "SLUS-00707 / unknown revision");
    if (d->image_bytes != SH_DISC_BYTES || exe.lba != SH_EXE_LBA || exe.bytes != SH_EXE_BYTES)
        return PD_UNSUPPORTED;
    for (unsigned i = 0; i < sizeof(sh_identity)/sizeof(sh_identity[0]); ++i) {
        const DiscReference *ref = &sh_identity[i];
        uint32_t crc = 0;
        int r = ShDisc_Checksum(d, ref->lba, 0, ref->bytes, &crc);
        s->identity_actual[s->identity_count++] = crc;
        if (r != PD_OK || crc != ref->crc) {
            s->failed_identity = 100 + i; s->expected = ref->crc; s->actual = crc;
            return PD_UNSUPPORTED;
        }
    }
    uint32_t crc = 0;
    int table_status = ShDisc_Checksum(d, SH_EXE_LBA, SH_TABLE_OFFSET, 2074u * 12, &crc);
    s->identity_actual[s->identity_count++] = crc;
    if (table_status != PD_OK || crc != SH_TABLE_CRC) {
        s->failed_identity = 104; s->expected = SH_TABLE_CRC; s->actual = crc;
        return PD_UNSUPPORTED;
    }
    strcpy(s->detected, "USA SLUS-00707 v1.1");
    s->supported = 1;
    return PD_OK;
}

int ShDisc_Resolve(ShDisc *s, uint32_t id, ShDiscFile *out)
{
    if (!s || !s->supported || !out || id >= 2074) return PD_RANGE;
    uint8_t entry[12];
    int r = ShDisc_ReadBytes(s->disc, SH_EXE_LBA, SH_TABLE_OFFSET + id * 12, entry, sizeof(entry));
    if (r != PD_OK) return r;
    uint32_t word = le32(entry);
    ShDiscFile f = {word & 0x7ffffu, ((word >> 19) & 0xfffu) * 256u};
    if ((uint64_t)f.lba * 2048 + f.bytes > (uint64_t)s->disc->sectors * 2048) return PD_RANGE;
    *out = f;
    return PD_OK;
}

int ShDisc_Read(ShDisc *s, const ShDiscFile *f, uint32_t off, void *out, uint32_t bytes)
{
    if (!s || !s->supported || !f || off > f->bytes || bytes > f->bytes - off) return PD_RANGE;
    return ShDisc_ReadBytes(s->disc, f->lba, off, out, bytes);
}
