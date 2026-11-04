#ifndef SH_PSX_DISC_H
#define SH_PSX_DISC_H
#include <stdint.h>
#include <stdio.h>

#define PSX_RAW_BYTES 2352u
#define PSX_DATA_BYTES 2048u
enum { PD_OK = 0, PD_NOT_FOUND = -1, PD_IO = -2, PD_FORMAT = -3,
       PD_RANGE = -4, PD_FORM2 = -5, PD_UNSUPPORTED = -6 };
typedef struct { uint8_t minute, second, frame; } PsxMsf;
typedef struct {
    uint32_t count, number, mode, sector_bytes, index01, pregap;
} PsxTrackInfo;
typedef struct {
    FILE *file;
    uint32_t sectors, image_bytes;
    PsxTrackInfo track;
    int cue_parsed;
    uint8_t scratch[PSX_RAW_BYTES];
    uint32_t next_raw_lba;
    int sequential_position_valid;
    uint8_t *raw_cache;
    uint32_t cache_lba,cache_sectors,cache_bytes,cache_hits,cache_misses;
    uint32_t preload_reads,preload_seeks;
    uint64_t preload_ticks;
    uint32_t cache_peak_bytes;
    uint8_t *extra_cache;
    uint32_t extra_lba,extra_sectors,extra_bytes;
} PsxDisc;
/* The BIN path is explicitly bound by the caller. CUE's FILE name is descriptive;
 * this supports renamed local dumps without editing their original CUE. Only
 * one BINARY FILE / TRACK 01 MODE2/2352 / INDEX 01 00:00:00 is accepted in Stage 2.
 * Nonzero pregaps, multi-track/file images and other formats fail closed. */
int PsxDisc_Open(PsxDisc *disc, const char *bin_path, const char *cue_path);
/* Optional caller-owned stdio buffer, installed before the first read.
 * Buffer must live through PsxDisc_Close; ordinary callers retain defaults. */
int PsxDisc_OpenBuffered(PsxDisc *disc,const char *bin_path,const char *cue_path,
                         void *buffer,uint32_t bytes);
void PsxDisc_Close(PsxDisc *disc);
int PsxDisc_GetTrackInfo(const PsxDisc *disc, PsxTrackInfo *out);
int PsxDisc_ReadRawSector(PsxDisc *disc, uint32_t lba, void *raw2352);
int PsxDisc_ReadDataSector(PsxDisc *disc, uint32_t lba, void *data2048);
/* Ordinary heap, at most 16 MiB. Optional cache failure leaves disk reads usable. */
int PsxDisc_CacheRange(PsxDisc *disc,uint32_t lba,uint32_t sectors);
/* One additional disjoint range. Combined resident/allocation limit stays 16 MiB. */
int PsxDisc_CacheExtraRange(PsxDisc *disc,uint32_t lba,uint32_t sectors);
int PsxDisc_LbaToMsf(int32_t lba, PsxMsf *out);
int PsxDisc_MsfToLba(const PsxMsf *msf, int32_t *out);
uint32_t PsxDisc_Crc32(uint32_t previous, const void *data, uint32_t bytes);
#endif
