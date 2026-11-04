#ifndef SH_3DS_PSYQ_FILE_H
#define SH_3DS_PSYQ_FILE_H
/* PSX descriptors/flags are not newlib descriptors/flags.
 * Game callers must explicitly use these names; libc calls are compile errors
 * by engine_profile.h. Future libapi implementations must export these symbols
 * rather than the conflicting upstream open/read/write/close/lseek definitions. */
#ifdef __cplusplus
extern "C" {
#endif
int PsxFile_Open(char *path, unsigned int flags);
int PsxFile_Read(int handle, void *buffer, int bytes);
int PsxFile_Write(int handle, void *buffer, int bytes);
int PsxFile_Close(int handle);
int PsxFile_Seek(int handle, int offset, int whence);
/* Stage 2: read-only cdrom: ISO files, FREAD (1) only. No memory-card backend.
 * Bind/unbind invalidates the bounded descriptor set. Caller owns disc lifetime. */
struct ShDisc;
void PsxFile_BindDisc(struct ShDisc *disc);
#ifdef __cplusplus
}
#endif
#endif
