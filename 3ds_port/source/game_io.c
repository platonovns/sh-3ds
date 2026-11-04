#include "game_io.h"
#include "game3ds.h"
#include <string.h>
#define FILES 2074
#define HISTORY 128
#define TICKS_PER_MS 268123.480
typedef struct { unsigned state,player,map;int x,z,yaw; } Context;
typedef struct { unsigned calls,bytes,maximum,game_calls,game_max; } File;
typedef struct { Context context;unsigned file,lba,requested,actual,raw_requested,raw_actual,reads,seeks,sequential;
    int status;uint64_t start,ticks,io; } Request;
static Context context;
static File files[FILES];
static Request request,history[HISTORY],slow[8];
static unsigned active,total,history_count;
#if defined(SH_STAGE11A_LIFETIME)
unsigned stage11a_lifetime_io_history(void){return history_count;}
#endif
void game_io_context(unsigned state,unsigned player,unsigned map,int32_t x,int32_t z,int32_t yaw)
{ context=(Context){state,player,map,x,z,yaw}; }
void game_io_begin(unsigned file,uint32_t lba,uint32_t bytes)
{
    memset(&request,0,sizeof(request));request.context=context;request.file=file;
    request.lba=lba;request.requested=bytes;request.start=game3ds_ticks();active=1;
}
void game_io_raw(uint32_t lba,uint32_t requested,uint32_t actual,unsigned seek,uint64_t ticks)
{
    (void)lba;if(!active)return;
    request.reads++;request.seeks+=seek;request.sequential+=!seek;
    request.raw_requested+=requested;request.raw_actual+=actual;request.io+=ticks;
}
void game_io_data(uint32_t bytes) { if(active)request.actual+=bytes; }
void game_io_end(int status)
{
    if(!active)return;
    active=0;request.ticks=game3ds_ticks()-request.start;request.status=status;
    history[total++%HISTORY]=request;if(history_count<HISTORY)history_count++;
    unsigned least=0;for(unsigned i=1;i<8;i++)if(slow[i].ticks<slow[least].ticks)least=i;
    if(request.ticks>slow[least].ticks)slow[least]=request;
    if(request.file<FILES) {
        File *f=&files[request.file];f->calls++;f->bytes+=request.requested;
        if(request.requested>f->maximum)f->maximum=request.requested;
        if(context.state==11 && context.map>700) {
            f->game_calls++;if(request.requested>f->game_max)f->game_max=request.requested;
        }
    }
}
static void print_request(FILE *out,const char *kind,unsigned index,const Request *r)
{
    fprintf(out,"io_%s_%u=%u,%u,%u,%u,%d,%d,%d,%u,%u,%u,%u,%u,%u,%u,%u,%d,%.4f,%.4f\n",kind,index,
        r->context.map,r->context.state,r->context.player,r->file,r->context.x,r->context.z,r->context.yaw,
        r->lba,r->requested,r->actual,r->raw_requested,r->raw_actual,r->reads,r->seeks,r->sequential,r->status,
        r->ticks/TICKS_PER_MS,r->io/TICKS_PER_MS);
}
void game_io_report(FILE *out)
{
    unsigned unique=0,game_unique=0,bytes=0,calls=0,game_calls=0,unique_files=0;
    fprintf(out,"io_schema=1\nio_history_capacity=%u\nio_requests=%u\n",HISTORY,total);
    for(unsigned i=0;i<FILES;i++)if(files[i].calls) {
        File *f=&files[i];unique+=f->maximum;game_unique+=f->game_max;
        bytes+=f->bytes;calls+=f->calls;game_calls+=f->game_calls;unique_files++;
        fprintf(out,"io_file_%u=%u,%u,%u,%u,%u\n",i,f->calls,f->bytes,f->maximum,f->game_calls,f->game_max);
    }
    fprintf(out,"io_unique_files=%u\nio_unique_resource_bytes=%u\nio_requested_bytes=%u\nio_repeated_requests=%u\nio_game_unique_resource_bytes=%u\nio_game_requests=%u\n",
        unique_files,unique,bytes,calls-unique_files,game_unique,game_calls);
    for(unsigned i=0;i<history_count;i++)print_request(out,"request",i,&history[(total-history_count+i)%HISTORY]);
    for(unsigned i=0;i<8;i++)if(slow[i].ticks)print_request(out,"slow",i,&slow[i]);
}

