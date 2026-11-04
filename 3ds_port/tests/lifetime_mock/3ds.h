#ifndef LIFETIME_MOCK_3DS_H
#define LIFETIME_MOCK_3DS_H
#include <stdint.h>
typedef int64_t s64;
#define CUR_PROCESS_HANDLE 1
uint64_t svcGetSystemTick(void);
uint32_t svcGetProcessInfo(s64 *out,unsigned handle,unsigned type);
uint32_t envGetHeapSize(void);
uint32_t envGetLinearHeapSize(void);
uint32_t linearSpaceFree(void);
uint32_t vramSpaceFree(void);
#endif
