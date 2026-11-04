/* Original FS queue exercised through a bounded CD/image platform facade.
 * No replacement for Fs_Queue*, no game-state mutation, no desktop GPU core. */
#include "main/fsqueue.h"
#include "main/fsmem.h"
#include "psx_memory.h"
#include "stage4_fs.h"
#include "sh_disc.h"
#include "psx_tim.h"
#include "tim_reference.h"
#include <psyq/libcd.h>
#include <psyq/libgpu.h>
#include <string.h>
#include <stdlib.h>
#ifdef SH_3DS_GAME
#include "game3ds.h"
#include "game_profile.h"
#include "game_io.h"
static PsxDisc game_disc;
static ShDisc game_sh;
static int game_mounted;
/* Read presentation assets without installing them in the gameplay VRAM.
 * Caller only uses this while the original queue is idle on the game thread. */
int stage4_fs_presentation_read(uint32_t id, void **out, uint32_t *size)
{
    ShDiscFile f;
    if (!game_mounted || !out || !size || ShDisc_Resolve(&game_sh,id,&f) != PD_OK ||
        !f.bytes || f.bytes > 1024*1024) return -1;
    void *p=malloc(f.bytes);
    if (!p) return -2;
    int rc=ShDisc_Read(&game_sh,&f,0,p,f.bytes);
    if (rc != PD_OK) { free(p); return rc; }
    *out=p; *size=f.bytes;
    return 0;
}
static int cache_enabled=1,preload_status=PD_UNSUPPORTED,common_status=PD_UNSUPPORTED;
static unsigned preload_files;
void stage4_fs_game_cache_enable(int enabled) {cache_enabled=enabled!=0;}
void stage4_fs_game_preload(const char *tag)
{
    if(!cache_enabled || !tag || strlen(tag)!=3 || !game_mounted)return;
    unsigned prefix=0,lo=UINT32_MAX,hi=0,count=0;
    for(unsigned i=0;i<3;i++)prefix|=((tag[i]-32)&63)<<(6*i);
    /* Derive the map's complete background library from original metadata.
     * No measured-file whitelist or map-specific resource replacement. */
    for(unsigned i=0;i<FS_FILE_COUNT;i++) {
        const s_FileInfo *f=&g_FileTable[i];
        if(f->pathIdx!=2 || (f->name0123&0x3ffff)!=prefix || !f->blockCount)continue;
        unsigned end=f->startSector+(f->blockCount*256+2047)/2048;
        if(f->startSector<lo)lo=f->startSector;
        if(end>hi)hi=end;
        count++;
    }
    preload_files=count;
    if(count)preload_status=PsxDisc_CacheRange(&game_disc,lo,hi-lo);
    if(preload_status==PD_OK) {
        /* Original GameFs_StreamBinSeek/Load names this common native module.
         * Its first 77824-byte load was separately measured at ~59 ms. */
        const s_FileInfo *common=&g_FileTable[FILE_VIN_STREAM_BIN];
        common_status=PsxDisc_CacheExtraRange(&game_disc,common->startSector,(common->blockCount*256+2047)/2048);
    }
}
void stage4_fs_game_report(FILE *out)
{
    fprintf(out,"resource_cache_peak_bytes=%lu\n",(unsigned long)game_disc.cache_peak_bytes);
    fprintf(out,"resource_common_status=%d\nresource_common_file=%u\nresource_common_lba=%lu\nresource_common_sectors=%lu\nresource_common_bytes=%lu\n",
        common_status,(unsigned)FILE_VIN_STREAM_BIN,(unsigned long)game_disc.extra_lba,(unsigned long)game_disc.extra_sectors,(unsigned long)game_disc.extra_bytes);
    fprintf(out,"resource_cache_enabled=%d\nresource_cache_status=%d\nresource_cache_budget=16777216\nresource_cache_bytes=%lu\nresource_cache_files=%u\nresource_cache_lba=%lu\nresource_cache_sectors=%lu\nresource_cache_hits=%lu\nresource_cache_misses=%lu\nresource_preload_reads=%lu\nresource_preload_seeks=%lu\nresource_preload_ms=%.4f\n",
        cache_enabled,preload_status,(unsigned long)(game_disc.cache_bytes+game_disc.extra_bytes),preload_files,(unsigned long)game_disc.cache_lba,
        (unsigned long)game_disc.cache_sectors,(unsigned long)game_disc.cache_hits,(unsigned long)game_disc.cache_misses,
        (unsigned long)game_disc.preload_reads,(unsigned long)game_disc.preload_seeks,game_disc.preload_ticks/268123.480);
}
static struct { uint32_t file, capacity; void *data; } game_spans[2];
static unsigned game_span_count;
static const void *game_image_span;
static uint32_t game_image_bytes;
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
void stage11a_lifetime_resource(uint32_t out[LT_RESOURCE_WORDS])
{
    out[0]=game_span_count;out[1]=2;out[2]=game_disc.cache_bytes;out[3]=game_disc.extra_bytes;
    out[4]=game_disc.cache_peak_bytes;out[5]=preload_files;out[6]=game_disc.cache_hits;
    out[7]=game_disc.cache_misses;out[8]=game_image_span!=NULL;
}
#endif
void stage4_fs_game_image_span(const void *data, uint32_t bytes)
{
    if (!data || !bytes || bytes > 65536 || game_image_span)
        game3ds_halt(455,"image producer extent",bytes);
    game_image_span=data; game_image_bytes=bytes;
}
#endif

