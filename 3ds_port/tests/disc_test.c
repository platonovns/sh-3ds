#define _POSIX_C_SOURCE 200809L
#include "disc_gate.h"
#include "sh_disc.h"
#include "psyq_file.h"
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* Link-time fault injection changes reads in RAM only. No image is copied or
 * modified. All actual IO remains the host stdio implementation. */
static long fault_at = -1;
static long short_at = -1;
size_t __real_fread(void *, size_t, size_t, FILE *);
size_t __wrap_fread(void *p, size_t size, size_t n, FILE *f)
{
    long pos = ftell(f);
    size_t result = __real_fread(p, size, n, f);
    if (short_at == pos) return result / 2;
    if (fault_at >= pos && pos >= 0 && (uint64_t)(fault_at - pos) < (uint64_t)size * result)
        ((unsigned char *)p)[fault_at - pos] ^= 1;
    return result;
}

static uint64_t clock_us(void)
{
    struct timespec t;
    assert(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (uint64_t)t.tv_sec * 1000000 + (uint64_t)t.tv_nsec / 1000;
}

static void cue_write(const char *path, const char *content)
{
    FILE *f = fopen(path, "w"); assert(f);
    assert(fputs(content, f) >= 0); assert(fclose(f) == 0);
}

int main(int argc, char **argv)
{
    assert(argc == 5);
    DiscGate g;
    disc_gate_run(&g, argv[1], argv[2], argv[3], clock_us);
    assert(g.open_status == PD_OK && g.identity_status == PD_OK && !g.first_failure && !g.log_status);
    assert(g.raw_pass == 3 && g.raw_total == 3);
    assert(g.data_pass == 3 && g.data_total == 3);
    assert(g.fs_pass == 6 && g.fs_total == 6);
    assert(g.msf_pass == 15 && g.msf_total == 15);
    uint32_t identity_us = g.identity_us, random_us = g.random_us, sequential_us = g.sequential_us;
    PsxDisc d;
    assert(PsxDisc_Open(&d, argv[1], argv[2]) == PD_OK);
    PsxTrackInfo track;
    assert(PsxDisc_GetTrackInfo(&d, &track) == PD_OK && track.count == 1 && track.mode == 2 && track.index01 == 0);
    ShDisc sh;
    assert(ShDisc_Init(&sh, &d) == PD_OK);
    uint8_t out[4096], ref[4096];
    memset(out, 0xa5, sizeof(out));
    assert(PsxDisc_ReadRawSector(&d, d.sectors, out) == PD_RANGE);
    assert(PsxDisc_ReadRawSector(&d, UINT32_MAX, out) == PD_RANGE);
    assert(PsxDisc_ReadDataSector(&d, d.sectors - 1, out) == PD_FORM2 && out[0] == 0xa5);
    assert(ShDisc_ReadBytes(&d, UINT32_MAX, UINT32_MAX, out, UINT32_MAX) == PD_RANGE);
    ShDiscFile file;
    assert(ShDisc_Resolve(&sh, 2074, &file) == PD_RANGE);
    assert(ShDisc_Resolve(&sh, 6, &file) == PD_OK && file.lba == 647 && file.bytes == 8448);
    assert(ShDisc_Read(&sh, &file, file.bytes, out, 1) == PD_RANGE);
    assert(ShDisc_Read(&sh, &file, 0, out, sizeof(out)) == PD_OK);
    assert(ShDisc_Read(&sh, &file, 2037, ref, 2059) == PD_OK && !memcmp(ref, out + 2037, 2059));
    assert(ShDisc_Read(&sh, &file, file.bytes, NULL, 0) == PD_OK);
    assert(ShDisc_FindIso(&d, "\\NO_SUCH_FILE;1", &file) == PD_NOT_FOUND);
    assert(ShDisc_FindIso(&d, "SLUS_007.07;1/INVALID", &file) == PD_FORMAT);
    PsxFile_BindDisc(&sh);
    assert(PsxFile_Open("sdmc:/anything", 1) == -1);
    assert(PsxFile_Open("bu00:save", 1) == -1);
    assert(PsxFile_Open("cdrom:\\SYSTEM.CNF;1", 2) == -1 && errno == EROFS);
    int h[4];
    for (unsigned i = 0; i < 4; ++i) { h[i] = PsxFile_Open("cdrom:\\SYSTEM.CNF;1", 1); assert(h[i] >= 0); }
    assert(PsxFile_Open("cdrom:\\SYSTEM.CNF;1", 1) == -1 && errno == EMFILE);
    assert(PsxFile_Read(h[0], out, -1) == -1);
    assert(PsxFile_Read(h[0], NULL, 1) == -1);
    assert(PsxFile_Seek(h[0], -1, 0) == -1);
    assert(PsxFile_Seek(h[0], 69, 0) == -1);
    assert(PsxFile_Seek(h[0], 0, 99) == -1);
    assert(PsxFile_Read(h[0], out, sizeof(out)) == 68);
    assert(PsxFile_Read(h[0], out, 1) == 0);
    assert(PsxFile_Seek(h[0], -4, 1) == 64 && PsxFile_Read(h[0], out, 8) == 4);
    assert(PsxFile_Write(h[0], out, 4) == -1 && errno == EROFS);
    assert(PsxFile_Close(h[0]) == 0 && PsxFile_Close(h[0]) == -1);
    PsxFile_BindDisc(NULL);
    assert(PsxFile_Read(h[1], out, 1) == -1 && errno == EBADF);
    assert(PsxFile_Open("cdrom:\\SYSTEM.CNF;1", 1) == -1 && errno == ENODEV);
    PsxDisc_Close(&d); PsxDisc_Close(&d);
    assert(PsxDisc_ReadRawSector(&d, 0, out) == PD_RANGE);

    // Negative identity checks: executable, ISO PVD and on-disc table corruption.
    const long faults[] = {25L * 2352 + 24 + 7, 16L * 2352 + 24 + 40,
                           (24L + 47388/2048) * 2352 + 24 + 47388%2048};
    for (unsigned i = 0; i < sizeof(faults)/sizeof(faults[0]); ++i) {
        fault_at = faults[i];
        disc_gate_run(&g, argv[1], argv[2], argv[4], clock_us);
        assert(g.open_status == PD_OK && g.identity_status == PD_UNSUPPORTED && g.first_failure);
        assert(!g.test_count && !g.raw_total && !g.data_total && !g.fs_total);
    }
    fault_at = 207L * 2352 + 31;
    disc_gate_run(&g, argv[1], argv[2], argv[4], clock_us);
    assert(g.identity_status == PD_OK && g.first_failure == 8 && g.expected == 0xa8966201u && g.actual != g.expected);
    assert(g.fs_pass == 5 && g.fs_total == 6);
    fault_at = -1;
    short_at = 207L * 2352;
    disc_gate_run(&g, argv[1], argv[2], argv[4], clock_us);
    assert(g.identity_status == PD_OK && g.first_failure == 8 && g.reads[7].status == PD_IO);
    short_at = -1;
    fault_at = 15;
    disc_gate_run(&g, argv[1], argv[2], argv[4], clock_us);
    assert(g.open_status == PD_FORMAT && !g.test_count);
    fault_at = -1;
    disc_gate_run(&g, "nonexistent-stage2-image.bin", argv[2], argv[4], clock_us);
    assert(!g.found && g.open_status == PD_NOT_FOUND && !g.test_count && g.msf_pass == 15);
    disc_gate_run(&g, argv[1], "nonexistent-stage2.cue", argv[4], clock_us);
    assert(g.found && g.open_status == PD_FORMAT && !g.test_count);
    disc_gate_run(&g, "nonexistent-stage2-image.bin", argv[2], "/nonexistent-stage2-dir/log", clock_us);
    assert(g.log_status != 0);

    // Synthetic geometry/parser failures; fixture contains generated bytes only.
    char bin[] = "/tmp/sh-disc-bin-XXXXXX", cue[] = "/tmp/sh-disc-cue-XXXXXX";
    int bfd = mkstemp(bin), cfd = mkstemp(cue); assert(bfd >= 0 && cfd >= 0);
    close(cfd);
    uint8_t synthetic[2352] = {0};
    memset(synthetic + 1, 255, 10); synthetic[13] = 2; synthetic[15] = 2;
    assert(write(bfd, synthetic, sizeof(synthetic)) == sizeof(synthetic)); close(bfd);
    const char *valid = "FILE \"renamed.bin\" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n";
    cue_write(cue, valid);
    assert(PsxDisc_Open(&d, bin, cue) == PD_OK);
    assert(ShDisc_Init(&sh, &d) == PD_UNSUPPORTED && !sh.supported);
    PsxDisc_Close(&d);
    const char *bad[] = {
        "FILE \"x\" BINARY\nTRACK 01 MODE1/2352\nINDEX 01 00:00:00\n",
        "FILE \"x\" BINARY\nTRACK 01 MODE2/2352\nINDEX 01 00:02:00\n",
        "FILE \"x\" BINARY\nTRACK 01 MODE2/2352\nPREGAP 00:02:00\nINDEX 01 00:00:00\n",
        "FILE \"x\" BINARY\nTRACK 01 MODE2/2352\nINDEX 01 00:00:00\nTRACK 02 AUDIO\n",
        "FILE \"x\" BINARY\nTRACK 01 MODE2/2352\nINDEX 01 00:00:00 junk\n",
        "FILE \"x\" BINARY\nTRACK 01 MODE2/2352\nINDEX 01 00:00:00\nFILE \"y\" BINARY\n"
    };
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
        cue_write(cue, bad[i]); assert(PsxDisc_Open(&d, bin, cue) == PD_FORMAT && !d.file);
    }
    cue_write(cue, valid);
    FILE *f = fopen(bin, "ab"); assert(f); assert(fputc(0, f) == 0); fclose(f);
    assert(PsxDisc_Open(&d, bin, cue) == PD_FORMAT && !d.file);
    unlink(bin); unlink(cue);
    printf("{\"result\":\"PASS\",\"raw\":\"3/3\",\"data\":\"3/3\",\"fs_psxfile\":\"6/6\",\"msf\":\"15/15\","
           "\"negative_tests\":\"identity/resource mutations, short IO, missing image/CUE, malformed geometry/CUE, bounds, Form2, descriptors, failed log\","
           "\"identity_us\":%"PRIu32",\"random_6_us\":%"PRIu32",\"sequential_32_us\":%"PRIu32"}\n",
           identity_us,random_us,sequential_us);
    return 0;
}
