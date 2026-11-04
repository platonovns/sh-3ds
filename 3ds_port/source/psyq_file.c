#include "psyq_file.h"
#include "sh_disc.h"
#include <errno.h>
#include <limits.h>
#include <string.h>

static ShDisc *mounted;
static struct { ShDiscFile file; uint32_t pos; int used; } handles[4];

void PsxFile_BindDisc(ShDisc *disc)
{
    mounted = disc;
    memset(handles, 0, sizeof(handles));
}

static int slot(int handle)
{
    int i = handle - 0x4000;
    if (i < 0 || i >= 4 || !handles[i].used) { errno = EBADF; return -1; }
    return i;
}

int PsxFile_Open(char *path, unsigned int flags)
{
    if (flags != 1) { errno = EROFS; return -1; }
    if (!mounted || !mounted->supported) { errno = ENODEV; return -1; }
    if (!path || strncmp(path, "cdrom:", 6)) { errno = ENOENT; return -1; }
    ShDiscFile file;
    if (ShDisc_FindIso(mounted->disc, path, &file) != PD_OK) { errno = ENOENT; return -1; }
    for (int i = 0; i < 4; ++i) {
        if (handles[i].used) continue;
        handles[i].file = file; handles[i].pos = 0; handles[i].used = 1;
        return 0x4000 + i;
    }
    errno = EMFILE;
    return -1;
}

int PsxFile_Read(int handle, void *buffer, int bytes)
{
    int i = slot(handle);
    if (i < 0) return -1;
    if (bytes < 0 || (!buffer && bytes)) { errno = EINVAL; return -1; }
    uint32_t n = (uint32_t)bytes, available = handles[i].file.bytes - handles[i].pos;
    if (n > available) n = available;
    if (ShDisc_Read(mounted, &handles[i].file, handles[i].pos, buffer, n) != PD_OK) { errno = EIO; return -1; }
    handles[i].pos += n;
    return (int)n;
}

int PsxFile_Write(int handle, void *buffer, int bytes)
{
    (void)handle; (void)buffer; (void)bytes;
    errno = EROFS;
    return -1;
}

int PsxFile_Close(int handle)
{
    int i = slot(handle);
    if (i < 0) return -1;
    handles[i].used = 0;
    return 0;
}

int PsxFile_Seek(int handle, int off, int whence)
{
    int i = slot(handle);
    if (i < 0) return -1;
    int64_t base;
    if (whence == 0) base = 0;
    else if (whence == 1) base = handles[i].pos;
    else if (whence == 2) base = handles[i].file.bytes;
    else { errno = EINVAL; return -1; }
    int64_t pos = base + off;
    if (pos < 0 || pos > handles[i].file.bytes || pos > INT_MAX) { errno = EINVAL; return -1; }
    handles[i].pos = (uint32_t)pos;
    return (int)pos;
}
