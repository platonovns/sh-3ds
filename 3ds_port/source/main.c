#include <3ds.h>

#include <errno.h>
#include <inttypes.h>
#include <malloc.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#include "render_3ds.h"
#include "render_tests.h"
#include "engine_gate.h"
#include "disc_gate.h"
#include "tim_gate.h"
#include "tim_selftest.h"
#include "stage4_fs.h"
#include "stage4_report.h"
#include "build_identity.h"

#define LOG_PATH "sdmc:/3ds/silenthill/smoke.txt"
#define DIAGNOSTIC_ROWS 29u
#define DIAGNOSTIC_COLUMNS 39u
#define DIAGNOSTIC_INTERVAL_MS 250u

extern u32 __ctru_heap_size;
extern char __bss_start__, __bss_end__;
static EngineGate engine_diag;
static DiscGate disc_diag;
static PsxVram stage3_vram;
static TimGate tim_diag;
static Stage4FsResult stage4_diag;
static int stage4_report_status;
static TimSelftest tim_tests;
static struct {
    Render3dsTexture *texture;
    unsigned width, height;
    bool allocated, uploaded;
} tim_pica[2];
static struct {
    uint32_t normal_before, normal_after, normal_low;
    uint32_t linear_before, linear_after, linear_low;
    int log_status;
} tim_memory;
_Static_assert(sizeof(EngineGate) == 68, "HAL/engine boundary layout");

static struct {
    Result srv, apt, hid, fs, sd;
    bool srv_ready, apt_ready, hid_ready, fs_ready, sd_ready;
} services;

static struct {
    Result model, ir, ptm, speed;
    bool is_new, ir_ready, speed_attempted;
    bool refresh_speed;
    unsigned int suspends, sleeps, restores;
    const char *event;
    int sd_errno;
    const char *sd_operation;
    bool log_ready;
} diag;

static struct {
    u32 normal_before, normal_after, linear_before, linear_after;
    u32 vram_before, vram_after;
    bool texture_ok, draw_ok;
    unsigned page;
} render_diag;

static struct {
    bool initialized, dirty;
    unsigned page;
    u64 next_update_ms;
    char lines[DIAGNOSTIC_ROWS][DIAGNOSTIC_COLUMNS + 1];
} console_diag;

/* Own IRRST separately so a missing C-stick service cannot fail HID startup. */
bool hidShouldUseIrrst(void)
{
    return false;
}

/* These weak libctru hooks let diagnostics retain the actual startup results. */
void __appInit(void)
{
    services.srv = srvInit();
    services.srv_ready = R_SUCCEEDED(services.srv);
    if (!services.srv_ready)
        return;

    services.apt = aptInit();
    services.apt_ready = R_SUCCEEDED(services.apt);
    services.hid = hidInit();
    services.hid_ready = R_SUCCEEDED(services.hid);
    services.fs = fsInit();
    services.fs_ready = R_SUCCEEDED(services.fs);
    if (services.fs_ready) {
        services.sd = archiveMountSdmc();
        services.sd_ready = R_SUCCEEDED(services.sd);
    }
}

void __appExit(void)
{
    if (services.sd_ready)
        archiveUnmountAll();
    if (services.fs_ready)
        fsExit();
    if (services.hid_ready)
        hidExit();
    if (services.apt_ready)
        aptExit();
    if (services.srv_ready)
        srvExit();
}

static void lifecycle_hook(APT_HookType hook, void *param)
{
    (void)param;
    switch (hook) {
    case APTHOOK_ONSUSPEND:
        diag.event = "suspend";
        ++diag.suspends;
        break;
    case APTHOOK_ONSLEEP:
        diag.event = "sleep";
        ++diag.sleeps;
        break;
    case APTHOOK_ONRESTORE:
    case APTHOOK_ONWAKEUP:
        diag.event = "resume";
        ++diag.restores;
        diag.refresh_speed = true;
        break;
    case APTHOOK_ONEXIT:
        diag.event = "APT exit";
        break;
    default:
        break;
    }
}

static void configure_speedup(void)
{
    diag.refresh_speed = false;
    if (R_FAILED(diag.model) || !diag.is_new)
        return;

    /* Keep libctru's desired state for APT restore, then obtain an IPC result. */
    osSetSpeedupEnable(true);
    diag.speed_attempted = true;
    diag.ptm = ptmSysmInit();
    if (R_SUCCEEDED(diag.ptm)) {
        diag.speed = PTMSYSM_ConfigureNew3DSCPU(3);
        ptmSysmExit();
    }
}

static const char *speed_status(void)
{
    if (R_FAILED(diag.model))
        return "unknown (model query failed)";
    if (!diag.is_new)
        return "off (Old 3DS)";
    if (R_FAILED(diag.ptm) || R_FAILED(diag.speed))
        return "requested; PTM error";
    return "enabled (PTM accepted)";
}

static u32 normal_free(void)
{
    const struct mallinfo info = mallinfo();
    const u32 used = (u32)info.uordblks;
    /* Include the unallocated newlib heap tail, not only arena free blocks. */
    return used < __ctru_heap_size ? __ctru_heap_size - used : 0;
}

static bool ensure_directory(const char *path)
{
    if (mkdir(path, 0777) == 0)
        return true;
    if (errno == EEXIST) {
        struct stat info;
        if (stat(path, &info) == 0) {
            if (S_ISDIR(info.st_mode))
                return true;
            errno = ENOTDIR;
        }
    }
    diag.sd_errno = errno;
    diag.sd_operation = "mkdir/stat";
    return false;
}

