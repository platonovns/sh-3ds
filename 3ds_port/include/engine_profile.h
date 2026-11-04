#ifndef SH_3DS_ENGINE_PROFILE_H
#define SH_3DS_ENGINE_PROFILE_H
/* This profile applies ONLY to game/PsyCross objects, never libctru headers. */
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <strings.h>
#define SH_3DS_PORT 1
#define SH_PC_PORT 1
#define bzero(ptr, bytes) __builtin_memset((ptr), 0, (bytes))
#define SKIP_ASM 1
#define VER_USA 1
#ifndef __cplusplus
#define static_assert _Static_assert
#endif
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error The PSX register and resource contracts require little endian
#endif
#if defined(USE_SDL2) || defined(OGL) || defined(OGLES) || defined(SH_ENABLE_RETROACHIEVEMENTS)
#error Desktop features are forbidden in the ARM11 compile gate
#endif
/* A legacy PSX file call must never silently bind to newlib. Use the explicit
 * namespaced contract in psyq_file.h. Stage 7 supplies the bounded card backend.
 * System declarations have been parsed above; HAL objects do not use this file.
 * A call error (rather than token poison) permits game fields named 'read'. */
#define SH_FORBID_FILE(name) extern __typeof__(name) name \
    __attribute__((error("Use the explicit PsxFile_* contract in game code")))
SH_FORBID_FILE(open);
SH_FORBID_FILE(read);
SH_FORBID_FILE(write);
SH_FORBID_FILE(close);
SH_FORBID_FILE(lseek);
#undef SH_FORBID_FILE
#endif