static Stage4FsResult *active;
static PsxVram *canonical;
static ShDisc *mounted;
#ifdef SH_3DS_GAME
int CdInit(void) { return mounted && active && !active->first_failure; }
#endif
static uint32_t cd_lba;
#ifdef SH_3DS_GAME
static void *last_read_data;
static uint32_t last_read_file, last_read_bytes;
#endif
static const uint8_t *tim_base;
static PsxTim parsed;
static RECT16 image_rect, clut_rect;

const char *stage4_checkpoint_name(uint32_t checkpoint)
{
    static const char *const names[] = {"BOOT", "FS_INIT", "FS_READ", "TIM_POSTLOAD", "VRAM", "FS_DONE"};
    return checkpoint < sizeof(names)/sizeof(names[0]) ? names[checkpoint] : "UNKNOWN";
}
void stage4_fs_fail(uint32_t code, const char *operation, uint32_t detail)
{
    if (active && !active->first_failure) {
        active->first_failure = code; active->operation = operation; active->detail = detail;
#ifdef SH_3DS_GAME
        game3ds_halt(code, operation, detail);
#endif
    }
}
static int failed(void) { return !active || active->first_failure; }

CdlLOC *CdIntToPos(int lba, CdlLOC *loc)
{
    PsxMsf msf;
    if (!loc || PsxDisc_LbaToMsf(lba, &msf)) {
        stage4_fs_fail(401, "CdIntToPos", (uint32_t)lba); return NULL;
    }
    loc->minute = msf.minute; loc->second = msf.second; loc->sector = msf.frame; loc->track = 0;
    return loc;
}
int CdControl(u_char command, u_char *param, u_char *result)
{
    if (result) *result = 0;
    if (failed()) return 0;
    if (command == CdlSetloc && param) {
        PsxMsf msf = {param[0], param[1], param[2]};
        int32_t lba;
        if (!PsxDisc_MsfToLba(&msf, &lba) && lba >= 0) { cd_lba = (uint32_t)lba; return 1; }
    } else if (command == CdlSeekL) {
        return 1; /* SD file has no mechanical seek latency. CdSync completes it. */
    }
    stage4_fs_fail(402, "CdControl", command);
    return 0;
}
int CdSync(int mode, u_char *result)
{
    (void)mode; if (result) *result = 0;
    return failed() ? CdlDiskError : CdlComplete;
}
int CdRead(int sectors, u_long *buffer, int mode)
{
    if (failed()) return 0;
    const s_FsQueueEntry *e = g_FsQueue.read.ptr;
    uintptr_t begin = (uintptr_t)g_PsxRam, dest = (uintptr_t)buffer;
    uint32_t bytes = sectors > 0 && sectors <= 512 ? (uint32_t)sectors * 2048 : 0;
    int destination_ok = dest >= begin && dest - begin <= PSX_RAM_SIZE && bytes <= PSX_RAM_SIZE - (dest-begin);
#ifdef SH_3DS_GAME
    for (unsigned i=0; i<game_span_count; i++)
        if (e->info == &g_FileTable[game_spans[i].file] && buffer == game_spans[i].data && bytes <= game_spans[i].capacity)
            destination_ok = 1;
#endif
    if (!mounted || mode != CdlModeSpeed || !bytes || !destination_ok ||
        e->info < g_FileTable || e->info >= g_FileTable + FS_FILE_COUNT ||
        cd_lba != e->info->startSector || (void*)buffer != e->data ||
        bytes != ALIGN(e->info->blockCount * FS_BLOCK_SIZE, FS_SECTOR_SIZE)) {
        stage4_fs_fail(403, "CdRead bounds/contract", cd_lba); return 0;
    }
    active->checkpoint = S4_FS_READ;
    active->file_id = (uint32_t)(e->info - g_FileTable);
    /* Original queue requests rounded sectors, including the final padding.
     * ShDisc_Read's file-byte limit must not be bypassed for ordinary reads;
     * this CD boundary deliberately reads the same padded sectors as PS1. */
#ifdef SH_3DS_GAME
    uint64_t profile=game_prof_begin();
    game_io_begin(active->file_id,cd_lba,bytes);
#endif
    int status = ShDisc_ReadBytes(mounted->disc, cd_lba, 0, buffer, bytes);
#ifdef SH_3DS_GAME
    game_io_end(status);
    game_prof_end(GP_RESOURCE,profile);game_prof_count(GC_READS,1);game_prof_count(GC_READ_BYTES,bytes);
#endif
    if (status) { stage4_fs_fail(404, "CdRead sector I/O", (uint32_t)status); return 0; }
#ifdef SH_3DS_GAME
    last_read_data = buffer;
    last_read_file = active->file_id;
    last_read_bytes = bytes;
#endif
    active->reads++; cd_lba += (uint32_t)sectors;
    return 1;
}
int CdReadSync(int mode, u_char *result)
{
    (void)mode; if (result) *result = 0;
    return failed() ? -1 : 0; /* synchronous SD I/O already finished */
}
int CdReset(int mode)
{
    (void)mode;
    stage4_fs_fail(405, "CdReset after read failure", cd_lba);
    return 0; /* Never turn an I/O failure into queue success. */
}