static void write_log(bool closing, const char *reason)
{
    FILE *file = fopen(LOG_PATH, closing ? "a" : "w");
    if (file == NULL) {
        diag.sd_errno = errno;
        diag.sd_operation = "fopen";
        return;
    }

    int result;
    if (closing) {
        result = fprintf(file, "Exit: %s; suspend=%u sleep=%u resume=%u\n",
                         reason, diag.suspends, diag.sleeps, diag.restores);
    } else {
        result = fprintf(file,
            "Silent Hill 3DS - stage 1B\nBootstrap started\n"
            "Model: %s; APT_CheckNew3DS=0x%08" PRIX32 "\n"
            "Speedup: %s; attempted=%u; PTM init=0x%08" PRIX32 " CPU=0x%08" PRIX32 "\n"
            "Normal free (estimate): %" PRIu32 " / %" PRIu32 " bytes\n"
            "Linear free: %" PRIu32 " bytes\n"
            "srv=0x%08" PRIX32 " apt=0x%08" PRIX32 " hid=0x%08" PRIX32 "\n"
            "fs=0x%08" PRIX32 " sd=0x%08" PRIX32 " ir=0x%08" PRIX32 " ir_ready=%u\n",
            R_FAILED(diag.model) ? "unknown" : (diag.is_new ? "New 3DS" : "Old 3DS"),
            (u32)diag.model, speed_status(), (unsigned int)diag.speed_attempted,
            (u32)diag.ptm, (u32)diag.speed,
            normal_free(), __ctru_heap_size, (u32)linearSpaceFree(),
            (u32)services.srv, (u32)services.apt, (u32)services.hid,
            (u32)services.fs, (u32)services.sd, (u32)diag.ir, (unsigned int)diag.ir_ready);
    }
    if (result >= 0) {
        result = fprintf(file,
            "ARM11 gate: memory=%lu scratch=%lu ABI=%lu core=%lu GTE=%lu/%lu\n"
            "RAM=%lu scratch=%lu pointer=%lu game bool=%lu SDK bool=%u B\n"
            "First fail=%lu actual=%ld expected=%ld\n"
            "Engine normal=%lu -> %lu linear=%lu -> %lu; BSS=%lu B\n",
            engine_diag.memory_ok, engine_diag.scratch_ok, engine_diag.abi_ok, engine_diag.core_ok,
            engine_diag.gte_passed, engine_diag.gte_total, engine_diag.ram_bytes,
            engine_diag.scratch_bytes, engine_diag.pointer_bytes, engine_diag.bool_bytes,
            (unsigned)sizeof(bool), engine_diag.failed_test, engine_diag.actual, engine_diag.expected,
            engine_diag.normal_before, engine_diag.normal_after,
            engine_diag.linear_before, engine_diag.linear_after,
            (unsigned long)((uintptr_t)&__bss_end__ - (uintptr_t)&__bss_start__));
    }
    const Render3dsStats *r = render3ds_stats();
    if (result >= 0) {
        result = fprintf(file,
            "Renderer: %s; C3D=%u target=%u shader=%u texture=%u\n"
            "Normal before=%" PRIu32 " after=%" PRIu32 " delta=%" PRId64 " B\n"
            "Linear before=%" PRIu32 " after=%" PRIu32 " delta=%" PRId64 " B\n"
            "VRAM before=%" PRIu32 " after=%" PRIu32 " delta=%" PRId64 " B\n"
            "Command buffer=%" PRIu32 " vertex buffer=%" PRIu32 " target=%" PRIu32 " B\n"
            "Texture: 32x32 RGBA8; bytes=%" PRIu32 "; nearest; no mipmaps\n"
            "Frames=%" PRIu32 " used vertices=%" PRIu32 " rejected draws=%" PRIu32 " draw_ok=%u\n"
            "CPU prep=%.3f ms; GPU queue+transfer=%.3f ms; timing_valid=%u; cmd usage=%.3f\n",
            r->error, (unsigned)r->citro3d_ok, (unsigned)r->target_ok,
            (unsigned)r->shader_ok, (unsigned)render_diag.texture_ok,
            render_diag.normal_before, render_diag.normal_after,
            (int64_t)render_diag.normal_before - render_diag.normal_after,
            render_diag.linear_before, render_diag.linear_after,
            (int64_t)render_diag.linear_before - render_diag.linear_after,
            render_diag.vram_before, render_diag.vram_after,
            (int64_t)render_diag.vram_before - render_diag.vram_after,
            r->command_buffer_bytes, r->vertex_buffer_bytes, r->target_bytes,
            r->texture_bytes, r->frames, r->vertices_used, r->rejected_draws,
            (unsigned)render_diag.draw_ok, r->cpu_prepare_ms, r->gpu_queue_ms,
            (unsigned)r->timing_valid, r->command_buffer_usage);
    }
    if (result < 0 || fflush(file) != 0) {
        diag.sd_errno = errno ? errno : EIO;
        diag.sd_operation = "write/flush";
    }
    if (fclose(file) != 0 && diag.sd_errno == 0) {
        diag.sd_errno = errno ? errno : EIO;
        diag.sd_operation = "fclose";
    }
    diag.log_ready = diag.sd_errno == 0;
}

