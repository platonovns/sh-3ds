/* Minimal host-only SDK contract. Never included by a 3DS build. */
#ifndef CPU_AUDIT_MOCK_3DS_H
#define CPU_AUDIT_MOCK_3DS_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
typedef uint32_t u32, Handle;
typedef uint8_t u8;
typedef int32_t s32, Result;
typedef int64_t s64;
typedef void (*ThreadFunc)(void*);
typedef struct MockThread *Thread;
#define CUR_THREAD_HANDLE 0xffff8000u
#define CUR_PROCESS_HANDLE 0xffff8001u
#define SYSCLOCK_ARM11 268123480u
#define R_SUCCEEDED(x) ((Result)(x)>=0)
#define R_FAILED(x) ((Result)(x)<0)
u32 svcGetSystemTick_dummy(void);
uint64_t svcGetSystemTick(void);
int svcGetProcessorID(void);
Result svcGetThreadId(u32*,Handle);
Result svcGetThreadPriority(s32*,Handle);
Result svcGetThreadIdealProcessor(s32*,Handle);
Result svcGetThreadAffinityMask(u8*,Handle,s32);
Result svcGetSystemInfo(s64*,u32,s32);
Result svcGetProcessInfo(s64*,Handle,u32);
Result APT_CheckNew3DS(bool*);
Result APT_GetAppCpuTimeLimit(u32*);
Result threadJoin(Thread,s64);
void threadFree(Thread);
Thread threadCreate(ThreadFunc,void*,size_t,int,int,bool);
#endif
