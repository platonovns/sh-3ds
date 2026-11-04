/* Game ABI only: libctru lives in game_audio_ndsp.c. */
#include "game_audio.h"
#include "game_xa.h"
#include "PsyX_SPUCore.h"
#include "PsyX/PsyX_public.h"
#include "game_profile.h"
#if defined(SH_STAGE11A_TRACEFIX)
#include "stage11a_pitch_trace.h"
#include <cstring>
#endif
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
static uint32_t lt_resets,lt_keyon,lt_keyoff;
#endif

PsyX_SfxOverrideFn g_PsyX_SfxOverride = nullptr;
namespace {
PsyX::SPUCore spu;
struct Guard { Guard(){game_audio_lock();} ~Guard(){game_audio_unlock();} };
uint32_t released;
struct Diagnostics {
    uint32_t enabled_blocks,disabled_active_blocks,input_frames,input_nonzero,final_nonzero;
    uint32_t submitted_frames,submitted_nonzero,last_cd_nonzero;
    int32_t cd_left,cd_right,master_left,master_right,current_master_left,current_master_right;
    uint32_t active_frames,active_enabled_blocks,final_active_nonzero;
} diag;
}
#if defined(SH_STAGE11A_TRACEFIX)
namespace {
constexpr unsigned pitch_trace_capacity=64;
struct PitchEvent {
    uint64_t tick;
    uint32_t caller,voice,mask,old_pitch,new_pitch,phase,level,ever_keyed,rr,vol_left,vol_right,fix;
    uint32_t midi[SH_PITCH_MIDI_WORDS];
};
static PitchEvent pitch_events[pitch_trace_capacity];
#ifndef SH_STAGE11A_F1_DEFAULT
#define SH_STAGE11A_F1_DEFAULT 0
#endif
static uint32_t pitch_count,fix_enabled=SH_STAGE11A_F1_DEFAULT;
static uint32_t fast_stats[13];
static void trace_pitch(const SpuVoiceAttr& a,uintptr_t caller)
{
    if(!(a.mask&SPU_VOICE_PITCH) || !a.pitch)return;
    for(unsigned i=0;i<24;i++)if(a.voice&(1u<<i)) {
        const auto& v=spu.GetVoiceState(i);
        if(v.attr.pitch || v.envLevel || v.everKeyedOn)continue;
        PitchEvent& e=pitch_events[pitch_count++%pitch_trace_capacity];
        e={};e.tick=game_prof_clock();e.caller=(uint32_t)caller;e.voice=i;e.mask=a.mask;
        e.old_pitch=v.attr.pitch;e.new_pitch=a.pitch;e.phase=(uint32_t)v.envPhase;e.level=v.envLevel;
        e.ever_keyed=v.everKeyedOn;e.rr=v.attr.rr;e.vol_left=v.attr.volmode.left;e.vol_right=v.attr.volmode.right;
        e.fix=fix_enabled;stage11a_pitch_midi_snapshot(i,e.midi);
    }
}
}
extern "C" unsigned game_spu_silent_fast_enabled(void){return fix_enabled;}
extern "C" int game_spu_silent_fast_toggle(void)
{Guard g;fix_enabled^=1;fast_stats[9]++;return (int)fix_enabled;}
extern "C" void game_spu_silent_fast_observe(uint32_t eligible,uint32_t used,uint32_t grouped,unsigned frames)
{
    unsigned a=__builtin_popcount(eligible),b=__builtin_popcount(used);
    fast_stats[0]++;fast_stats[1]=a;fast_stats[2]=b;
    if(a>fast_stats[3])fast_stats[3]=a;
    if(b>fast_stats[4])fast_stats[4]=b;
    fast_stats[5]+=a*frames;fast_stats[6]+=b*frames;fast_stats[fix_enabled?8:7]++;
    unsigned n=__builtin_popcount(grouped);fast_stats[10]=n;
    if(n>fast_stats[11])fast_stats[11]=n;
    fast_stats[12]+=n*frames;
}
extern "C" void game_spu_pitch_trace_report(FILE *out)
{
    static PitchEvent copy[pitch_trace_capacity];
    uint32_t total,mode,stats[13];
    {Guard g;total=pitch_count;mode=fix_enabled;std::memcpy(stats,fast_stats,sizeof(stats));
        std::memcpy(copy,pitch_events,sizeof(copy));}
    unsigned count=total<pitch_trace_capacity?total:pitch_trace_capacity;
    fprintf(out,"pitch_trace_schema=1\npitch_trace_capacity=%u\npitch_trace_total=%lu\npitch_trace_used=%u\npitch_trace_overwritten=%lu\n",
        pitch_trace_capacity,(unsigned long)total,count,(unsigned long)(total-count));
    fputs("pitch_trace_event_schema=absolute_ticks,caller_return_address,voice,mask,old_pitch,new_pitch,env_phase,env_level,ever_keyed,rr,volmode_left,volmode_right,fix_mode,scope_kind,scope_channel,cc1,cc2,port_voice,port_status,midi_channel,note,pbend_cache,vibrato,random,pbend_current,mod,porta,scope_return_address\n"
        "pitch_trace_scope_schema=outside:0,control_change:1,midi_vsync:2\n"
        "silent_fast_semantics=PITCH_AND_DECODER_ADVANCE_EVERY_SAMPLE_NO_REGISTER_OR_KEY_RESET\n"
        "silent_fast_stats_schema=blocks,eligible_last,used_last,eligible_peak,used_peak,eligible_voice_frames_mod32,used_voice_frames_mod32,F0_blocks,F1_blocks,toggles,grouped_last,grouped_peak,grouped_voice_frames_mod32\n",out);
    fprintf(out,"silent_fast_mode=%lu\nsilent_fast_stats=",(unsigned long)mode);
    for(unsigned i=0;i<13;i++)fprintf(out,"%s%lu",i?",":"",(unsigned long)stats[i]);
    fputc('\n',out);
    for(unsigned i=0;i<count;i++) {
        const PitchEvent& e=copy[(total-count+i)%pitch_trace_capacity];
        fprintf(out,"pitch_trace_event_%02u=%llu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu",i,
            (unsigned long long)e.tick,(unsigned long)e.caller,(unsigned long)e.voice,(unsigned long)e.mask,
            (unsigned long)e.old_pitch,(unsigned long)e.new_pitch,(unsigned long)e.phase,(unsigned long)e.level,
            (unsigned long)e.ever_keyed,(unsigned long)e.rr,(unsigned long)e.vol_left,(unsigned long)e.vol_right,(unsigned long)e.fix);
        for(unsigned j=0;j<SH_PITCH_MIDI_WORDS;j++)fprintf(out,",%lu",(unsigned long)e.midi[j]);
        fputc('\n',out);
    }
}
#endif
extern "C" {
void game_spu_init(void) { Guard g; spu.Reset(); released=0xffffff;
#if defined(SH_STAGE11A_LIFETIME)
    lt_resets++;
#endif
}
void game_spu_render(int16_t *out,uint32_t frames) {
    uint64_t locked=game_prof_begin();
    Guard g;
    if(locked && game_prof_enabled)game_prof_audio_add(GP_AUDIO_LOCK,game_prof_clock()-locked);
    int16_t cd[512*2];
    while(frames) {
        uint32_t n=frames>512?512:frames;
        uint64_t xa_time=game_prof_begin();
        uint32_t active=game_xa_is_active();
        if(active)diag.active_frames+=n;
        /* Consume only this block, then render it under the existing core
         * lock. No XA frames survive in the SPU queue between blocks. */
        uint32_t before=spu.nativeCdNonzero,got=0;
        if(spu.GetCdAudioEnable()) {
            ++diag.enabled_blocks;got=game_xa_pull(cd,n);diag.input_frames+=got;
            if(active)++diag.active_enabled_blocks;
            for(uint32_t i=0;i<got*2;i++)diag.input_nonzero+=cd[i]!=0;
            for(uint32_t i=0;i<got;i++)spu.PushCdStereoFrame(cd[i*2],cd[i*2+1]);
        } else if(active)++diag.disabled_active_blocks;
        int16_t l,r;
        if(got) {
            spu.GetCdVolume(&l,&r);diag.cd_left=l;diag.cd_right=r;
            spu.GetMasterVolume(&l,&r);diag.master_left=l;diag.master_right=r;
            spu.GetCurrentMasterVolume(&l,&r);diag.current_master_left=l;diag.current_master_right=r;
        }
        if(xa_time && game_prof_enabled)game_prof_audio_add(GP_XA_PCM,game_prof_clock()-xa_time);
        uint64_t core_time=game_prof_begin();
        spu.RenderFrames(out,n);
        if(core_time && game_prof_enabled)game_prof_audio_add(GP_SPU,game_prof_clock()-core_time);
        diag.last_cd_nonzero=spu.nativeCdNonzero-before;
        if(got)for(uint32_t i=0;i<n*2;i++)diag.final_nonzero+=out[i]!=0;
        if(active)for(uint32_t i=0;i<n*2;i++)diag.final_active_nonzero+=out[i]!=0;
        out+=n*2;frames-=n;
    }
}
void SpuInit(void) { game_spu_init(); }
void SpuQuit(void) { Guard g; spu.SetKey(SPU_OFF,0xffffff); }
unsigned int SpuWrite(unsigned char *data,unsigned int bytes) { Guard g; return spu.Write(data,bytes); }
unsigned int SpuSetTransferStartAddr(unsigned int addr) { Guard g; return spu.SetTransferStartAddr(addr); }
int SpuSetTransferMode(int mode) { Guard g; spu.SetTransferMode(mode==0?PsyX::TransferMode::DmaWrite:PsyX::TransferMode::ManualWrite); return mode; }
int SpuIsTransferCompleted(int flag) { (void)flag; return 1; }
int SpuInitMalloc(int num,char *top) { Guard g; (void)top; spu.InitMalloc(num,0x1010); return num; }
void SpuSetVoiceAttr(SpuVoiceAttr *a) { Guard g;
#if defined(SH_STAGE11A_TRACEFIX)
    trace_pitch(*a,(uintptr_t)__builtin_return_address(0));
#endif
    spu.SetVoiceAttr(*a); }
void SpuGetVoiceAttr(SpuVoiceAttr *a) { Guard g; spu.GetVoiceAttr(*a); }
void SpuSetKey(int on,unsigned int mask) { Guard g; spu.SetKey(on,mask); if(on==SPU_ON)released&=~mask;else released|=mask;
#if defined(SH_STAGE11A_LIFETIME)
    if(on==SPU_ON)lt_keyon++;else lt_keyoff++;
#endif
}
void SpuSetKeyOnWithAttr(SpuVoiceAttr *a) { Guard g; spu.SetVoiceAttr(*a);spu.SetKey(SPU_ON,a->voice);released&=~a->voice;
#if defined(SH_STAGE11A_LIFETIME)
    lt_keyon++;
#endif
}
#if defined(SH_STAGE11A_LIFETIME)
void stage11a_lifetime_spu(uint32_t out[LT_SPU_WORDS],uint32_t voices[24][LT_VOICE_WORDS])
{
    Guard g;out[0]=lt_resets;out[1]=lt_keyon;out[2]=lt_keyoff;out[3]=released;
    for(unsigned i=0;i<24;i++) {
        const auto& v=spu.GetVoiceState(i);
        bool frozen=v.attr.pitch==0 &&
            (v.envPhase==PsyX::EnvPhase::Off || (v.envPhase==PsyX::EnvPhase::Release && v.envLevel==0 && (v.attr.rr&31)<=11)) &&
            v.attr.volmode.left==SPU_VOICE_DIRECT16 && v.attr.volmode.right==SPU_VOICE_DIRECT16;
        out[4]+=v.everKeyedOn;out[5]+=v.attr.pitch!=0;out[6]+=v.envLevel!=0;
        out[7]+=frozen;out[8]+=v.envLevel==0 && v.attr.pitch!=0;
        auto *p=voices[i];p[0]=v.attr.pitch;p[1]=(uint32_t)v.envLevel;p[2]=(uint32_t)v.envPhase;
        p[3]=v.attr.volmode.left;p[4]=v.attr.volmode.right;p[5]=v.curAddr;
        p[6]=v.pitchCounter;p[7]=v.envCounter;p[8]=(uint32_t)v.lastOutX;
        p[9]=((released>>i)&1)|(v.everKeyedOn?2:0)|(v.noiseMode?4:0)|(v.pitchModEnable?8:0)|
            (v.reverbSend?16:0)|(v.reachedLoopEnd?32:0)|(v.blockValid?64:0)|(frozen?128:0);
    }
    out[9]=spu.GetPendingCdFrameCount();out[10]=spu.GetEndxFlags();out[11]=spu.GetVoiceNoiseModeMask();
    out[12]=spu.GetVoicePitchModEnableMask();out[13]=spu.GetVoiceReverbSendMask();
    out[14]=spu.GetReverbMasterEnable();out[15]=24;
}
#endif
int SpuGetKeyStatus(unsigned int mask) {
    Guard g;
    /* libsd polls for completed register writes. A key-off is synchronous at
     * this boundary; the PCM renderer still performs the original release. */
    if(mask&released)return SPU_OFF;
    int state=spu.GetKeyStatus(mask); return state==SPU_OFF_ENV_ON?SPU_OFF:state;
}
void SpuGetAllKeysStatus(char *s) { Guard g;spu.GetAllKeysStatus(s);for(int i=0;i<24;i++)if(released&(1u<<i))s[i]=SPU_OFF; }
int SpuSetReverbModeParam(SpuReverbAttr *a) { Guard g;spu.SetReverbModeParam(*a);return 0; }
int SpuSetReverb(int on) { Guard g;spu.SetReverbMasterEnable(on!=0);return on; }
int SpuReserveReverbWorkArea(int on) { return on; }
int SpuClearReverbWorkArea(int mode) { Guard g;(void)mode;spu.ClearReverbWorkArea();return 0; }
unsigned int SpuSetReverbVoice(int on,unsigned int mask) { Guard g;spu.SetVoiceReverbSend(mask,on!=0);return spu.GetVoiceReverbSendMask(); }
unsigned int SpuGetReverbVoice(void) { Guard g;return spu.GetVoiceReverbSendMask(); }
void SpuSetCommonAttr(SpuCommonAttr *a) { Guard g;spu.SetCommonAttr(*a); }
void game_spu_xa_submitted(uint32_t frames,uint32_t nonzero)
{ Guard g;if(diag.last_cd_nonzero){diag.submitted_frames+=frames;diag.submitted_nonzero+=nonzero;} }
void game_spu_audio_report(FILE *out)
{
    Diagnostics v;uint32_t cd_nz,cd_peak,enabled;int16_t cl,cr,ml,mr;
    { Guard g;v=diag;cd_nz=spu.nativeCdNonzero;cd_peak=spu.nativeCdPeak;
      spu.GetCdVolume(&cl,&cr);spu.GetMasterVolume(&ml,&mr);enabled=spu.GetCdAudioEnable(); }
    fprintf(out,"xa_spu_enabled_blocks=%lu\nxa_spu_disabled_active_blocks=%lu\nxa_spu_input_frames=%lu\nxa_spu_input_nonzero=%lu\nxa_spu_mix_nonzero=%lu\nxa_spu_mix_peak=%lu\nxa_spu_final_nonzero=%lu\nxa_ndsp_submitted_frames=%lu\nxa_ndsp_submitted_nonzero=%lu\nxa_spu_cd_volume=%d,%d\nxa_spu_master_volume=%d,%d\nxa_spu_last_audio_cd_volume=%ld,%ld\nxa_spu_last_audio_master=%ld,%ld\n",
        (unsigned long)v.enabled_blocks,(unsigned long)v.disabled_active_blocks,(unsigned long)v.input_frames,(unsigned long)v.input_nonzero,
        (unsigned long)cd_nz,(unsigned long)cd_peak,(unsigned long)v.final_nonzero,(unsigned long)v.submitted_frames,(unsigned long)v.submitted_nonzero,
        cl,cr,ml,mr,(long)v.cd_left,(long)v.cd_right,(long)v.master_left,(long)v.master_right);
    fprintf(out,"xa_spu_last_audio_current_master=%ld,%ld\n",(long)v.current_master_left,(long)v.current_master_right);
    fprintf(out,"xa_spu_cd_enable_current=%lu\nxa_spu_active_frames=%lu\nxa_spu_active_enabled_blocks=%lu\nxa_spu_final_active_nonzero=%lu\n",
        (unsigned long)enabled,(unsigned long)v.active_frames,(unsigned long)v.active_enabled_blocks,(unsigned long)v.final_active_nonzero);
}
}