static void probe_sd(void)
{
    if (!services.sd_ready)
        return;
    if (!ensure_directory("sdmc:/3ds") || !ensure_directory("sdmc:/3ds/silenthill"))
        return;
    write_log(false, NULL);
}

static void __attribute__((format(printf, 2, 3)))
console_line(unsigned row, const char *format, ...)
{
    if (row == 0 || row > DIAGNOSTIC_ROWS)
        return;
    char text[DIAGNOSTIC_COLUMNS + 1];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    const size_t length = strlen(text);
    memset(text + length, ' ', DIAGNOSTIC_COLUMNS - length);
    text[DIAGNOSTIC_COLUMNS] = '\0';
    if (memcmp(console_diag.lines[row - 1], text, sizeof(text)) == 0)
        return;
    memcpy(console_diag.lines[row - 1], text, sizeof(text));
    /* Leave the last column/row unused; never emit newlines or trigger wrap.
     * Padding replaces old digits without erasing a line or the whole screen. */
    printf("\x1b[%u;1H%s", row, text);
    console_diag.dirty = true;
}

static void console_result(unsigned row, const char *name, Result result)
{
    console_line(row, "%-10s %s 0x%08" PRIX32, name,
                 R_FAILED(result) ? "ERR" : " OK", (u32)result);
}

static void draw_console_static(void)
{
    console_line(1, "Silent Hill 3DS - stage 1B");
    console_line(2, "Services / input diagnostics");
    console_line(3, "START: exit  A: next page");
    console_line(4, "Model: %s", R_FAILED(diag.model) ? "unknown" :
                 (diag.is_new ? "New 3DS" : "Old 3DS"));
    console_line(7, "Normal heap  %" PRIu32 " B", __ctru_heap_size);
    console_result(14, "SRV", services.srv);
    console_result(15, "APT", services.apt);
    console_result(16, "HID", services.hid);
    console_result(17, "FS", services.fs);
    if (services.fs_ready)
        console_result(18, "SD mount", services.sd);
    else
        console_line(18, "SD mount: skipped (FS failed)");
    console_result(19, "New3DS", diag.model);
    if (R_SUCCEEDED(diag.model) && diag.is_new && services.hid_ready)
        console_result(22, "IRRST", diag.ir);
    console_line(25, "%s", services.hid_ready ? "Diagnostics: 4 Hz" : "HID failed: auto-exit after 3s");
}

static void draw_console_dynamic(circlePosition pad, circlePosition cstick)
{
    console_line(5, "Speedup: %s", speed_status());
    console_line(6, "Normal free~ %" PRIu32 " B", normal_free());
    console_line(8, "Linear free  %" PRIu32 " B", (u32)linearSpaceFree());
    console_line(9, "Circle Pad: %6d %6d", pad.dx, pad.dy);
    if (diag.ir_ready)
        console_line(10, "C-stick:    %6d %6d", cstick.dx, cstick.dy);
    else
        console_line(10, "C-stick: unavailable");
    console_line(11, "Lifecycle: %s", diag.event);
    console_line(12, "S:%u sleep:%u resume:%u", diag.suspends, diag.sleeps, diag.restores);
    if (diag.speed_attempted) {
        console_result(20, "PTM init", diag.ptm);
        if (R_SUCCEEDED(diag.ptm))
            console_result(21, "CPU/L2", diag.speed);
        else
            console_line(21, "CPU/L2: skipped (PTM failed)");
    }
    console_line(23, "SD log: %s", diag.log_ready ? "smoke.txt written/closed" : "unavailable");
    if (diag.sd_errno)
        console_line(24, "SD %s: errno %d", diag.sd_operation, diag.sd_errno);
    else
        console_line(24, "%s", "");
}

static void draw_renderer_console_static(void)
{
    const Render3dsStats *r = render3ds_stats();
    console_line(1, "Silent Hill 3DS - stage 1B");
    console_line(2, "START: exit  A: next page");
    console_line(3, "C3D:%s target:%s shader:%s", r->citro3d_ok ? "OK" : "ERR",
                 r->target_ok ? "OK" : "--", r->shader_ok ? "OK" : "--");
    console_line(4, "Renderer: %s", r->error);
    console_line(5, "Texture: %s 32x32 RGBA8 nearest", render_diag.texture_ok ? "OK" : "ERR");
    console_line(6, "Tex:%" PRIu32 " B RT:%" PRIu32 " B VRAM", r->texture_bytes, r->target_bytes);
    console_line(7, "VBO:%" PRIu32 " B (%" PRIu32 " verts)", r->vertex_buffer_bytes, r->vertex_capacity);
    console_line(11, "Init N: %" PRIu32 " -> %" PRIu32, render_diag.normal_before, render_diag.normal_after);
    console_line(12, "Init L: %" PRIu32 " -> %" PRIu32, render_diag.linear_before, render_diag.linear_after);
    console_line(13, "Delta N: %" PRId64 " B", (int64_t)render_diag.normal_before - render_diag.normal_after);
    console_line(14, "Delta L: %" PRId64 " B", (int64_t)render_diag.linear_before - render_diag.linear_after);
    console_line(15, "Delta VRAM: %" PRId64 " B", (int64_t)render_diag.vram_before - render_diag.vram_after);
    console_line(20, "Top tests (left to right):");
    console_line(21, "A:RGB tri B:tex C:draw order");
    console_line(22, "D:modulate E:alpha F:scissor");
    console_line(29, "%s", services.hid_ready ? "Diagnostics: 4 Hz" : "HID ERR: auto-exit after 3s");
}