static int memory_read(void *context, uint32_t offset, void *out, uint32_t bytes)
{
    memcpy(out, (const uint8_t*)context + offset, bytes); return 0;
}
static int open_tim_extent(void *data, uint32_t bytes, uint32_t file_id)
{
    active->checkpoint = S4_TIM_POSTLOAD;
    active->file_id = file_id;
    PsxSource source = {memory_read, data, bytes};
    int status = psx_tim_parse(source, &parsed);
    if (status) { stage4_fs_fail(407, "OpenTIM parse", (uint32_t)status); return 0; }
    tim_base = (const uint8_t*)data;
    return 0;
}
#ifdef SH_3DS_GAME
int stage4_fs_open_read_tim(void *data, uint32_t file_id)
{
    tim_base = NULL; memset(&parsed, 0, sizeof(parsed));
    if (failed()) return 0;
    if (file_id >= FS_FILE_COUNT || data != last_read_data || file_id != last_read_file ||
        g_FileTable[file_id].blockCount * FS_BLOCK_SIZE > last_read_bytes) {
        stage4_fs_fail(406, "OpenTIM read extent", file_id); return 0;
    }
    return open_tim_extent(data, g_FileTable[file_id].blockCount * FS_BLOCK_SIZE, file_id);
}
#endif
int OpenTIM(u_long *data)
{
    tim_base = NULL; memset(&parsed, 0, sizeof(parsed));
    if (failed()) return 0;
    const s_FsQueueEntry *e = g_FsQueue.postLoad.ptr;
    if (e->info < g_FileTable || e->info >= g_FileTable + FS_FILE_COUNT ||
        e->allocate || (void*)data != e->externalData || e->externalData != e->data) {
        stage4_fs_fail(406, "OpenTIM queue extent", 0); return 0;
    }
    return open_tim_extent(data, e->info->blockCount * FS_BLOCK_SIZE,
                           (uint32_t)(e->info - g_FileTable));
}
TIM_IMAGE *ReadTIM(TIM_IMAGE *tim)
{
    memset(tim, 0, sizeof(*tim));
    memset(&image_rect, 0, sizeof(image_rect)); memset(&clut_rect, 0, sizeof(clut_rect));
    tim->prect = &image_rect; tim->crect = &clut_rect;
    if (!tim_base || failed()) return tim;
    image_rect = (RECT16){parsed.image.x, parsed.image.y, parsed.image.w, parsed.image.h};
    clut_rect = (RECT16){parsed.clut.x, parsed.clut.y, parsed.clut.w, parsed.clut.h};
    tim->mode = parsed.flags;
    tim->paddr = (u_int*)(tim_base + parsed.image_offset);
    tim->caddr = parsed.has_clut ? (u_int*)(tim_base + parsed.clut_offset) : NULL;
    return tim;
}
int LoadImage(RECT16 *rect, u_long *data)
{
    if (failed()) return -1;
    if (!rect || !data || !canonical) { stage4_fs_fail(408, "LoadImage null", 0); return -1; }
    PsxRect r = {(uint16_t)rect->x, (uint16_t)rect->y, (uint16_t)rect->w, (uint16_t)rect->h};
    size_t bytes = (size_t)r.w * r.h * 2;
    /* This slice only reaches TIM image/CLUT uploads. Validate the source too. */
    int source_valid=tim_base && (((const uint8_t*)data == tim_base + parsed.image_offset && bytes == parsed.image_bytes) ||
                                ((const uint8_t*)data == tim_base + parsed.clut_offset && bytes == parsed.clut_bytes));
#ifdef SH_3DS_GAME
    if (data == game_image_span && bytes == game_image_bytes) source_valid=1;
    /* StoreImage/MoveImage effects restore arbitrary PSX RAM snapshots. The
     * full readable span must still fit the emulated RAM allocation. */
    uintptr_t image_address=(uintptr_t)data,ram_address=(uintptr_t)g_PsxRam;
    if(image_address>=ram_address && image_address-ram_address<=PSX_RAM_SIZE &&
        bytes<=PSX_RAM_SIZE-(image_address-ram_address))source_valid=1;
    game_image_span=NULL; game_image_bytes=0;
#endif
    if (!source_valid) {
        stage4_fs_fail(409, "LoadImage source extent", (uint32_t)bytes); return -1;
    }
#ifdef SH_3DS_GAME
    game3ds_gpu_dirty_rect(r.x,r.y,r.w,r.h); /* Flush old draws before the write. */
#endif
    int status = psx_vram_load(canonical, r, data, bytes);
    if (status) { stage4_fs_fail(410, "LoadImage VRAM bounds", (uint32_t)status); return -1; }
    active->uploads++; active->checkpoint = S4_VRAM;
    return 0;
}

