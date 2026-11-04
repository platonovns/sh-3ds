#ifndef SH_SH_DISC_H
#define SH_SH_DISC_H
#include "psx_disc.h"
typedef struct { uint32_t lba, bytes; } ShDiscFile;
typedef struct ShDisc {
    PsxDisc *disc;
    int supported;
    uint32_t failed_identity, expected, actual;
    char detected[40];
    uint32_t identity_count, identity_actual[5];
} ShDisc;
/* Read-only lower FS gate. No FS queue/post-load/relocation is executed. */
int ShDisc_Init(ShDisc *sh, PsxDisc *disc);
int ShDisc_FindIso(PsxDisc *disc, const char *path, ShDiscFile *out);
int ShDisc_Resolve(ShDisc *sh, uint32_t file_id, ShDiscFile *out);
int ShDisc_Read(ShDisc *sh, const ShDiscFile *file, uint32_t offset, void *out, uint32_t bytes);
int ShDisc_ReadBytes(PsxDisc *disc, uint32_t lba, uint32_t offset, void *out, uint32_t bytes);
int ShDisc_Checksum(PsxDisc *disc, uint32_t lba, uint32_t offset, uint32_t bytes, uint32_t *crc);
#endif