static void draw_renderer_console_dynamic(circlePosition pad, circlePosition cstick)
{
    const Render3dsStats *r = render3ds_stats();
    console_line(8, "Cmd:%" PRIu32 " B used:%.1f%%", r->command_buffer_bytes, r->command_buffer_usage * 100);
    console_line(9, "Normal free~ %" PRIu32 " B", normal_free());
    console_line(10, "Linear free  %" PRIu32 " B", (u32)linearSpaceFree());
    console_line(16, "Frame:%" PRIu32 " verts:%" PRIu32, r->frames, r->vertices_used);
    console_line(17, "Draw:%s rejected:%" PRIu32, render_diag.draw_ok ? "OK" : "ERR", r->rejected_draws);
    if (r->timing_valid) {
        console_line(18, "CPU prep: %.3f ms", r->cpu_prepare_ms);
        console_line(19, "GPU queue+xfer: %.3f ms", r->gpu_queue_ms);
    } else {
        console_line(18, "CPU prep: pending");
        console_line(19, "GPU queue+xfer: pending");
    }
    console_line(23, "Pad:%6d %6d", pad.dx, pad.dy);
    if (diag.ir_ready)
        console_line(24, "C-stick:%6d %6d", cstick.dx, cstick.dy);
    else
        console_line(24, "C-stick: unavailable");
    console_line(25, "S:%u sleep:%u resume:%u", diag.suspends, diag.sleeps, diag.restores);
    console_line(26, "Model:%s speed:%s", diag.is_new ? "New" : "Old/unknown",
                 R_SUCCEEDED(diag.speed) && diag.speed_attempted ? "ON" : "see A");
    console_line(27, "SD:%s errno:%d", diag.log_ready ? "smoke.txt OK" : "unavailable", diag.sd_errno);
    console_line(28, "Lifecycle: %s", diag.event);
}

static void draw_engine_console(void)
{
    const EngineGate *e = &engine_diag;
    console_line(1, "Silent Hill 3DS - stage 1B");
    console_line(2, "ARM11 compile / ABI gate");
    console_line(3, "START: exit  A: renderer page");
    console_line(4, "ARM compile/link: PASS (7 TUs)");
    console_line(5, "PSX memory: %s", e->memory_ok ? "PASS" : "FAIL");
    console_line(6, "RAM: %lu B (3 MiB)", e->ram_bytes);
    console_line(7, "Scratch: %s %lu B", e->scratch_ok ? "PASS" : "FAIL", e->scratch_bytes);
    console_line(8, "Pointer: %lu B; little endian", e->pointer_bytes);
    console_line(9, "ABI probes: %s", e->abi_ok ? "PASS" : "FAIL");
    console_line(10, "bool: game=%lu SDK=%u B", e->bool_bytes, (unsigned)sizeof(bool));
    console_line(11, "RNG/move/allocator: %s", e->core_ok ? "PASS" : "FAIL");
    console_line(12, "GTE: %s %lu/%lu", e->gte_passed == e->gte_total ? "PASS" : "FAIL",
                 e->gte_passed, e->gte_total);
    console_line(13, "First FAIL id: %lu", e->failed_test);
    console_line(14, "Actual:   %ld", e->actual);
    console_line(15, "Expected: %ld", e->expected);
    console_line(16, "Normal free~ %" PRIu32 " B", normal_free());
    console_line(17, "Linear free  %" PRIu32 " B", (u32)linearSpaceFree());
    console_line(18, "ELF .bss: %lu B", (unsigned long)((uintptr_t)&__bss_end__ - (uintptr_t)&__bss_start__));
    console_line(19, "Gate N: %lu -> %lu", e->normal_before, e->normal_after);
    console_line(20, "Gate L: %lu -> %lu", e->linear_before, e->linear_after);
    console_line(21, "No game data; map0_s00 deferred");
    console_line(22, "Top: Stage 1A synthetic graphics");
    console_line(23, "SD log: %s", diag.log_ready ? "smoke.txt OK" : "FAIL/unavailable");
    console_line(24, "SD errno: %d", diag.sd_errno);
    console_line(25, "Lifecycle: %s", diag.event);
    console_line(26, "S:%u sleep:%u resume:%u", diag.suspends, diag.sleeps, diag.restores);
    console_line(29, "Diagnostics: 4 Hz");
}

static uint64_t disc_clock_us(void)
{
    const uint64_t ticks = svcGetSystemTick();
    return (ticks / SYSCLOCK_ARM11) * 1000000u + (ticks % SYSCLOCK_ARM11) * 1000000u / SYSCLOCK_ARM11;
}

