#include "stage4_report.h"
#include "build_identity.h"
#include <errno.h>
#include <stdio.h>

int stage4_report_write(const char *path, const Stage4FsResult *r, int pica0, int pica1)
{
    if (!path || !r) return EINVAL;
    char text[768];
    int length = snprintf(text, sizeof(text),
        "schema=2\nbuild=%s\ncontext=ORIGINAL_FS_DIAGNOSTIC title=NOT_RUN map=NOT_RUN\n"
        "checkpoint=%s first_failure=%lu file_id=%lu operation=%.64s detail=%08lX\n"
        "state=%lu substate=%lu\ncompleted=%lu reads=%lu uploads=%lu ticks=%lu vram_crc=%08lX\n"
        "pica=%d,%d\nreport_complete=1\n",
        SH_BUILD_ID, stage4_checkpoint_name(r->checkpoint), (unsigned long)r->first_failure,
        (unsigned long)r->file_id, r->operation ? r->operation : "none", (unsigned long)r->detail,
        (unsigned long)r->state, (unsigned long)r->substate, (unsigned long)r->completed,
        (unsigned long)r->reads, (unsigned long)r->uploads, (unsigned long)r->ticks,
        (unsigned long)r->vram_crc, !!pica0, !!pica1);
    if (length < 0 || (size_t)length >= sizeof(text)) return EOVERFLOW;
    FILE *file = fopen(path, "w");
    if (!file) return errno ? errno : EIO;
    int ok = fwrite(text, 1, (size_t)length, file) == (size_t)length;
    if (fflush(file)) ok = 0;
    if (fclose(file)) ok = 0;
    return ok ? 0 : EIO;
}
