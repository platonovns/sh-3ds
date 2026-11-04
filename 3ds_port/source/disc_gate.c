#include "disc_gate.h"
#include "sh_disc.h"
#include "psyq_file.h"
#include <errno.h>
#include <inttypes.h>
#include <string.h>
#define SH_READS_ONLY
#include "disc_reference.h"

static uint64_t stamp(DiscClockUs clock) { return clock ? clock() : 0; }
static uint32_t elapsed(DiscClockUs clock, uint64_t start)
{
    uint64_t n = stamp(clock) - start;
    return n > UINT32_MAX ? UINT32_MAX : (uint32_t)n;
}

uint32_t disc_gate_msf_tests(uint32_t *total)
{
    static const struct { int32_t lba; PsxMsf msf; } cases[] = {
        {-150,{0,0,0}}, {-1,{0,1,0x74}}, {0,{0,2,0}}, {74,{0,2,0x74}},
        {75,{0,3,0}}, {4350,{1,0,0}}, {131057,{0x29,9,0x32}},
        {262114,{0x58,0x16,0x64}}, {449849,{0x99,0x59,0x74}}
    };
    uint32_t passed = 0;
    for (unsigned i = 0; i < sizeof(cases)/sizeof(cases[0]); ++i) {
        PsxMsf msf;
        int32_t lba = 0;
        if (PsxDisc_LbaToMsf(cases[i].lba, &msf) == PD_OK && !memcmp(&msf, &cases[i].msf, 3) &&
            PsxDisc_MsfToLba(&msf, &lba) == PD_OK && lba == cases[i].lba) ++passed;
    }
    PsxMsf invalid[] = {{0x0a,0,0}, {0,0x60,0}, {0,0,0x75}, {0,0xfa,0}};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) {
        int32_t lba;
        if (PsxDisc_MsfToLba(&invalid[i], &lba) == PD_RANGE) ++passed;
    }
    PsxMsf msf;
    if (PsxDisc_LbaToMsf(-151, &msf) == PD_RANGE) ++passed;
    if (PsxDisc_LbaToMsf(449850, &msf) == PD_RANGE) ++passed;
    *total = 15;
    return passed;
}

static void fail(DiscGate *g, uint32_t id, uint32_t expected, uint32_t actual)
{
    if (g->first_failure) return;
    g->first_failure = id; g->expected = expected; g->actual = actual;
}

static int log_results(const DiscGate *g, const char *path)
{
    FILE *f = path ? fopen(path, "w") : NULL;
    if (!f) return errno ? errno : EIO;
    int ok = fprintf(f,
        "Silent Hill Stage 2 lower disc/FS gate (no gameplay)\n"
        "DISC found=%"PRIu32" open=%"PRId32" identity=%"PRId32" detected=%s\n"
        "CUE parsed=%"PRIu32" tracks=%"PRIu32" mode=%"PRIu32" raw=%"PRIu32"\n"
        "bytes=%"PRIu32" sectors=%"PRIu32"; BIN byte offset = LBA * 2352\n"
        "Form1 data offset=24 bytes=2048; Form2 raw only; MSF BCD = LBA+150\n"
        "MSF=%"PRIu32"/%"PRIu32" raw=%"PRIu32"/%"PRIu32" data=%"PRIu32"/%"PRIu32" FS=%"PRIu32"/%"PRIu32"\n"
        "first_failure=%"PRIu32" expected=%08"PRIX32" actual=%08"PRIX32"\n"
        "identity_us=%"PRIu32" random_us=%"PRIu32" sequential_us=%"PRIu32" sequential_sectors=%"PRIu32"\n",
        g->found,g->open_status,g->identity_status,g->detected,g->cue_parsed,g->tracks,g->mode,g->sector_bytes,
        g->image_bytes,g->sectors,g->msf_pass,g->msf_total,g->raw_pass,g->raw_total,g->data_pass,g->data_total,
        g->fs_pass,g->fs_total,g->first_failure,g->expected,g->actual,g->identity_us,g->random_us,g->sequential_us,g->sequential_sectors) >= 0;
    for (uint32_t i = 0; i < g->test_count; ++i) {
        const DiscReadResult *r = &g->reads[i];
        if (fprintf(f,"test=%"PRIu32" lba=%"PRIu32" bytes=%"PRIu32" expected=%08"PRIX32" actual=%08"PRIX32" us=%"PRIu32" status=%"PRId32" %s\n",
                    r->id,r->lba,r->bytes,r->expected,r->actual,r->us,r->status,
                    r->status == PD_OK && r->expected == r->actual ? "PASS" : "FAIL") < 0) ok = 0;
    }
    static const uint32_t expected_identity[5] = {0x27bb3453, 0xc40662e8, 0x1f1a87cc, 0x1c2b2258, SH_TABLE_CRC};
    for (uint32_t i = 0; i < g->identity_count; ++i) {
        if (fprintf(f,"identity_test=%"PRIu32" expected=%08"PRIX32" actual=%08"PRIX32" %s\n",
                    100+i, expected_identity[i], g->identity_actual[i],
                    expected_identity[i] == g->identity_actual[i] ? "PASS" : "FAIL") < 0) ok = 0;
    }
    if (fprintf(f,"RESULT: %s\n",g->open_status == PD_OK && g->identity_status == PD_OK && !g->first_failure ? "PASS" : "FAIL") < 0) ok = 0;
    if (fflush(f)) ok = 0;
    if (fclose(f)) ok = 0;
    return ok ? 0 : EIO;
}

