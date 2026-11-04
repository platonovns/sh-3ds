#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define SH_CPU_AUDIT_RECORDER 1
static unsigned fail_sync;
static int test_fsync(int fd)
{if(fail_sync){fail_sync--;errno=EIO;return -1;}return fsync(fd);}
#define fsync test_fsync
#include "../source/game_cpu_recorder.c"
#undef fsync
static uint64_t ticks;
static CpuRecordSnapshot cpu;
uint64_t game3ds_ticks(void) {return ticks;}
void game_cpu_audit_snapshot(CpuRecordSnapshot *out) {*out=cpu;}
void game_cpu_audit_report(FILE *out) {fputs("cpu_core_reader=TEST\ncpu_thread_0_runtime=1,0,1,0,48\n",out);}
static void file(const char *dir,unsigned n,const char *content)
{
    char path[512];snprintf(path,sizeof(path),"%s/cpu_audit_%03u.txt",dir,n);
    FILE *f=fopen(path,"wb");assert(f);assert(fputs(content,f)>=0);assert(!fclose(f));
}
static void read_sample(const char *dir,unsigned n,char *buffer,size_t capacity)
{
    char path[512];snprintf(path,sizeof(path),"%s/cpu_audit_%03u.txt",dir,n);
    FILE *f=fopen(path,"rb");assert(f);size_t got=fread(buffer,1,capacity-1,f);buffer[got]=0;
    assert(feof(f));assert(!fclose(f));
}
static void press(CpuRecordContext *c)
{
    unsigned chord=SELECT_BIT|DOWN_BIT;
    assert(cpu_recorder_input(chord,c)==0);
    assert(cpu_recorder_input(chord,c)==0); /* held is not another press */
    assert(cpu_recorder_input(SELECT_BIT,c)==0);
    assert(cpu_recorder_input(chord,c)==0); /* both must release first */
    assert(cpu_recorder_input(0,c)==0);
}
static void frame(unsigned cost)
{
    game_prof_add(GP_UPDATE,cost);game_prof_count(GC_GTE,2);
    ticks+=26812348;game_prof_frame();
    cpu.calls[GCPU_RESOLVE]++;cpu.ticks[GCPU_RESOLVE]+=1000;
}
int main(int argc,char **argv)
{
    assert(argc==2);char data[32768],label[40];
    CpuRecordContext c={.game=11,.map=10,.room=3,.fps_mode=60,.control_mode=2,.lcd_frames=100};
    cpu.valid=(1u<<GCPU_SCOPES)-1;ticks=100;game_prof_enable(16);game_prof_frame();
    cpu_recorder_init(argv[1],"test-cpu-recorder");
    assert(next_index==1 && !error_code);
    assert(cpu_recorder_input(SELECT_BIT,&c)==0);
    assert(cpu_recorder_input(0,&c)==SELECT_BIT); /* single Select retains original action */
    assert(cpu_recorder_input(DOWN_BIT,&c)==DOWN_BIT); /* ordinary movement unchanged */
    press(&c);assert(active);
    for(unsigned i=0;i<10;i++)frame(5000);
    c.lcd_frames+=20;
    assert(cpu_recorder_label(label,sizeof(label)) && strstr(label,"CPU REC 00:01"));
    press(&c);assert(!active && !pending && last_saved==1);
    read_sample(argv[1],1,data,sizeof(data));
    assert(strstr(data,"sample_number=1\n") && strstr(data,"sample_flashlight=OFF\n"));
    assert(strstr(data,"sample_duration_ms=1000.0000\n") && strstr(data,"sample_lcd_fps=20.0000\n"));
    assert(strstr(data,"sample_profile_frames=10\n") && strstr(data,"sample_profile_update_total_ms=0.1865\n"));
    assert(strstr(data,"sample_cpu_resolve=1,10,0.0373,0.0037\n"));
    assert(strstr(data,"sample_context_changed_mask=0x0\n") && strstr(data,"sample_complete=1\n"));
    frame(999999); /* outside both windows */
    c.flashlight=1;press(&c);
    for(unsigned i=0;i<3;i++)frame(7000);
    c.lcd_frames+=3;press(&c);
    read_sample(argv[1],2,data,sizeof(data));
    assert(strstr(data,"sample_flashlight=ON\n") && strstr(data,"sample_profile_frames=3\n"));
    assert(strstr(data,"sample_profile_update_total_ms=0.0783\n"));
    assert(strstr(data,"sample_cpu_resolve=1,3,0.0112,0.0037\n"));
    /* Stop by the final dump; it must win over the recording chord. */
    press(&c);frame(9000);c.flashlight=0;
    unsigned exit=START_BIT|SELECT_BIT|DOWN_BIT;
    assert(cpu_recorder_input(exit,&c)==exit && active);
    cpu_recorder_finish(&c,"FINAL_DUMP");assert(!active && last_saved==3);
    read_sample(argv[1],3,data,sizeof(data));
    assert(strstr(data,"sample_stop_reason=FINAL_DUMP\n") && strstr(data,"sample_context_changed_mask=0x4\n"));
    cpu_recorder_input(0,&c);
    /* Restart finds 004; a competing creator after the scan must be preserved. */
    cpu_recorder_init(argv[1],"test-cpu-recorder");assert(next_index==4);
    file(argv[1],4,"DO NOT OVERWRITE");
    press(&c);frame(5000);press(&c);assert(last_saved==5);
    read_sample(argv[1],4,data,sizeof(data));assert(!strcmp(data,"DO NOT OVERWRITE"));
    /* A failed SD flush is not reported as saved. Retry uses another index. */
    press(&c);frame(5000);fail_sync=1;press(&c);
    assert(!active && pending && error_code==EIO && last_saved==5);
    read_sample(argv[1],6,data,sizeof(data));assert(!strstr(data,"sample_complete=1\n"));
    press(&c);assert(!pending && !error_code && last_saved==7);
    read_sample(argv[1],7,data,sizeof(data));assert(strstr(data,"sample_complete=1\n"));
    /* Unknown snapshot is explicit; 32-bit call-counter wrap is modular. */
    cpu.calls[0]=UINT32_MAX-2;press(&c);cpu.calls[0]=5;cpu.valid&=~(1u<<GCPU_RESOLVE);frame(1000);press(&c);
    read_sample(argv[1],8,data,sizeof(data));
    assert(strstr(data,"sample_cpu_spu_block=1,8,") && strstr(data,"sample_cpu_resolve=0,0,0.0000,0.0000\n"));
    file(argv[1],UINT_MAX,"LAST INDEX");
    cpu_recorder_init(argv[1],"test");assert(error_code==EOVERFLOW);
    press(&c);assert(!active);read_sample(argv[1],1,data,sizeof(data));assert(strstr(data,"sample_number=1\n"));
    puts("PASS: isolated OFF/ON frame and CPU deltas, duration/context, held-chord debounce, Select/movement forwarding, final dump priority, restart numbering, exclusive collision handling, fsync failure/retry, unknown snapshots, counter wrap and index exhaustion");
}