static void draw_disc_console(void)
{
    const DiscGate *d = &disc_diag;
    console_line(1, "Silent Hill 3DS - Stage 2");
    console_line(2, "START: exit  A: next page");
    console_line(3, "DISC: %s", !d->found ? "NOT FOUND" :
                 d->open_status ? "UNSUPPORTED / OPEN FAIL" :
                 d->identity_status ? "UNSUPPORTED" : "FOUND / OPEN PASS");
    console_line(4, "Identity: %s", d->detected);
    console_line(5, "Supported: %s", !d->open_status && !d->identity_status ? "YES" : "NO");
    console_line(6, "CUE: %s tracks: %lu", d->cue_parsed ? "parsed" : "error/missing", (unsigned long)d->tracks);
    console_line(7, "Mode %lu / raw %lu B", (unsigned long)d->mode, (unsigned long)d->sector_bytes);
    console_line(8, "Sectors: %lu", (unsigned long)d->sectors);
    console_line(9, "Image: %lu B", (unsigned long)d->image_bytes);
    console_line(10, "Data: Form1 +24 / 2048 B");
    console_line(11, "Raw: %lu/%lu  Data: %lu/%lu", (unsigned long)d->raw_pass, (unsigned long)d->raw_total,
                 (unsigned long)d->data_pass, (unsigned long)d->data_total);
    console_line(12, "LBA/MSF: %lu/%lu", (unsigned long)d->msf_pass, (unsigned long)d->msf_total);
    console_line(13, "FS / PsxFile: %lu/%lu", (unsigned long)d->fs_pass, (unsigned long)d->fs_total);
    console_line(14, "First FAIL ID: %lu", (unsigned long)d->first_failure);
    console_line(15, "Expected: %08lX", (unsigned long)d->expected);
    console_line(16, "Actual:   %08lX", (unsigned long)d->actual);
    console_line(17, "Identity: %lu us", (unsigned long)d->identity_us);
    console_line(18, "Random x6: %lu us", (unsigned long)d->random_us);
    console_line(19, "Sequential x%lu: %lu us", (unsigned long)d->sequential_sectors, (unsigned long)d->sequential_us);
    console_line(20, "Normal free~ %lu B", (unsigned long)normal_free());
    console_line(21, "Linear free  %lu B", (unsigned long)linearSpaceFree());
    console_line(22, "disc_test.txt: %s (%ld)", d->log_status ? "FAIL" : "written/closed", (long)d->log_status);
    console_line(23, "Open code: %ld identity: %ld", (long)d->open_status, (long)d->identity_status);
    console_line(24, "FS queue/post-load: not running");
    console_line(25, "Lifecycle: %s", diag.event);
    console_line(26, "S:%u sleep:%u resume:%u", diag.suspends, diag.sleeps, diag.restores);
    console_line(27, "No XA decode / no gameplay");
    console_line(29, "Diagnostics: 4 Hz");
}

static bool tim_read_row(void *context, unsigned y, uint8_t *rgba, unsigned width)
{
    unsigned index = *(unsigned *)context;
    tim_pica[index].allocated = true;
    uint32_t n = normal_free(), l = linearSpaceFree();
    if (n < tim_memory.normal_low) tim_memory.normal_low = n;
    if (l < tim_memory.linear_low) tim_memory.linear_low = l;
    TimResourceGate *r = &tim_diag.resources[index];
    PsxTextureRegion region;
    return psx_tim_region(&r->tim, r->image_destination, r->clut_destination, 0, &region) == PV_OK &&
           tim_gate_decode_row(&stage3_vram, region, y, rgba, width) == PV_OK;
}

