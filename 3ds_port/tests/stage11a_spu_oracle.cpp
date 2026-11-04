/* Canonical field serialization, no object padding, pointers or STL internals.
 * Compile the SAME fixture against frozen/native and each candidate SPU.
 * Test-only private access also covers reverb FIR history and decoder state.
 */
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <deque>
#include <vector>
#define private public
#include "PsyX_SPUCore.h"
#undef private
#include "game_profile.h"
#include "stage11a_perf.h"
extern "C" {
int game_prof_enabled=0,game_prof_gte_sample=0;
static uint64_t test_ticks=1;
uint64_t game_prof_clock(void) {return ++test_ticks;}
void game_prof_audio_add(unsigned,uint64_t) {}
int stage11a_perf_active(void) {return 1;}
void stage11a_perf_add(unsigned,uint64_t) {}
}
static void bytes(const void *p,size_t n) {if(n && fwrite(p,1,n,stdout)!=n)std::abort();}
template<class T> static void value(T v) {
    uint64_t n=static_cast<uint64_t>(v);
    unsigned char out[8];for(unsigned i=0;i<8;i++)out[i]=(unsigned char)(n>>(8*i));
    bytes(out,sizeof(out));
}
static void volume(const SpuVolume& v) {value(v.left);value(v.right);}
static void voice(const PsyX::SPUVoiceState& v)
{
    const auto& a=v.attr;
    value(a.voice);value(a.mask);volume(a.volume);volume(a.volmode);volume(a.volumex);
    value(a.pitch);value(a.note);value(a.sample_note);value(a.envx);value(a.addr);value(a.loop_addr);
    value(a.a_mode);value(a.s_mode);value(a.r_mode);value(a.ar);value(a.dr);value(a.sr);value(a.rr);value(a.sl);value(a.adsr1);value(a.adsr2);
    value(v.curAddr);value(v.repeatAddr);value(v.repeatAddrLatchedByBlock);
    value(v.adpcmHist1);value(v.adpcmHist2);bytes(v.blockSamples,sizeof(v.blockSamples));
    value(v.blockSamplePos);value(v.blockValid);value(v.ovrPcm!=nullptr);value(v.ovrCount);value(v.ovrPos);value(v.ovrStep);
    bytes(v.interpTaps,sizeof(v.interpTaps));value(v.pitchCounter);value(v.reachedLoopEnd);
    value(v.blockLoopEnd);value(v.forceReleaseOnBlockEnd);value(v.envPhase);value(v.envLevel);value(v.envCounter);
    value(v.reverbSend);value(v.noiseMode);value(v.pitchModEnable);value(v.everKeyedOn);
    value(v.curVolL);value(v.curVolR);value(v.sweepCounterL);value(v.sweepCounterR);value(v.lastOutX);
}
static void snapshot(const PsyX::SPUCore& s)
{
    bytes(s.m_ram,sizeof(s.m_ram));
    for(const auto& v:s.m_voices)voice(v);
    value(s.GetEndxFlags());value(s.m_transferStartAddr);value(s.m_transferCurAddr);value(s.m_transferMode);
    value(s.m_malloc.initialized);value(s.m_malloc.heapBase);value(s.m_malloc.heapEnd);value(s.m_malloc.maxRecords);
    value(s.m_malloc.blocks.size());for(const auto& b:s.m_malloc.blocks){value(b.addr);value(b.size);value(b.free);}
    value(s.m_masterVolL);value(s.m_masterVolR);value(s.m_masterVolModeL);value(s.m_masterVolModeR);
    value(s.m_curMasterVolL);value(s.m_curMasterVolR);value(s.m_masterSweepCounterL);value(s.m_masterSweepCounterR);value(s.m_muted);
    value(s.m_reverbMasterEnable);value(s.m_reverbAttr.mask);value(s.m_reverbAttr.mode);
    volume(s.m_reverbAttr.depth);value(s.m_reverbAttr.delay);value(s.m_reverbAttr.feedback);
    const auto& r=s.m_reverb;
    bytes(&r.m_regs,sizeof(r.m_regs));value(r.m_mBaseRaw);value(r.m_baseAddress);value(r.m_currentAddress);
    value(r.m_vLOUT);value(r.m_vROUT);value(r.m_masterEnable);
    bytes(r.m_downsampleBuffer,sizeof(r.m_downsampleBuffer));bytes(r.m_upsampleBuffer,sizeof(r.m_upsampleBuffer));value(r.m_resamplePos);
    value(s.m_noiseClock);value(s.m_noiseCount);value(s.m_noiseLevel);
    value(s.m_cdEnable);value(s.m_cdReverb);value(s.m_cdVolL);value(s.m_cdVolR);
    value(s.m_xaMasterGainQ16);bytes(&s.m_xaMasterGain,sizeof(s.m_xaMasterGain));
    value(s.m_cdQueue.size());for(const auto& c:s.m_cdQueue){value(c.l);value(c.r);}
    value(s.m_lastCdFrame.l);value(s.m_lastCdFrame.r);
    value(s.m_cdQueueDouble.size());for(const auto& c:s.m_cdQueueDouble){bytes(&c.l,sizeof(c.l));bytes(&c.r,sizeof(c.r));}
    value(s.m_renderer);value(s.m_clipMode);value(s.m_nativePhase);value(s.m_referenceSincProcessCount);
    bytes(s.m_highRateVoiceSamples,sizeof(s.m_highRateVoiceSamples));bytes(s.m_highRateVoiceSteps,sizeof(s.m_highRateVoiceSteps));
    bytes(&s.m_highRateCdL,sizeof(s.m_highRateCdL));bytes(&s.m_highRateCdR,sizeof(s.m_highRateCdR));
    value(s.nativeCdNonzero);value(s.nativeCdPeak);
}
static uint32_t seed;
static uint32_t random32() {return seed=seed*1664525u+1013904223u;}
int main()
{
    std::setvbuf(stdout,nullptr,_IOFBF,65536);
    for(unsigned scenario=0;scenario<8;scenario++) {
        PsyX::SPUCore s;seed=0x110a0000u+scenario;
        for(unsigned i=0;i<0x6000;i++)s.RamData()[0x2000+i]=random32()>>24;
        /* All filters, shifts and end/loop encodings, including invalid headers. */
        for(unsigned i=0;i<0x6000;i+=16) {
            s.RamData()[0x2000+i]=(unsigned char)(((i/16)%6)*16+((i/96)%16));
            s.RamData()[0x2001+i]=(i/16)%8;
        }
        s.SetMasterVolume(0x3fff,-0x3000);s.SetCdVolume(0x4000,-0x4000);
        s.InitMalloc(16,0x1010);auto addr=s.Malloc(512);s.Free(addr);
        SpuReverbAttr reverb{};reverb.mask=~0u;reverb.mode=scenario%10;reverb.depth={0x2fff,-0x2000};
        s.SetReverbModeParam(reverb);s.SetReverbMasterEnable(true);s.SetVoiceReverbSend(0xaaaaaa,true);
        s.SetVoiceNoiseMode(scenario&1?0x555555:0,false);s.SetNoiseClock(scenario*9);
        s.SetVoicePitchModEnable(scenario&2?0xfffffe:0,true);
        for(unsigned v=0;v<24;v++) {
            SpuVoiceAttr a{};a.voice=1u<<v;a.mask=~0u;a.addr=0x2000+v*512;a.loop_addr=a.addr+16;
            static const uint16_t pitches[]={0,1,0x800,0xfff,0x1000,0x3fff,0x4000,0xffff};
            a.pitch=pitches[(v+scenario)%8];a.volume={(short)(random32()>>16),(short)(random32()>>16)};
            a.volmode.left=(scenario&4)?(v%8):SPU_VOICE_DIRECT16;
            a.volmode.right=(scenario&4)?((v+3)%8):SPU_VOICE_DIRECT16;
            a.adsr1=(uint16_t)random32();a.adsr2=(uint16_t)random32();
            s.SetVoiceAttr(a);s.SetKey(v%4,1u<<v);
        }
        s.SetVoiceNoiseMode(scenario&1?0x555555:0,true);
        int16_t pcm[1024*2],taps[24][1024],wet[2048],cd[2048];
        for(unsigned step=0;step<32;step++) {
            unsigned v=random32()%24;
            if(step%3==0)s.SetKey(step%4,1u<<v);
            if(step%5==0)s.SetVoicePitch(v,(uint16_t)random32());
            if(step%7==0){int16_t left=(int16_t)random32(),right=(int16_t)random32();s.SetVoiceVolume(v,left,right);}
            if(step==9)s.SetMute(SPU_ON);if(step==11)s.SetMute(SPU_OFF);
            if(step==15)s.SetReverbMasterEnable(false);if(step==18)s.SetReverbMasterEnable(true);
            if(step==21)s.ClearReverbWorkArea();
            s.SetCdAudioEnable(step%4!=0);s.SetCdAudioReverb(step%3!=0);
            s.SetXaMasterGain((step%3)*0.5);
            for(unsigned i=0;i<step*3;i++){int16_t left=(int16_t)random32(),right=(int16_t)random32();s.PushCdStereoFrame(left,right);}
            static const unsigned lengths[]={0,1,27,28,29,511,512,513,1024};
            unsigned n=lengths[(step+scenario)%9];
            std::memset(pcm,0x5a,sizeof(pcm));std::memset(taps,0x5a,sizeof(taps));
            std::memset(wet,0x5a,sizeof(wet));std::memset(cd,0x5a,sizeof(cd));
            PsyX::SPUCore::SplitOutput split{};
            for(unsigned i=0;i<24;i++)split.voiceMono[i]=taps[i];split.wetLR=wet;split.cdLR=cd;
            bool use_split=step%7==0;
            s.RenderFrames(step%11?pcm:nullptr,n,use_split?&split:nullptr);
            value(scenario);value(step);value(n);bytes(pcm,sizeof(pcm));
            if(use_split){bytes(taps,sizeof(taps));bytes(wet,sizeof(wet));bytes(cd,sizeof(cd));
                bytes(split.panL,sizeof(split.panL));bytes(split.panR,sizeof(split.panR));value(split.masterL);value(split.masterR);}
            snapshot(s);
        }
    }
    return std::fflush(stdout)?1:0;
}
