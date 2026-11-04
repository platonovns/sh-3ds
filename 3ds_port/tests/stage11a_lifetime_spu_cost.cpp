/* Isolated synthetic settled voices, NOT a game replay or hardware benchmark. */
#include <chrono>
#include <cstdio>
#include <cstring>
#include <deque>
#include <vector>
#define private public
#include "PsyX_SPUCore.h"
#undef private
int main()
{
    for(unsigned count: {0u,6u,12u,24u}) {
        PsyX::SPUCore s;
        for(unsigned i=0;i<24;i++) {
            auto& v=s.m_voices[i];v.attr.pitch=i<count?0x1000:0;
            v.envPhase=PsyX::EnvPhase::Release;v.envLevel=0;v.envCounter=0;v.attr.rr=0;
            v.attr.volmode.left=v.attr.volmode.right=SPU_VOICE_DIRECT16;
            v.curAddr=v.repeatAddr=0x2000;v.attr.addr=v.attr.loop_addr=0x2000;
            v.everKeyedOn=i<count;
        }
        s.RamData()[0x2000]=4;s.RamData()[0x2001]=3; /* bounded ADPCM loop */
        int16_t pcm[1024];
        for(unsigned i=0;i<64;i++)s.RenderFrames(pcm,512);
        auto before=s.m_voices[0].blockSamplePos;
        auto start=std::chrono::steady_clock::now();
        for(unsigned i=0;i<1024;i++)s.RenderFrames(pcm,512);
        double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/1024;
        unsigned nonzero=0;for(auto v:pcm)nonzero+=v!=0;
        if(nonzero)return 1;
        std::printf("%u %.6f %u %u %u %zu\n",count,us,nonzero,before,s.m_voices[0].blockSamplePos,sizeof(s));
    }
}
