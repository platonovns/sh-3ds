#ifndef SH_STAGE4_REPORT_H
#define SH_STAGE4_REPORT_H
#include "stage4_fs.h"
/* One bounded snapshot, no accumulated trace and no SDK/game type mixing. */
int stage4_report_write(const char *path, const Stage4FsResult *result, int pica0, int pica1);
#endif