void stage4_fs_run(Stage4FsResult *r, PsxVram *v, const char *bin, const char *cue)
{
    memset(r, 0, sizeof(*r)); active = r; canonical = v; cd_lba = 0; tim_base = NULL;
    PsxDisc disc;
    ShDisc sh;
    int status = PsxDisc_Open(&disc, bin, cue);
    if (status) { stage4_fs_fail(411, "PsxDisc_Open", (uint32_t)status); goto done; }
    status = ShDisc_Init(&sh, &disc);
    if (status) { stage4_fs_fail(412, "ShDisc_Init", (uint32_t)status); goto close; }
    mounted = &sh; r->checkpoint = S4_FS_INIT;
    /* Refuse any table mismatch before using original queue metadata. */
    for (uint32_t id = 0; id < FS_FILE_COUNT; ++id) {
        ShDiscFile file;
        if (ShDisc_Resolve(&sh, id, &file) || file.lba != g_FileTable[id].startSector ||
            file.bytes != (uint32_t)g_FileTable[id].blockCount * FS_BLOCK_SIZE) {
            r->file_id = id; stage4_fs_fail(413, "original file table mismatch", id); goto close;
        }
    }
    Fs_QueueInitialize(); psx_vram_init(v);
    for (unsigned i = 0; i < 2 && !failed(); ++i) {
        uint32_t id = i ? FILE_1ST_FONT16_TIM : FILE_1ST_2ZANKO80_TIM;
        /* Same relocation fixture as accepted Stage 3, performed by the game. */
        s_FsImageDesc image = {.tPage = {0, (uint8_t)(i ? 26 : 10)}, .u = 0, .v = 0,
                              .clutX = 0, .clutY = (int16_t)(i ? 481 : 480)};
        Fs_QueueStartReadTim(id, FS_BUFFER_0, &image);
        unsigned ticks = 0;
        while (Fs_QueueGetLength() > 0 && !failed() && ticks++ < 64) {
            Fs_QueueUpdate(); r->ticks++;
            r->state = g_FsQueue.state; r->substate = g_FsQueue.postLoadState;
        }
        if (!failed() && Fs_QueueGetLength()) stage4_fs_fail(414, "Fs_QueueUpdate timeout", ticks);
        if (failed()) break;
        r->vram_crc = psx_vram_crc(v);
        if (r->vram_crc != tim_reference[i][1]) {
            stage4_fs_fail(415, "original postload VRAM CRC", r->vram_crc); break;
        }
        r->completed++;
    }
    if (!failed() && r->completed == 2) r->checkpoint = S4_FS_DONE;
close:
    PsxDisc_Close(&disc);
done:
    mounted = NULL; canonical = NULL; tim_base = NULL; active = NULL;
}