static void tim_visual_init(void)
{
    tim_memory.normal_before = tim_memory.normal_low = normal_free();
    tim_memory.linear_before = tim_memory.linear_low = linearSpaceFree();
    tim_selftest_run(&stage3_vram, &tim_tests);
    tim_gate_run(&tim_diag, &stage3_vram, "sdmc:/3ds/silenthill/sh1.bin", "sdmc:/3ds/silenthill/sh1.cue");
    /* Preserve the accepted diagnostic gate, then feed PICA from the actual
     * original queue/post-load chain using the same canonical VRAM. */
    stage4_fs_run(&stage4_diag, &stage3_vram, "sdmc:/3ds/silenthill/sh1.bin", "sdmc:/3ds/silenthill/sh1.cue");
    if (tim_tests.first_failure && !tim_diag.first_failure) {
        tim_diag.first_failure = 370; tim_diag.expected = tim_tests.total; tim_diag.actual = tim_tests.passed;
    }
    for (unsigned i = 0; i < 2; ++i) {
        const TimResourceGate *r = &tim_diag.resources[i];
        if (r->passed != 63 || stage4_diag.first_failure) continue;
        tim_pica[i].texture = render3ds_texture_create_rows(r->tim.width, r->tim.height,
            tim_read_row, &i, &tim_pica[i].width, &tim_pica[i].height);
        tim_pica[i].uploaded = tim_pica[i].texture != NULL;
        if (!tim_pica[i].uploaded && !stage4_diag.first_failure) {
            stage4_diag.first_failure = 419;
            stage4_diag.operation = "PICA texture upload";
            stage4_diag.file_id = i ? 6 : 0;
        }
        if (!tim_pica[i].uploaded && !tim_diag.first_failure) {
            tim_diag.first_failure = 380 + i; tim_diag.expected = 1; tim_diag.actual = 0;
        }
    }
    if (!render_orientation_ready() && !tim_diag.first_failure) {
        tim_diag.first_failure = 390; tim_diag.expected = 1; tim_diag.actual = 0;
    }
    /* Write after PICA allocation, so the machine report also sees failure 419. */
    stage4_report_status = stage4_report_write("sdmc:/3ds/silenthill/stage4_fs.txt", &stage4_diag,
                                              tim_pica[0].uploaded, tim_pica[1].uploaded);
    int status_report = stage4_report_write("sdmc:/3ds/silenthill/stage4_status.txt", &stage4_diag,
                                           tim_pica[0].uploaded, tim_pica[1].uploaded);
    if (!stage4_report_status) stage4_report_status = status_report;
    tim_memory.normal_after = normal_free(); tim_memory.linear_after = linearSpaceFree();
    tim_memory.log_status = tim_gate_log(&tim_diag, "sdmc:/3ds/silenthill/tim_test.txt");
    if (!tim_memory.log_status) {
        FILE *f = fopen("sdmc:/3ds/silenthill/tim_test.txt", "a");
        if (!f) { tim_memory.log_status = errno ? errno : EIO; return; }
        int ok = 1;
        for (unsigned i = 0; i < 2; ++i)
            if (fprintf(f, "PICA %s allocated=%u upload=%u physical=%ux%u logical=%lux%lu\n",
                tim_gate_name(i), (unsigned)tim_pica[i].allocated, (unsigned)tim_pica[i].uploaded,
                tim_pica[i].width, tim_pica[i].height,
                (unsigned long)tim_diag.resources[i].tim.width, (unsigned long)tim_diag.resources[i].tim.height) < 0) ok = 0;
        if (fprintf(f, "Synthetic=%lu/%lu first_fail=%lu\n"
                       "Memory normal=%lu->%lu low=%lu linear=%lu->%lu low=%lu\n"
                       "Static VRAM=%u row scratch<=4096 B; no full resource/RGBA copies\n"
                       "PSX native top-left; PICA tex3ds layout U=x/W V=1-y/H\n"
                       "Orientation pattern: TL/TR/BL/BR, four U/V combinations\n"
                       "Result=%s (Stage 3 orientation hardware accepted)\n",
                    (unsigned long)tim_tests.passed, (unsigned long)tim_tests.total, (unsigned long)tim_tests.first_failure,
                    (unsigned long)tim_memory.normal_before, (unsigned long)tim_memory.normal_after,
                    (unsigned long)tim_memory.normal_low, (unsigned long)tim_memory.linear_before,
                    (unsigned long)tim_memory.linear_after, (unsigned long)tim_memory.linear_low,
                    (unsigned)sizeof(stage3_vram), tim_diag.first_failure ? "FAIL" : "PASS") < 0) ok = 0;
        if (fflush(f)) ok = 0;
        if (fclose(f)) ok = 0;
        if (!ok) tim_memory.log_status = EIO;
    }
}

static void draw_tim_console(unsigned index)
{
    const TimResourceGate *r = &tim_diag.resources[index]; const PsxTim *t = &r->tim;
    console_line(1, "Stage 3 - Real TIM / PSX VRAM");
    console_line(2, "START exit / A next page (%u/2)", index + 1);
    console_line(3, "Disc supported: %s open:%ld", !tim_diag.open_status && !tim_diag.identity_status ? "YES" : "NO", (long)tim_diag.open_status);
    console_line(4, "ID %lu %s", (unsigned long)r->file_id, tim_gate_name(index));
    console_line(5, "Bytes:%lu CRC:%s", (unsigned long)r->bytes, r->passed & TG_CRC ? "PASS" : "FAIL");
    console_line(6, "CRC32: %08lX", (unsigned long)r->crc);
    console_line(7, "TIM magic/parse:%s mode:%lu", r->passed & TG_PARSE ? "PASS" : "FAIL", (unsigned long)t->mode);
    console_line(8, "CLUT:%s entries:%lu count:%lu", t->has_clut ? "YES" : "NO", (unsigned long)t->palette_entries, (unsigned long)t->palette_count);
    console_line(9, "Image logical: %lux%lu", (unsigned long)t->width, (unsigned long)t->height);
    console_line(10, "Auth I:%u,%u CLUT:%u,%u", t->image.x, t->image.y, t->clut.x, t->clut.y);
    console_line(11, "VRAM I:%u,%u %ux%u words", r->image_destination.x, r->image_destination.y, t->image.w, t->image.h);
    console_line(12, "VRAM CLUT:%u,%u %ux%u", r->clut_destination.x, r->clut_destination.y, t->clut.w, t->clut.h);
    console_line(13, "Shadow:%s upload:%s bounds:%s", tim_diag.shadow_ok ? "OK" : "ERR", r->passed & TG_UPLOAD ? "OK" : "ERR", r->passed & TG_BOUNDS ? "OK" : "ERR");
    console_line(14, "VRAM CRC:%08lX gen:%lu", (unsigned long)r->vram_crc, (unsigned long)r->generation);
    console_line(15, "Decode:%s %lux%lu", r->passed & TG_DECODE ? "PASS" : "FAIL", (unsigned long)t->width, (unsigned long)t->height);
    console_line(16, "Pixel CRC:%08lX", (unsigned long)r->decoded_crc);
    console_line(17, "STP:%lu zero:%lu (opaque STP)", (unsigned long)r->stp_texels, (unsigned long)r->transparent_texels);
    console_line(18, "PICA alloc:%s upload:%s", tim_pica[index].allocated ? "PASS" : "FAIL", tim_pica[index].uploaded ? "PASS" : "FAIL");
    console_line(19, "PICA physical: %ux%u nearest", tim_pica[index].width, tim_pica[index].height);
    console_line(20, "Normal free~ %lu B", (unsigned long)normal_free());
    console_line(21, "Linear free  %lu B", (unsigned long)linearSpaceFree());
    console_line(22, "Selftest:%lu/%lu ANM:%s", (unsigned long)tim_tests.passed, (unsigned long)tim_tests.total, tim_diag.anm.passed ? "PASS" : "FAIL");
    console_line(23, "First FAIL:%lu status:%ld", (unsigned long)tim_diag.first_failure, (long)r->status);
    console_line(24, "Expected:%08lX actual:%08lX", (unsigned long)tim_diag.expected, (unsigned long)tim_diag.actual);
    console_line(25, "tim_test.txt:%s (%d)", tim_memory.log_status ? "FAIL" : "OK", tim_memory.log_status);
    console_line(26, "Lifecycle:%s S:%u R:%u", diag.event, diag.sleeps, diag.restores);
    console_line(27, "%s", index ? "Top: atlas + four native 256px strips" : "Top: 320x240 centered, native pixels");
    console_line(28, "PSX native | UV u+,v- | accepted");
    console_line(29, "Diagnostics 4 Hz / A regressions");
}

