/* Bit/state comparison fixture: compile against upstream and native SPU. */
#include "PsyX_SPUCore.h"
#include <cstdio>
#include <cstring>
#include <vector>
static uint64_t hash(const void *data,size_t size)
{
    uint64_t value=1469598103934665603ull;
    const unsigned char *p=static_cast<const unsigned char*>(data);
    while(size--){value^=*p++;value*=1099511628211ull;}
    return value;
}
int main()
{
    PsyX::SPUCore core;
    uint32_t random=12345;
    for(unsigned i=0;i<4096;i++){random=random*1664525u+1013904223u;core.RamData()[0x2000+i]=random>>24;}
    for(unsigned i=0;i<4096;i+=16){core.RamData()[0x2000+i]=0x04;core.RamData()[0x2001+i]=3;}
    core.SetMasterVolume(0x3fff,0x3fff);
    std::vector<int16_t> pcm(2048);
    for(int test=0;test<48;test++)
    {
        int voice=(test*7)%24;
        SpuVoiceAttr a{};a.voice=1u<<voice;a.mask=~0u;
        a.addr=0x2000;a.loop_addr=0x2000;a.pitch=test%4?0x1000:0;
        a.volume.left=0x3000-test*23;a.volume.right=-0x2000+test*31;
        a.volmode.left=a.volmode.right=SPU_VOICE_DIRECT16;
        a.adsr1=0x00ff;a.adsr2=0x0000;
        core.SetVoiceAttr(a);
        if(test%3==1)core.SetKey(SPU_ON,a.voice);
        if(test%3==2)core.SetKey(SPU_OFF,a.voice);
        unsigned frames=(test*71)%1024;
        PsyX::SPUCore::SplitOutput split{};
        core.RenderFrames(pcm.data(),frames,test%7?nullptr:&split);
        uint64_t state=0;
        for(int v=0;v<24;v++)state^=hash(&core.GetVoiceState(v),sizeof(PsyX::SPUVoiceState))*(v+1);
        std::printf("%d %016llx %016llx %016llx %06lx\n",test,
            (unsigned long long)hash(pcm.data(),frames*4),(unsigned long long)state,
            (unsigned long long)hash(core.RamData(),PsyX::kSpuRamSize),(unsigned long)core.GetEndxFlags());
    }
}
