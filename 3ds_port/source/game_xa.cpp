/* Raw-disc transport around the existing PC decoder and PsyCross resampler.
 * One worker owns FILE/ADPCM/resampler. Commands and PCM share a short lock;
 * no disk access, decoding or allocation occurs while that lock is held. */
#include "game_xa.h"
#include "PsyX_XAStream.h"
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
#endif
#include <string.h>
#include <limits.h>
#include <errno.h>
namespace {
constexpr uint32_t Capacity=16384, MaxSectorOutput=9408;
constexpr uint32_t RawBatchSectors=32, RawBatchBytes=RawBatchSectors*2352;
constexpr uint32_t StartupFrames=4096; // Two 37.8-kHz stereo sectors (4704 frames).
struct Guard { Guard(){game_xa_lock();} ~Guard(){game_xa_unlock();} };
struct Info {
    uint32_t epoch,lba,file,channel,target,active,paused,done,error;
    uint32_t read,write,count,elapsed,played,starts,stops,raw,matched,underflows,peak_queue;
    uint32_t rate,channels;
    uint32_t ll=127,lr=0,rr=127,rl=0;
    uint32_t primed;
};
struct Stream : Info { int16_t pcm[Capacity*2]; } s;
struct Event { uint32_t type,epoch,entry,a,b,c; };
struct Diagnostics {
    uint32_t requests,first_request,last_request,preloads,driver,driver_states,driver_flags,active_transitions;
    uint32_t cd_command,cd_mode_filter,cd_lba,worker_starts,worker_lba,open_attempts,open_success,seeks;
    uint32_t valid_form2,filter_matches,decoded_sectors,decoded_frames,decoded_nonzero,resampled_frames,resampled_nonzero,resampled_peak;
    uint32_t ring_in,ring_out,matrix_nonzero,pull_frames,eof_count,limit_count,watchdogs;
    uint32_t cancels,last_cancel,first_cancel,cancel_mask,cancel_played,cancel_queued,cancel_context0,cancel_context1;
    uint32_t io_operation,io_errno,io_lba,io_result,errors,last_error,event_count;
    Event events[32];
    uint32_t read_batches,read_bytes,startup_wait_frames,missing_frames,eof_padding_frames;
    uint32_t short_blocks,gap_frames,longest_gap_frames,min_active_queue=UINT32_MAX;
} d;
void event(uint32_t type,uint32_t a,uint32_t b,uint32_t c)
{ d.events[d.event_count++%32]={type,s.epoch,d.last_request,a,b,c}; }
void io_result(uint32_t op,uint32_t lba,int result)
{ Guard g;d.io_operation=op;d.io_errno=errno;d.io_lba=lba;d.io_result=result; }
FILE *disc;
bool output_available=true;
uint32_t sector_count,worker_epoch=UINT32_MAX,next_lba,produced,scan_without_match;
int32_t history[2][2];
PsyX_XAStream *resampler;
#if defined(SH_STAGE11A_LIFETIME)
uint32_t lt_resampler_present;
#endif
uint8_t raw[2352];
/* Keep physical reads sector-aligned and amortize SD/FS transaction latency.
 * A FILE buffer of the same size is also essential on newlib: a large fread
 * alone can otherwise be fulfilled by many small __srefill reads. The two
 * fixed buffers duplicate one batch, never preload a whole XA file/line. */
uint8_t raw_batch[RawBatchBytes],disc_stdio[RawBatchBytes];
uint32_t batch_read,batch_count;
int16_t decoded[4032],converted[MaxSectorOutput*2];
bool open_disc()
{
    if(disc)return true;
    { Guard g;++d.open_attempts; }
    errno=0;
    disc=fopen("sdmc:/3ds/silenthill/sh1.bin","rb");
    if(!disc){io_result(1,0,-1);return false;}
    if(setvbuf(disc,reinterpret_cast<char *>(disc_stdio),_IOFBF,sizeof(disc_stdio))) {
        io_result(1,0,-1);fclose(disc);disc=nullptr;return false;
    }
    if(fseek(disc,0,SEEK_END)){io_result(2,0,-1);fclose(disc);disc=nullptr;return false;}
    long size=ftell(disc);
    if(size<=0 || size%2352){io_result(3,0,size);fclose(disc);disc=nullptr;return false;}
    sector_count=static_cast<uint32_t>(size/2352);
    { Guard g;++d.open_success; }
    return true;
}
int16_t clamp(int32_t v) { return static_cast<int16_t>(v>32767?32767:(v< -32768?-32768:v)); }
void failed(uint32_t epoch,uint32_t code)
{
    Guard g;
    if(s.epoch==epoch){s.error=code;s.done=1;++d.errors;d.last_error=code;event(9,code,s.played,s.count);}
}
}
extern "C" {
#if defined(SH_STAGE11A_LIFETIME)
void stage11a_lifetime_xa(uint32_t out[LT_XA_WORDS])
{
    Guard g;out[0]=s.epoch;out[1]=s.active;out[2]=s.paused;out[3]=s.count;
    out[4]=Capacity;out[5]=s.rate;out[6]=s.channels;out[7]=s.starts;out[8]=s.stops;
    out[9]=s.raw;out[10]=s.underflows;out[11]=__atomic_load_n(&lt_resampler_present,__ATOMIC_ACQUIRE);
    out[12]=d.event_count;out[13]=32;out[14]=d.ring_in;out[15]=d.ring_out;
}
#endif
void game_xa_note(uint32_t type,uint32_t a,uint32_t b,uint32_t c)
{
    Guard g;
    if(type==XA_NOTE_REQUEST){if(!d.requests)d.first_request=a;++d.requests;d.last_request=a;}
    if(type==XA_NOTE_PRELOAD)++d.preloads;
    if(type==XA_NOTE_DRIVER){d.driver=a;d.driver_states=b;d.driver_flags=c;}
    if(type==XA_NOTE_CD){d.cd_command=a;d.cd_mode_filter=b;d.cd_lba=c;}
    if(type==XA_NOTE_ACTIVE)++d.active_transitions;
    if(type==XA_NOTE_WATCHDOG)++d.watchdogs;
    event(type,a,b,c);
}
void game_xa_start(uint32_t lba,uint32_t file,uint32_t channel,uint32_t ticks)
{
    Guard g;
    ++s.epoch;s.lba=lba;s.file=file;s.channel=channel;
    s.target=ticks<=60*60*10?ticks*735u:0;
    s.active=s.target!=0;s.done=s.error=s.read=s.write=s.count=s.elapsed=s.played=0;
    s.primed=0;d.gap_frames=0;
    if(!output_available){s.error=8;s.done=1;}
    s.rate=s.channels=0;++s.starts;
    event(7,lba,(file<<8)|channel,ticks);
}
void game_xa_stop(void)
{ game_xa_cancel(XA_CANCEL_ORIGINAL,0,0); }
void game_xa_cancel(uint32_t reason,uint32_t context0,uint32_t context1)
{
    Guard g;
    if(s.active || (reason!=XA_CANCEL_CD_SEEK && reason!=XA_CANCEL_CD_PAUSE && reason!=XA_CANCEL_SHUTDOWN)) {
        if(!d.cancels)d.first_cancel=reason;
        ++d.cancels;d.last_cancel=reason;d.cancel_mask|=1u<<reason;
        d.cancel_played=s.played;d.cancel_queued=s.count;d.cancel_context0=context0;d.cancel_context1=context1;
    }
    event(8,reason,s.played,s.count);
    ++s.epoch;s.active=0;s.count=0;s.read=s.write=0;s.done=1;++s.stops;
    s.primed=0;d.gap_frames=0;
}
void game_xa_pause(uint32_t paused) { Guard g;s.paused=paused;if(paused)d.gap_frames=0; }
void game_xa_disable_output(void) { Guard g;output_available=false;s.error=8;s.done=1; }
uint32_t game_xa_status(void) { Guard g;return s.error?0x03:(s.active && !s.done?0x22:0x02); }
uint32_t game_xa_is_active(void) { Guard g;return s.active; }
uint32_t game_xa_draining(void) { Guard g;return s.active && !s.error && (!s.done || s.count); }
uint32_t game_xa_ready(void) { Guard g;return s.active && !s.error && s.played!=0; }
uint32_t game_xa_elapsed60(void) { Guard g;return s.error?0x7fffffffu:s.elapsed/735u; }
void game_xa_mix(uint32_t ll,uint32_t lr,uint32_t rr,uint32_t rl)
{ Guard g;s.ll=ll;s.lr=lr;s.rr=rr;s.rl=rl; }
uint32_t game_xa_step(void)
{
    uint32_t epoch,lba,file,channel,target;
    {
        Guard g;
        if(!s.active || s.paused || s.done || Capacity-s.count<MaxSectorOutput)return 0;
        epoch=s.epoch;lba=s.lba;file=s.file;channel=s.channel;target=s.target;
    }
    if(epoch!=worker_epoch) {
        { Guard g;++d.worker_starts;d.worker_lba=lba;event(10,lba,file,channel); }
        worker_epoch=epoch;next_lba=lba;produced=scan_without_match=0;
        batch_read=batch_count=0;
        memset(history,0,sizeof(history));
        if(!resampler)resampler=PsyX_XAStream_Create();
#if defined(SH_STAGE11A_LIFETIME)
        __atomic_store_n(&lt_resampler_present,resampler!=nullptr,__ATOMIC_RELEASE);
#endif
        if(!resampler){failed(epoch,1);return 0;}
        PsyX_XAStream_Reset(resampler);
        if(!open_disc() || next_lba>=sector_count) {
            failed(epoch,2);return 0;
        }
        errno=0;
        int seek=fseek(disc,static_cast<long>(next_lba)*2352,SEEK_SET);
        io_result(4,next_lba,seek);
        if(seek){failed(epoch,2);return 0;}
        { Guard g;++d.seeks; }
    }
    /* At most 64 raw sectors and one decode per wake. A mismatched file or
     * missing channel terminates after 512 sectors rather than scanning a BIN. */
    for(unsigned scan=0;scan<64;scan++) {
        if(next_lba>=sector_count){io_result(5,next_lba,0);failed(epoch,3);return 0;}
        if(batch_read==batch_count) {
            uint32_t sectors=sector_count-next_lba;
            if(sectors>RawBatchSectors)sectors=RawBatchSectors;
            uint32_t wanted=sectors*2352;
            errno=0;size_t bytes=fread(raw_batch,1,wanted,disc);
            { Guard g;++d.read_batches;d.read_bytes+=bytes; }
            if(bytes!=wanted){io_result(5,next_lba,bytes);failed(epoch,3);return 0;}
            batch_read=0;batch_count=sectors;
        }
        memcpy(raw,raw_batch+(batch_read++)*2352,sizeof(raw));
        ++next_lba;
        { Guard g;if(s.epoch!=epoch)return 0;++s.raw; }
        static const uint8_t sync[12]={0,255,255,255,255,255,255,255,255,255,255,0};
        if(memcmp(raw,sync,12) || raw[15]!=2 || memcmp(raw+16,raw+20,4)) {failed(epoch,4);return 0;}
        { Guard g;if((raw[18]&0x64)==0x64)++d.valid_form2; }
        if(raw[16]!=file || raw[17]!=channel || (raw[18]&0x64)!=0x64) {
            if(++scan_without_match>=512){failed(epoch,5);return 0;}
            continue;
        }
        scan_without_match=0;
        { Guard g;++d.filter_matches; }
        uint32_t coding=raw[19];
        /* Original SH disc dialogue is 4-bit; reject reserved/8-bit formats
         * explicitly rather than feeding them to the 4-bit decoder. */
        if(coding&0xba){failed(epoch,6);return 0;}
        uint32_t channels=(coding&1)?2:1,rate=(coding&4)?18900:37800;
        int samples=game_xa_decode(raw+16,decoded,history);
        if(samples<=0 || !PsyX_XAStream_Push(resampler,decoded,samples/channels,rate,channels)) {failed(epoch,7);return 0;}
        uint32_t frames=PsyX_XAStream_Pop44100Stereo(resampler,converted,MaxSectorOutput);
        uint32_t generated=frames;
        uint32_t dnz=0,rnz=0,peak=0;
        for(int i=0;i<samples;i++)dnz+=decoded[i]!=0;
        for(uint32_t i=0;i<frames*2;i++){int v=converted[i];uint32_t a=v<0?-v:v;rnz+=a!=0;if(a>peak)peak=a;}
        if(frames>target-produced)frames=target-produced;
        {
            Guard g;
            if(s.epoch!=epoch || !s.active)return 0;
            ++d.decoded_sectors;d.decoded_frames+=samples/channels;d.decoded_nonzero+=dnz;
            d.resampled_frames+=generated;
            d.resampled_nonzero+=rnz;if(peak>d.resampled_peak)d.resampled_peak=peak;
            for(uint32_t i=0;i<frames;i++) {
                s.pcm[s.write*2]=converted[i*2];s.pcm[s.write*2+1]=converted[i*2+1];
                s.write=(s.write+1)%Capacity;
            }
            s.count+=frames;produced+=frames;d.ring_in+=frames;++s.matched;s.rate=rate;s.channels=channels;
            if(s.count>s.peak_queue)s.peak_queue=s.count;
            if(produced>=target){++d.limit_count;s.done=1;event(11,1,produced,s.played);}
            if(raw[18]&0x80){++d.eof_count;s.done=1;event(11,2,produced,s.played);}
        }
        return frames;
    }
    return 0;
}
uint32_t game_xa_pull(int16_t *out,uint32_t frames)
{
    Guard g;
    if(!s.active || s.paused)return 0;
    d.pull_frames+=frames;
    if(!s.primed) {
        if(s.count>=StartupFrames || s.done)s.primed=1;
        else {d.startup_wait_frames+=frames;return 0;}
    }
    uint32_t n=frames<s.count?frames:s.count;
    if(s.played && !s.done && s.count-n<d.min_active_queue)d.min_active_queue=s.count-n;
    for(uint32_t i=0;i<n;i++) {
        int32_t l=s.pcm[s.read*2],r=s.pcm[s.read*2+1];
        /* CD coefficients are unsigned bytes, but PCM and the accumulator
         * must stay signed. Unsigned multiplication made the right shift
         * logical and turned every negative sample into positive clipping.
         * Two S16 inputs times byte gains fit safely in an int32_t. */
        out[i*2]=clamp((l*static_cast<int32_t>(s.ll)+r*static_cast<int32_t>(s.rl))>>7);
        out[i*2+1]=clamp((l*static_cast<int32_t>(s.lr)+r*static_cast<int32_t>(s.rr))>>7);
        d.matrix_nonzero+=(out[i*2]!=0)+(out[i*2+1]!=0);
        s.read=(s.read+1)%Capacity;
    }
    s.count-=n;s.played+=n;s.elapsed+=n;
    d.ring_out+=n;
    /* Preserve original audioLength+32 watchdog padding. Count it using
     * mixer samples only after source drain; pauses and game FPS cannot move it. */
    if(n)d.gap_frames=0;
    if(s.done && !s.count) {
        s.elapsed+=frames-n;d.eof_padding_frames+=frames-n;
    } else if(n<frames && s.played) {
        ++s.underflows;++d.short_blocks;d.missing_frames+=frames-n;d.gap_frames+=frames-n;
        if(d.gap_frames>d.longest_gap_frames)d.longest_gap_frames=d.gap_frames;
    }
    return n;
}
void game_xa_close(void)
{
    if(disc){fclose(disc);disc=nullptr;}
    if(resampler){PsyX_XAStream_Destroy(resampler);resampler=nullptr;}
#if defined(SH_STAGE11A_LIFETIME)
    __atomic_store_n(&lt_resampler_present,0,__ATOMIC_RELEASE);
#endif
    worker_epoch=UINT32_MAX;
    batch_read=batch_count=0;
}
void game_xa_report(FILE *out)
{
    Info snapshot;
    Diagnostics diag;
    /* Do not copy the PCM ring onto the report/game thread stack. */
    { Guard g;snapshot=s;diag=d; }
    fprintf(out,"xa_read_batch_sectors=%u\nxa_read_buffer_bytes=%u\nxa_startup_frames=%u\nxa_primed=%lu\nxa_read_batches=%lu\nxa_read_bytes=%lu\nxa_startup_wait_frames=%lu\nxa_missing_frames=%lu\nxa_eof_padding_frames=%lu\nxa_short_blocks=%lu\nxa_longest_gap_frames=%lu\nxa_min_active_queue=%lu\n",
        RawBatchSectors,RawBatchBytes*2,StartupFrames,(unsigned long)snapshot.primed,
        (unsigned long)diag.read_batches,(unsigned long)diag.read_bytes,(unsigned long)diag.startup_wait_frames,
        (unsigned long)diag.missing_frames,(unsigned long)diag.eof_padding_frames,(unsigned long)diag.short_blocks,
        (unsigned long)diag.longest_gap_frames,(unsigned long)(diag.min_active_queue==UINT32_MAX?0:diag.min_active_queue));
    fprintf(out,"audio_xa=RAW_BIN_ADPCM\nxa_active=%u\nxa_lba=%u\nxa_filter=%u,%u\nxa_rate=%u\nxa_channels=%u\nxa_queued=%u\nxa_capacity=%u\nxa_elapsed60=%u\nxa_played=%u\nxa_starts=%u\nxa_stops=%u\nxa_raw_sectors=%u\nxa_matched_sectors=%u\nxa_underflows=%u\nxa_peak_queue=%u\nxa_done=%u\nxa_error=%u\n",
        snapshot.active,snapshot.lba,snapshot.file,snapshot.channel,snapshot.rate,snapshot.channels,
        snapshot.count,Capacity,snapshot.elapsed/735,snapshot.played,snapshot.starts,snapshot.stops,
        snapshot.raw,snapshot.matched,snapshot.underflows,snapshot.peak_queue,snapshot.done,snapshot.error);
    fprintf(out,"xa_diag_schema=3\nxa_requests=%lu\nxa_first_request=%lu\nxa_last_request=%lu\nxa_preloads=%lu\nxa_driver_task=%lu\nxa_driver_states=%08lx\nxa_driver_flags=%08lx\nxa_active_transitions=%lu\nxa_cd_command=%lu\nxa_cd_mode_filter=%08lx\nxa_cd_lba=%lu\nxa_worker_starts=%lu\nxa_worker_lba=%lu\nxa_open_attempts=%lu\nxa_open_success=%lu\nxa_seeks=%lu\nxa_valid_form2=%lu\nxa_filter_matches=%lu\nxa_decoded_sectors=%lu\nxa_decoded_frames=%lu\nxa_decoded_nonzero=%lu\nxa_resampled_frames=%lu\nxa_resampled_nonzero=%lu\nxa_resampled_peak=%lu\nxa_ring_in=%lu\nxa_ring_out=%lu\nxa_matrix_nonzero=%lu\nxa_pull_frames=%lu\nxa_eof_count=%lu\nxa_limit_count=%lu\nxa_watchdogs=%lu\n",
        (unsigned long)diag.requests,(unsigned long)diag.first_request,(unsigned long)diag.last_request,(unsigned long)diag.preloads,
        (unsigned long)diag.driver,(unsigned long)diag.driver_states,(unsigned long)diag.driver_flags,(unsigned long)diag.active_transitions,
        (unsigned long)diag.cd_command,(unsigned long)diag.cd_mode_filter,(unsigned long)diag.cd_lba,(unsigned long)diag.worker_starts,
        (unsigned long)diag.worker_lba,(unsigned long)diag.open_attempts,(unsigned long)diag.open_success,(unsigned long)diag.seeks,
        (unsigned long)diag.valid_form2,(unsigned long)diag.filter_matches,(unsigned long)diag.decoded_sectors,(unsigned long)diag.decoded_frames,
        (unsigned long)diag.decoded_nonzero,(unsigned long)diag.resampled_frames,(unsigned long)diag.resampled_nonzero,(unsigned long)diag.resampled_peak,
        (unsigned long)diag.ring_in,(unsigned long)diag.ring_out,(unsigned long)diag.matrix_nonzero,(unsigned long)diag.pull_frames,
        (unsigned long)diag.eof_count,(unsigned long)diag.limit_count,(unsigned long)diag.watchdogs);
    fprintf(out,"xa_cancel_count=%lu\nxa_cancel_first=%lu\nxa_cancel_last=%lu\nxa_cancel_mask=%08lx\nxa_cancel_played=%lu\nxa_cancel_queued=%lu\nxa_cancel_context=%08lx,%08lx\nxa_io_operation=%lu\nxa_io_errno=%lu\nxa_io_lba=%lu\nxa_io_result=%ld\nxa_errors_total=%lu\nxa_last_error=%lu\nxa_matrix=%lu,%lu,%lu,%lu\nxa_events_total=%lu\n",
        (unsigned long)diag.cancels,(unsigned long)diag.first_cancel,(unsigned long)diag.last_cancel,(unsigned long)diag.cancel_mask,
        (unsigned long)diag.cancel_played,(unsigned long)diag.cancel_queued,(unsigned long)diag.cancel_context0,(unsigned long)diag.cancel_context1,
        (unsigned long)diag.io_operation,(unsigned long)diag.io_errno,(unsigned long)diag.io_lba,(long)(int32_t)diag.io_result,
        (unsigned long)diag.errors,(unsigned long)diag.last_error,(unsigned long)snapshot.ll,(unsigned long)snapshot.lr,
        (unsigned long)snapshot.rr,(unsigned long)snapshot.rl,(unsigned long)diag.event_count);
    for(uint32_t i=diag.event_count>32?diag.event_count-32:0;i<diag.event_count;i++) {
        const Event &e=diag.events[i%32];
        fprintf(out,"xa_event_%lu=%lu,%lu,%lu,%lu,%lu,%lu\n",(unsigned long)i,(unsigned long)e.type,(unsigned long)e.epoch,
            (unsigned long)e.entry,(unsigned long)e.a,(unsigned long)e.b,(unsigned long)e.c);
    }
}
}