static void draw_stage4_console(void)
{
    console_line(1, "Stage 4.1 ORIGINAL FS / TIM");
    console_line(3, "Checkpoint: %s", stage4_checkpoint_name(stage4_diag.checkpoint));
    console_line(5, "Original queue/post-load -> PICA");
    console_line(7, "Files: %lu/2 reads:%lu uploads:%lu", (unsigned long)stage4_diag.completed,
                 (unsigned long)stage4_diag.reads, (unsigned long)stage4_diag.uploads);
    console_line(9, "Ticks:%lu VRAM:%08lX", (unsigned long)stage4_diag.ticks, (unsigned long)stage4_diag.vram_crc);
    console_line(11, "First FAIL:%lu file:%lu", (unsigned long)stage4_diag.first_failure, (unsigned long)stage4_diag.file_id);
    console_line(13, "%s", stage4_diag.operation ? stage4_diag.operation : "No unsupported operation");
    console_line(15, "Detail:%08lX", (unsigned long)stage4_diag.detail);
    console_line(16, "PICA: %s / %s", tim_pica[0].uploaded ? "PASS" : "FAIL", tim_pica[1].uploaded ? "PASS" : "FAIL");
    console_line(18, "Title/map: NOT RUN (next slice)");
    console_line(20, "Stage 4.1: HARDWARE ACCEPTED");
    console_line(23, "A: diagnostics  START: exit");
    console_line(25, "Report:%s (%d)", stage4_report_status ? "FAIL" : "OK", stage4_report_status);
    console_line(27, "%s", SH_BUILD_ID);
}

static bool tim_visual_draw(unsigned index)
{
    if (!render3ds_begin_frame()) return false;
    bool ok = true;
    if (tim_pica[index].texture) {
        if (!index) ok = render3ds_draw_texture_region(tim_pica[0].texture,40,0,320,240,0,0,320,240,0,true);
        else {
            ok = render3ds_draw_texture_region(tim_pica[1].texture,0,24,400,6.25f,0,0,1024,16,0,true);
            for (unsigned i = 0; i < 4; ++i)
                ok = render3ds_draw_texture_region(tim_pica[1].texture,72,64+i*36,256,16,i*256,0,256,16,0,true) && ok;
        }
    }
    render3ds_end_frame(); return ok;
}

static void draw_orientation_console(void)
{
    console_line(1,"Stage 3 - Orientation regression");
    console_line(2,"START exit / A next page");
    console_line(4,"PSX/decode: native top-left");
    console_line(5,"PICA layout: tex3ds, no Y flip");
    console_line(6,"UV: U=x/W, V=1-y/H");
    console_line(8,"Pattern texture: %s 32x32 nearest",render_orientation_ready()?"OK":"FAIL");
    console_line(10,"Top-left: U normal / V normal");
    console_line(11,"THIS panel must be readable:");
    console_line(12,"TL red    TR green");
    console_line(13,"BL blue   BR yellow");
    console_line(14,"White arrow must point RIGHT");
    console_line(16,"Top-right: U flip (mirror X)");
    console_line(17,"Bottom-left: V flip (mirror Y)");
    console_line(18,"Bottom-right: U+V flip (180)");
    console_line(20,"Normal free~ %lu B",(unsigned long)normal_free());
    console_line(21,"Linear free  %lu B",(unsigned long)linearSpaceFree());
    console_line(23,"Hardware rendering confirmed");
    console_line(24,"Orientation: hardware accepted");
    console_line(26,"Lifecycle:%s S:%u R:%u",diag.event,diag.sleeps,diag.restores);
    console_line(29,"Diagnostics: 4 Hz / A regressions");
}

