#ifndef SH_DISC_GATE_H
#define SH_DISC_GATE_H
#include <stdint.h>
#include <stdio.h>
typedef struct {
    const char *name;
    uint32_t lba, bytes, crc;
    int32_t file_id, raw;
} DiscReference;
typedef struct {
    uint32_t id, lba, bytes, expected, actual, us;
    int32_t status;
} DiscReadResult;
#define DISC_MAX_TESTS 16u
typedef struct {
    int32_t open_status, identity_status, log_status;
    uint32_t found, cue_parsed, tracks, mode, sector_bytes, sectors, image_bytes;
    uint32_t raw_pass, raw_total, data_pass, data_total, fs_pass, fs_total;
    uint32_t msf_pass, msf_total, first_failure, expected, actual, test_count;
    uint32_t identity_us, random_us, sequential_us, sequential_sectors;
    char detected[40];
    DiscReadResult reads[DISC_MAX_TESTS];
    uint32_t identity_count, identity_actual[5];
} DiscGate;
typedef uint64_t (*DiscClockUs)(void);
void disc_gate_run(DiscGate *out, const char *bin, const char *cue, const char *log, DiscClockUs clock);
uint32_t disc_gate_msf_tests(uint32_t *total);
#endif