#ifdef SH_3DS_GAME
void stage4_fs_game_allow_span(uint32_t file, void *data, uint32_t capacity)
{
    if (file >= FS_FILE_COUNT || !data || !capacity || capacity > 65536 || game_span_count == 2)
        game3ds_halt(438, "native FS span registration", file);
    game_spans[game_span_count].file = file; game_spans[game_span_count].data = data;
    game_spans[game_span_count++].capacity = capacity;
}
int stage4_fs_game_open(Stage4FsResult *r, PsxVram *v, const char *bin, const char *cue)
{
    memset(r, 0, sizeof(*r)); active = r; canonical = v; cd_lba = 0; tim_base = NULL;
    int status = PsxDisc_Open(&game_disc, bin, cue);
    if (status) { stage4_fs_fail(411, "PsxDisc_Open", (uint32_t)status); return 0; }
    game_mounted = 1;
    status = ShDisc_Init(&game_sh, &game_disc);
    if (status) { stage4_fs_fail(412, "ShDisc_Init", (uint32_t)status); return 0; }
    mounted = &game_sh;
    for (uint32_t id = 0; id < FS_FILE_COUNT; ++id) {
        ShDiscFile file;
        if (ShDisc_Resolve(mounted, id, &file) || file.lba != g_FileTable[id].startSector ||
            file.bytes != (uint32_t)g_FileTable[id].blockCount * FS_BLOCK_SIZE) {
            r->file_id = id; stage4_fs_fail(413, "original file table mismatch", id); return 0;
        }
    }
    Fs_QueueInitialize(); psx_vram_init(v); r->checkpoint = S4_FS_INIT;
    return 1;
}
void stage4_fs_game_close(void)
{
    if (game_mounted) PsxDisc_Close(&game_disc);
    game_mounted = 0; game_span_count = 0; mounted = NULL; canonical = NULL; active = NULL; tim_base = NULL;
}
void stage4_fs_game_observe(void)
{
    if (active) {
        active->state = g_FsQueue.state; active->substate = g_FsQueue.postLoadState;
        active->ticks++;
    }
}
#endif
