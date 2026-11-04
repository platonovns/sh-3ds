/* Hardware diagnostic only. No game worker, renderer, or scheduling changes. */
#if defined(SH_CPU_AUDIT_RECORDER)
#include "game_cpu_recorder.h"
#include "game_profile.h"
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
#define RIGHT_BIT (1u<<4)
#endif
#if defined(SH_STAGE11A_TRACEFIX)
#include "stage11a_pitch_trace.h"
#define LEFT_BIT (1u<<5)
#else
#define LEFT_BIT 0u
#endif
#if defined(SH_STAGE11A)
#include "stage11a_perf.h"
#endif
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define SELECT_BIT (1u<<2)
#define DOWN_BIT (1u<<7)
#define START_BIT (1u<<3)
#define TICKS_PER_MS 268123.480
#if defined(SH_STAGE11A_CPU)
#define RECORD_VARIANT "STAGE11A_CPU_CANDIDATE"
#elif defined(SH_STAGE11A_TRACEFIX)
#define RECORD_VARIANT "STAGE11A_LIFETIME_TRACE_FIX_CANDIDATE"
#elif defined(SH_STAGE11A_LIFETIME)
#define RECORD_VARIANT "STAGE11A_LIFETIME_INVESTIGATION"
#elif defined(SH_STAGE11A)
#define RECORD_VARIANT "STAGE11A_CONTROL_INSTRUMENTED"
#else
#define RECORD_VARIANT "CPU_AUDIT_RECORDER_ONLY"
#endif
static char directory[256];
static const char *build_id;
static unsigned next_index,active,pending,chord_latched,select_pending,error_code,last_saved;
static unsigned changed,ui_dirty,ui_second=UINT_MAX;
static uint64_t begin_tick,end_tick;
static CpuRecordContext begin_context,end_context;
static CpuRecordSnapshot before,after;
static const char *stop_reason;
static const char *const scopes[]={"spu_block","spu_wait","xa_step","xa_wait","flashlight_setup","resolve"};
static unsigned differences(const CpuRecordContext *a,const CpuRecordContext *b)
{
    return (a->game!=b->game?1u:0)|(a->map!=b->map || a->room!=b->room?2u:0)|
        (a->flashlight!=b->flashlight?4u:0)|(a->fps_mode!=b->fps_mode?8u:0)|
        (a->control_mode!=b->control_mode?16u:0)|
        (a->x!=b->x || a->z!=b->z || a->yaw!=b->yaw?32u:0)|
        (memcmp(a->view,b->view,sizeof(a->view))?64u:0);
}
void cpu_recorder_init(const char *path,const char *build)
{
#if defined(SH_STAGE11A_LIFETIME)
    stage11a_lifetime_init();
#endif
    active=pending=chord_latched=select_pending=error_code=last_saved=changed=0;
    next_index=1;build_id=build;ui_dirty=1;ui_second=UINT_MAX;
    if(snprintf(directory,sizeof(directory),"%s",path)>=(int)sizeof(directory)) {error_code=ENAMETOOLONG;return;}
    DIR *d=opendir(directory);
    if(!d){error_code=errno;return;}
    unsigned maximum=0;
    for(;;) {
        errno=0;struct dirent *e=readdir(d);
        if(!e){if(errno)error_code=errno;break;}
        if(strncmp(e->d_name,"cpu_audit_",10) || e->d_name[10]<'0' || e->d_name[10]>'9')continue;
        char *tail;errno=0;unsigned long n=strtoul(e->d_name+10,&tail,10);
        if(strcmp(tail,".txt"))continue;
        if(errno==ERANGE || n>=UINT_MAX){error_code=EOVERFLOW;break;}
        if(n>maximum)maximum=(unsigned)n;
    }
    if(closedir(d) && !error_code)error_code=errno;
    if(!error_code)next_index=maximum+1;
}
static void context_report(FILE *out,const char *name,const CpuRecordContext *c)
{
    fprintf(out,"sample_%s_context=%lu,%lu,%lu,%s,%lu,%lu,%ld,%ld,%ld",
        name,(unsigned long)c->game,(unsigned long)c->map,(unsigned long)c->room,
        c->flashlight?"ON":"OFF",(unsigned long)c->fps_mode,(unsigned long)c->control_mode,
        (long)c->x,(long)c->z,(long)c->yaw);
    for(unsigned i=0;i<6;i++)fprintf(out,",%ld",(long)c->view[i]);
    fputc('\n',out);
}
static void write_sample(void)
{
    /* Reserve atomically; startup scanning is not a substitute for O_EXCL.
     * Existing files, even empty/incomplete ones, are never opened for write. */
    char path[320];int fd=-1;unsigned number=0;
    for(unsigned tries=0;tries<1024 && next_index && next_index<UINT_MAX;tries++) {
        number=next_index++;
        snprintf(path,sizeof(path),"%s/cpu_audit_%03u.txt",directory,number);
        fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0666);
        if(fd>=0)break;
        if(errno!=EEXIST){error_code=errno;ui_dirty=1;return;}
    }
    if(fd<0){error_code=EOVERFLOW;ui_dirty=1;return;}
    FILE *out=fdopen(fd,"w");
    if(!out){error_code=errno;close(fd);ui_dirty=1;return;}
    static char buffer[8192];
    setvbuf(out,buffer,_IOFBF,sizeof(buffer));
    double duration=(end_tick-begin_tick)/TICKS_PER_MS;
    unsigned frames=end_context.lcd_frames-begin_context.lcd_frames;
    fprintf(out,"cpu_record_schema=1\nbuild=%s\nbuild_variant=" RECORD_VARIANT "\n"
        "sample_number=%u\nsample_stop_reason=%s\nsample_duration_ms=%.4f\n"
        "sample_map=%lu\nsample_room=%lu\nsample_flashlight=%s\nsample_fps_mode=%lu\n"
        "sample_control_mode=%lu\nsample_control_name=%s\n"
        "sample_lcd_frames=%u\nsample_lcd_fps=%.4f\nsample_context_changed_mask=0x%X\n"
        "sample_changed_schema=game:1,map_room:2,flashlight:4,fps:8,control:16,player_pose:32,camera:64\n"
        "sample_context_schema=game,map,room,flashlight,fps_mode,control_mode,x,z,yaw,camera_x,camera_y,camera_z,camera_pitch,camera_yaw,camera_roll\n"
        "sample_cpu_basis=COMPLETED_CALL_DELTAS_INCLUDING_PREEMPTION_AND_BLOCKING\n"
        "sample_cpu_boundary=IN_FLIGHT_WORKER_CALLS_MAY_STRADDLE_BOUNDARIES\n"
        "sample_cpu_schema=valid,calls,total_elapsed_ms,mean_elapsed_ms\n",
        build_id,number,stop_reason,duration,(unsigned long)begin_context.map,(unsigned long)begin_context.room,
        begin_context.flashlight?"ON":"OFF",(unsigned long)begin_context.fps_mode,
        (unsigned long)begin_context.control_mode,
        begin_context.control_mode==0?"Tank":begin_context.control_mode==1?"Modern":"Hybrid",
        frames,duration>0?frames*1000.0/duration:0,changed);
    context_report(out,"start",&begin_context);context_report(out,"end",&end_context);
    for(unsigned i=0;i<GCPU_SCOPES;i++) {
        unsigned valid=(before.valid&after.valid&(1u<<i))!=0;
        unsigned calls=after.calls[i]-before.calls[i];
        uint64_t ticks=after.ticks[i]-before.ticks[i];
        fprintf(out,"sample_cpu_%s=%u,%u,%.4f,%.4f\n",scopes[i],valid,
            valid?calls:0,valid?ticks/TICKS_PER_MS:0,valid && calls?ticks/TICKS_PER_MS/calls:0);
    }
    game_prof_sample_report(out);
