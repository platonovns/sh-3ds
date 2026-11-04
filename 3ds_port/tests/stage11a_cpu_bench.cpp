/* Synthetic, reproducible workloads. Host timing is not an ARM11 forecast. */
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <deque>
#include <vector>
#define private public
#include "PsyX_SPUCore.h"
#undef private
extern "C" unsigned game_spu_silent_fast_enabled(void){return 1;}
extern "C" void game_spu_silent_fast_observe(uint32_t,uint32_t,uint32_t,unsigned){}
static volatile unsigned checksum;
int main() {
 for(unsigned scenario=0;scenario<6;scenario++) {
  double samples[7];
  for(unsigned trial=0;trial<7;trial++) {
   PsyX::SPUCore s;unsigned seed=0x115a;
   for(unsigned i=0;i<0x4000;i++){seed=seed*1664525u+1013904223u;s.RamData()[0x2000+i]=seed>>24;}
   for(unsigned i=0;i<0x4000;i+=16){s.RamData()[0x2000+i]=(i/16%5)*16+4;s.RamData()[0x2001+i]=i%512==496?3:0;}
   unsigned active=scenario==0?0:scenario==2?12:4;
   for(unsigned vi=0;vi<24;vi++){
    SpuVoiceAttr a{};a.voice=1u<<vi;a.mask=~0u;a.pitch=vi<active?0x1000+vi*237:0x1000;
    a.addr=a.loop_addr=vi<active?0x2000+vi*512:0x1000;a.volume={0x3000,-0x2000};a.adsr1=0x7f0f;a.adsr2=0x1fc0;
    s.SetVoiceAttr(a);
    if(vi<active){s.SetKey(SPU_ON,1u<<vi);auto &v=s.m_voices[vi];v.envPhase=PsyX::EnvPhase::Sustain;v.envLevel=0x6000;}
   }
   s.SetMasterVolume(0x3fff,0x3fff);
   if(scenario==4){SpuReverbAttr a{};a.mask=~0u;a.mode=4;a.depth={0x3000,0x3000};s.SetReverbModeParam(a);s.SetReverbMasterEnable(true);s.SetVoiceReverbSend(0xffffff,true);}
   s.SetCdAudioEnable(scenario==3);s.SetCdVolume(0x4000,0x4000);
   short pcm[1024];double total=0;
   for(unsigned block=0;block<512;block++) {
    if(scenario==3)for(unsigned i=0;i<512;i++)s.PushCdStereoFrame((short)(block*137+i*31),(short)(i*157));
    if(scenario==5 && block==256)s.SetKey(SPU_ON,1u<<20);
    auto start=std::chrono::steady_clock::now();s.RenderFrames(pcm,512);
    if(block>=32)total+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
    checksum+=(unsigned short)pcm[23];
   }
   samples[trial]=total/480;
  }
  std::sort(samples,samples+7);printf("%u %.6f %.6f %.6f\n",scenario,samples[3],samples[0],samples[6]);
 }
 fprintf(stderr,"checksum=%u\n",checksum);
}