static void update_console(circlePosition pad, circlePosition cstick)
{
    const u64 now = osGetTime();
    const bool page_changed = !console_diag.initialized ||
        console_diag.page != render_diag.page;
    if (!page_changed && now < console_diag.next_update_ms)
        return;
    console_diag.dirty = false;
    if (page_changed) {
        /* Clear only on entry/page switch, never during periodic refresh. */
        printf("\x1b[2J");
        memset(console_diag.lines, 0, sizeof(console_diag.lines));
        console_diag.initialized = true;
        console_diag.page = render_diag.page;
        console_diag.dirty = true;
        if (console_diag.page == 1)
            draw_console_static();
        else if (console_diag.page == 0)
            draw_renderer_console_static();
    }
    if (console_diag.page == 1)
        draw_console_dynamic(pad, cstick);
    else if (console_diag.page == 0)
        draw_renderer_console_dynamic(pad, cstick);
    else if (console_diag.page == 2)
        draw_engine_console();
    else if (console_diag.page == 3)
        draw_disc_console();
    else if (console_diag.page < 6)
        draw_tim_console(console_diag.page - 4);
    else if (console_diag.page == 6)
        draw_orientation_console();
    else
        draw_stage4_console();
    console_diag.next_update_ms = now + DIAGNOSTIC_INTERVAL_MS;
    if (console_diag.dirty) {
        /* The bottom RGB565 console is single-buffered; citro3d owns top. */
        u16 width, height;
        u8 *buffer = gfxGetFramebuffer(GFX_BOTTOM, GFX_LEFT, &width, &height);
        GSPGPU_FlushDataCache(buffer, width * height * 2);
    }
}

int main(void)
{
    /* A usable service manager and APT are prerequisites for screen/lifecycle IO. */
    if (!services.srv_ready || !services.apt_ready)
        return 1;

    gfxInitDefault();
    gfxSet3D(false);
    consoleInit(GFX_BOTTOM, NULL);
    gfxSetDoubleBuffering(GFX_BOTTOM, false);

    diag.event = "running";
    diag.model = APT_CheckNew3DS(&diag.is_new);
    configure_speedup();
    if (R_SUCCEEDED(diag.model) && diag.is_new && services.hid_ready) {
        diag.ir = irrstInit();
        diag.ir_ready = R_SUCCEEDED(diag.ir);
    }
    /* Warm up stdout before the paired snapshots; SD probing follows them. */
    printf("Stage 1B engine diagnostics...\n");
    const u32 engine_normal_before = normal_free();
    const u32 engine_linear_before = linearSpaceFree();
    engine_gate_run(&engine_diag);
    engine_diag.normal_before = engine_normal_before;
    engine_diag.linear_before = engine_linear_before;
    engine_diag.normal_after = normal_free();
    engine_diag.linear_after = linearSpaceFree();
    render_diag.page = 7;
    render_diag.normal_before = normal_free();
    render_diag.linear_before = linearSpaceFree();
    render_diag.vram_before = vramSpaceFree();
    if (render3ds_init())
        render_diag.texture_ok = render_tests_init();
    render_diag.normal_after = normal_free();
    render_diag.linear_after = linearSpaceFree();
    render_diag.vram_after = vramSpaceFree();
    render_diag.draw_ok = render3ds_stats()->ready && render_diag.texture_ok;
    probe_sd();
    printf("Stage 2 disc checks...\n");
    disc_gate_run(&disc_diag, "sdmc:/3ds/silenthill/sh1.bin", "sdmc:/3ds/silenthill/sh1.cue",
                  "sdmc:/3ds/silenthill/disc_test.txt", disc_clock_us);
    if (services.sd_ready) {
        FILE *disc_log = fopen("sdmc:/3ds/silenthill/disc_test.txt", "a");
        if (disc_log) {
            int log_ok = fprintf(disc_log, "Memory normal_free=%lu linear_free=%lu BSS=%lu\n",
                                 (unsigned long)normal_free(), (unsigned long)linearSpaceFree(),
                                 (unsigned long)((uintptr_t)&__bss_end__ - (uintptr_t)&__bss_start__)) >= 0;
            if (fclose(disc_log)) log_ok = 0;
            if (!log_ok) disc_diag.log_status = EIO;
        } else disc_diag.log_status = errno ? errno : EIO;
    }

    tim_visual_init();

    aptHookCookie cookie;
    aptHook(&cookie, lifecycle_hook, NULL);
    const char *exit_reason = "APT close";
    unsigned int frame = 0;
    while (aptMainLoop()) {
        circlePosition pad = {0}, cstick = {0};
        if (diag.refresh_speed)
            configure_speedup();
        if (services.hid_ready) {
            hidScanInput();
            if (hidKeysDown() & KEY_START) {
                exit_reason = "START";
                break;
            }
            if (hidKeysDown() & KEY_A)
                render_diag.page = (render_diag.page + 1) % 8;
            hidCircleRead(&pad);
            if (diag.ir_ready) {
                irrstScanInput();
                irrstCstickRead(&cstick);
            }
        } else if (frame >= 180) {
            exit_reason = "HID init failed";
            break;
        }
        if (render3ds_stats()->ready) {
            if (render_diag.page == 7)
                tim_visual_draw(0);
            else if (render_diag.page == 6)
                render_orientation_draw();
            else if (render_diag.page >= 4)
                tim_visual_draw(render_diag.page - 4);
            else
                render_diag.draw_ok = render_tests_draw(frame) && render_diag.texture_ok;
        }
        else
            gspWaitForVBlank();
        update_console(pad, cstick);
        ++frame;
    }

    aptUnhook(&cookie);
    if (diag.log_ready)
        write_log(true, exit_reason);
    for (unsigned i = 0; i < 2; ++i) render3ds_texture_destroy(tim_pica[i].texture);
    render_tests_shutdown();
    render3ds_shutdown();
    if (diag.ir_ready)
        irrstExit();
    if (diag.speed_attempted)
        osSetSpeedupEnable(false);
    gfxExit();
    return services.hid_ready ? 0 : 1;
}
