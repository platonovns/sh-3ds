#include "stage4_fs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static PsxVram vram;
static int fault;
size_t __real_fread(void *, size_t, size_t, FILE *);
size_t __wrap_fread(void *data, size_t size, size_t count, FILE *file)
{
    long position = ftell(file);
    if (fault == 1 && position == 64 * 2352) return 0;
    size_t result = __real_fread(data, size, count, file);
    if (position == 64 * 2352 && size * result >= 2352) {
        if (fault == 2) ((unsigned char*)data)[24 + 4] = 7; /* unsupported TIM mode */
        if (fault == 3) ((unsigned char*)data)[24 + 544] ^= 1; /* valid TIM, bad pixel CRC */
    }
    return result;
}
int main(int argc, char **argv)
{
    assert(argc == 3);
    Stage4FsResult r;
    stage4_fs_run(&r, &vram, argv[1], argv[2]);
    assert(!r.first_failure && r.checkpoint == S4_FS_DONE);
    assert(r.completed == 2 && r.reads == 2 && r.uploads == 4 && r.ticks <= 32);
    printf("{\"positive\":{\"files\":%u,\"reads\":%u,\"uploads\":%u,\"ticks\":%u,\"vram_crc\":%u},\"faults\":[",
           r.completed, r.reads, r.uploads, r.ticks, r.vram_crc);
    for (fault = 1; fault <= 3; ++fault) {
        stage4_fs_run(&r, &vram, argv[1], argv[2]);
        unsigned expected = fault == 1 ? 404 : fault == 2 ? 407 : 415;
        assert(r.first_failure == expected && r.completed == 0);
        printf("%s%u", fault == 1 ? "" : ",", r.first_failure);
    }
    fault = 0;
    stage4_fs_run(&r, &vram, "/nonexistent-stage4.bin", argv[2]);
    assert(r.first_failure == 411 && !r.completed);
    printf(",%u],\"sanitizers\":\"ASan+UBSan\"}\n", r.first_failure);
    return 0;
}