void disc_gate_run(DiscGate *g, const char *bin, const char *cue, const char *log, DiscClockUs clock)
{
    memset(g, 0, sizeof(*g));
    g->identity_status = PD_UNSUPPORTED;
    strcpy(g->detected, "not detected");
    g->msf_pass = disc_gate_msf_tests(&g->msf_total);
    if (g->msf_pass != g->msf_total) fail(g, 200, g->msf_total, g->msf_pass);
    PsxDisc d;
    ShDisc sh;
    uint8_t buffer[2352];
    PsxFile_BindDisc(NULL);
    g->open_status = PsxDisc_Open(&d, bin, cue);
    g->found = g->open_status != PD_NOT_FOUND;
    g->cue_parsed = (uint32_t)d.cue_parsed;
    g->tracks = d.track.count; g->mode = d.track.mode; g->sector_bytes = d.track.sector_bytes;
    g->sectors = d.sectors; g->image_bytes = d.image_bytes;
    if (g->open_status != PD_OK) goto done;
    uint64_t start = stamp(clock);
    g->identity_status = ShDisc_Init(&sh, &d);
    g->identity_us = elapsed(clock, start);
    g->identity_count = sh.identity_count;
    memcpy(g->identity_actual, sh.identity_actual, sizeof(g->identity_actual));
    strcpy(g->detected, sh.detected);
    if (g->identity_status != PD_OK) {
        fail(g, sh.failed_identity ? sh.failed_identity : 100, sh.expected, sh.actual);
        goto done;
    }
    PsxFile_BindDisc(&sh);
    for (unsigned i = 0; i < sizeof(sh_reads)/sizeof(sh_reads[0]); ++i) {
        const DiscReference *ref = &sh_reads[i];
        DiscReadResult *r = &g->reads[g->test_count++];
        *r = (DiscReadResult){i+1, ref->lba, ref->bytes, ref->crc, 0, 0, PD_OK};
        start = stamp(clock);
        if (ref->raw) {
            ++g->raw_total;
            r->status = PsxDisc_ReadRawSector(&d, ref->lba, buffer);
            if (r->status == PD_OK) r->actual = PsxDisc_Crc32(0, buffer, 2352);
        } else if (ref->file_id >= 0) {
            ++g->fs_total;
            ShDiscFile file;
            r->status = ShDisc_Resolve(&sh, (uint32_t)ref->file_id, &file);
            if (r->status == PD_OK && (file.lba != ref->lba || file.bytes != ref->bytes)) r->status = PD_FORMAT;
            // Read through the same bounded FS contract future queue callers use.
            for (uint32_t off = 0; r->status == PD_OK && off < ref->bytes; ) {
                uint32_t n = ref->bytes - off;
                if (n > 2048) n = 2048;
                r->status = ShDisc_Read(&sh, &file, off, buffer, n);
                if (r->status == PD_OK) r->actual = PsxDisc_Crc32(r->actual, buffer, n);
                off += n;
            }
        } else {
            ++g->data_total;
            r->status = ShDisc_Checksum(&d, ref->lba, 0, ref->bytes, &r->actual);
        }
        r->us = elapsed(clock, start);
        if (r->status == PD_OK && r->actual == r->expected) {
            if (ref->raw) ++g->raw_pass;
            else if (ref->file_id >= 0) ++g->fs_pass;
            else ++g->data_pass;
        } else fail(g, r->id, r->expected, r->actual);
    }
    // Exercise real PsxFile_* descriptors separately from host/newlib file IO.
    ++g->fs_total;
    start = stamp(clock);
    int h = PsxFile_Open("cdrom:\\SLUS_007.07;1", 1);
    uint32_t crc = 0;
    int ok = h >= 0;
    for (uint32_t off = 0; ok && off < SH_EXE_BYTES; off += 2048) {
        ok = PsxFile_Read(h, buffer, 2048) == 2048;
        if (ok) crc = PsxDisc_Crc32(crc, buffer, 2048);
    }
    ok = ok && crc == 0x1c2b2258u && PsxFile_Read(h, buffer, 1) == 0 &&
         PsxFile_Seek(h, -4, 2) == (int)SH_EXE_BYTES - 4 && PsxFile_Read(h, buffer, 8) == 4;
    if (h >= 0 && PsxFile_Close(h)) ok = 0;
    g->reads[g->test_count++] = (DiscReadResult){300, SH_EXE_LBA, SH_EXE_BYTES, 0x1c2b2258u, crc,
                                              elapsed(clock, start), ok ? PD_OK : PD_IO};
    if (ok) ++g->fs_pass; else fail(g, 300, 0x1c2b2258u, crc);
    // Small correctness-oriented timing sanity checks, no cache/whole image load.
    start = stamp(clock);
    const uint32_t random_lbas[] = {16, 131057, 64, 261964, 24, 647};
    for (unsigned i = 0; i < sizeof(random_lbas)/sizeof(random_lbas[0]); ++i)
        if (PsxDisc_ReadDataSector(&d, random_lbas[i], buffer) != PD_OK) fail(g, 400+i, PD_OK, PD_IO);
    g->random_us = elapsed(clock, start);
    start = stamp(clock);
    g->sequential_sectors = 32;
    for (uint32_t i = 0; i < g->sequential_sectors; ++i)
        if (PsxDisc_ReadDataSector(&d, 64+i, buffer) != PD_OK) fail(g, 420+i, PD_OK, PD_IO);
    g->sequential_us = elapsed(clock, start);
done:
    PsxFile_BindDisc(NULL);
    PsxDisc_Close(&d);
    g->log_status = log_results(g, log);
}