#if defined(SH_STAGE11A_LIFETIME)
    stage11a_lifetime_report(out);
#endif
#if defined(SH_STAGE11A)
    stage11a_perf_report(out);stage11a_audio_report(out);stage11a_renderer_report(out);
#endif
    /* Preserve all original counters with a distinct, explicit lifetime scope.
     * Their report runs after the stop snapshot; SD writing is outside it. */
    fputs("reference_scope=LIFETIME_AT_SAVE_NOT_RECORDING_WINDOW\n",out);
    game_cpu_audit_report(out);
    int failure=ferror(out)?EIO:0;
    if(fflush(out) && !failure)failure=errno?errno:EIO;
    if(!failure && fsync(fd))failure=errno?errno:EIO;
    if(!failure) {
        if(fputs("sample_complete=1\nreport_complete=1\n",out)<0)failure=errno?errno:EIO;
        if(fflush(out) && !failure)failure=errno?errno:EIO;
        if(!failure && fsync(fd))failure=errno?errno:EIO;
    }
    if(fclose(out) && !failure)failure=errno?errno:EIO;
    /* Retain a failed sample in RAM for another chord/retry into a NEW file.
     * Leave partial files on SD as evidence; never truncate/reuse their index. */
    error_code=failure;
    if(!failure){pending=0;last_saved=number;}
    ui_dirty=1;
}
void cpu_recorder_finish(const CpuRecordContext *c,const char *reason)
{
    if(active) {
        end_tick=game_prof_clock();end_context=*c;changed|=differences(&begin_context,c);
        game_cpu_audit_snapshot(&after);game_prof_sample_stop();
#if defined(SH_STAGE11A)
        stage11a_perf_stop();stage11a_audio_boundary(0);stage11a_renderer_boundary(0);
#if defined(SH_STAGE11A_LIFETIME)
        stage11a_lifetime_boundary(0);
#endif
#endif
        active=0;pending=1;stop_reason=reason;
    }
    if(pending)write_sample();
}
static void toggle(const CpuRecordContext *c)
{
    if(active || pending){cpu_recorder_finish(c,"BUTTON_CHORD");return;}
    if(error_code){ui_dirty=1;return;}
    begin_context=*c;begin_tick=game_prof_clock();changed=0;
    game_cpu_audit_snapshot(&before);game_prof_sample_start();
#if defined(SH_STAGE11A)
    stage11a_audio_boundary(1);stage11a_renderer_boundary(1);stage11a_perf_start();
#if defined(SH_STAGE11A_LIFETIME)
    stage11a_lifetime_boundary(1);
#endif
#endif
    active=1;ui_dirty=1;ui_second=UINT_MAX;
}
uint32_t cpu_recorder_input(uint32_t held,const CpuRecordContext *c)
{
    if(active)changed|=differences(&begin_context,c);
    /* Final dump has priority, including when Down is still held. */
    if((held&(START_BIT|SELECT_BIT))==(START_BIT|SELECT_BIT)) {
        select_pending=0;chord_latched=1;return held;
    }
    if(chord_latched) {
#if defined(SH_STAGE11A_LIFETIME)
        if(!(held&(SELECT_BIT|DOWN_BIT|RIGHT_BIT|LEFT_BIT)))chord_latched=0;
        return held&~(SELECT_BIT|DOWN_BIT|RIGHT_BIT|LEFT_BIT);
#else
        if(!(held&(SELECT_BIT|DOWN_BIT)))chord_latched=0;
        return held&~(SELECT_BIT|DOWN_BIT);
#endif
    }
    if(held&SELECT_BIT) {
        select_pending=1;
#if defined(SH_STAGE11A_LIFETIME)
#if defined(SH_STAGE11A_TRACEFIX)
        if(held&LEFT_BIT) {
            select_pending=0;chord_latched=1;ui_dirty=1;
            if(!active && !pending)game_spu_silent_fast_toggle();
            return held&~(SELECT_BIT|DOWN_BIT|RIGHT_BIT|LEFT_BIT);
        }
#endif
        if(held&RIGHT_BIT) {
            select_pending=0;chord_latched=1;ui_dirty=1;
            if(!active && !pending)stage11a_lifetime_toggle();
            return held&~(SELECT_BIT|DOWN_BIT|RIGHT_BIT);
        }
#endif
        if(held&DOWN_BIT) {select_pending=0;chord_latched=1;toggle(c);}
        return held&~(SELECT_BIT|DOWN_BIT);
    }
    if(select_pending) {select_pending=0;return held|SELECT_BIT;}
    return held;
}
int cpu_recorder_label(char *out,size_t size)
{
    unsigned seconds=active?(unsigned)((game_prof_clock()-begin_tick)/(uint64_t)268123480):0;
    if(!ui_dirty && (!active || seconds==ui_second))return 0;
    ui_second=seconds;ui_dirty=0;
    if(error_code)snprintf(out,size,"CPU ! %u",error_code);
    else if(active)snprintf(out,size,"CPU REC %02u:%02u",seconds/60,seconds%60);
    else if(last_saved)snprintf(out,size,"CPU #%03u OK",last_saved);
    else snprintf(out,size,"CPU SELECT + v");
#if defined(SH_STAGE11A_LIFETIME)
    size_t used=strlen(out);if(used<size)snprintf(out+used,size-used," P%u",stage11a_lifetime_mode());
#endif
#if defined(SH_STAGE11A_TRACEFIX)
    size_t used_fix=strlen(out);if(used_fix<size)snprintf(out+used_fix,size-used_fix," F%u",game_spu_silent_fast_enabled());
#endif
    return 1;
}
void cpu_recorder_reference(FILE *out)
{
    fprintf(out,"cpu_recorder=DIAGNOSTIC_ONLY\ncpu_recording=%u\ncpu_record_pending=%u\n"
        "cpu_record_next_index=%u\ncpu_record_last_saved=%u\ncpu_record_errno=%u\n",
        active,pending,next_index,last_saved,error_code);
}
#endif
