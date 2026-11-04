/* Test-only narrow libctru boundary. Production uses the actual SDK header. */
#ifndef FMV_FAKE_3DS_H
#define FMV_FAKE_3DS_H
#include <stdint.h>
#include <stdbool.h>
typedef uint16_t u16;
#define SYSCLOCK_ARM11 268123480ull
#define KEY_START 8u
#define GFX_TOP 0
#define GFX_LEFT 0
#define NDSP_INTERP_POLYPHASE 2
#define NDSP_FORMAT_STEREO_PCM16 0x11
enum {NDSP_WBUF_FREE,NDSP_WBUF_QUEUED,NDSP_WBUF_PLAYING,NDSP_WBUF_DONE};
typedef struct {int16_t *data_pcm16;uint32_t nsamples;uint8_t status;uint16_t sequence_id;} ndspWaveBuf;
typedef enum {APTHOOK_ONSUSPEND,APTHOOK_ONSLEEP,APTHOOK_ONRESTORE,APTHOOK_ONWAKEUP} APT_HookType;
typedef struct {int active;} aptHookCookie;
typedef void *Thread;
uint64_t svcGetSystemTick(void);
int svcGetProcessorID(void);
void svcSleepThread(int64_t);
Thread threadCreate(void (*)(void *),void *,unsigned,int,int,bool);
void threadJoin(Thread,uint64_t);
void threadFree(Thread);
void *linearAlloc(unsigned);
void linearFree(void *);
void aptHook(aptHookCookie *,void (*)(APT_HookType,void *),void *);
void aptUnhook(aptHookCookie *);
bool aptMainLoop(void);
void hidScanInput(void);
uint32_t hidKeysHeld(void);
uint8_t *gfxGetFramebuffer(int,int,u16 *,u16 *);
void gfxFlushBuffers(void);
void gfxSwapBuffers(void);
void gspWaitForVBlank(void);
void ndspChnSetPaused(int,bool);
void ndspChnReset(int);
void ndspChnSetInterp(int,int);
void ndspChnSetRate(int,float);
void ndspChnSetFormat(int,int);
void ndspChnSetMix(int,float *);
void ndspChnWaveBufAdd(int,ndspWaveBuf *);
void ndspChnWaveBufClear(int);
uint16_t ndspChnGetWaveBufSeq(int);
uint32_t ndspChnGetSamplePos(int);
void DSP_FlushDataCache(void *,unsigned);
#endif
