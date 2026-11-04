int main()
{
    std::setvbuf(stdout,nullptr,_IOFBF,65536);
    static const unsigned pitches[]={0,1,0x800,0xfff,0x1000,0x3fff,0x4000,0xffff};
    static const unsigned lengths[]={0,1,2,27,28,29,127,511,512,513};
    for(unsigned scenario=0;scenario<72;scenario++) {
        PsyX::SPUCore s;seed=0x110af100+scenario;
        for(unsigned i=0;i<sizeof(s.m_ram);i++)s.m_ram[i]=random32()>>24;
        for(unsigned i=0;i<sizeof(s.m_ram);i+=16){s.m_ram[i]=(i/16)%80;s.m_ram[i+1]=(i/16)%8;}
        s.SetMasterVolume(0x3fff,-0x3000);s.SetCdVolume(0x4000,0x3000);
        SpuReverbAttr rev{};rev.mask=~0u;rev.mode=scenario%10;rev.depth={0x3000,-0x2000};
        s.SetReverbModeParam(rev);s.SetReverbMasterEnable(true);s.SetVoiceReverbSend(0xffffff,true);
        // Put some decoders inside live reverb RAM: batching ahead of the
        // reverb clock would change ADPCM state and fail the oracle.
        for(unsigned i=0;i<24;i++) {
            auto& v=s.m_voices[i];v.attr.pitch=pitches[(i+scenario)%8];
            v.curAddr=v.repeatAddr=(scenario&1?0x7e000:0x2000)+i*16;
            v.envPhase=(scenario&2)?PsyX::EnvPhase::Off:PsyX::EnvPhase::Release;
            v.envLevel=0;v.envCounter=scenario&4?12345:0;
            v.attr.rr=(scenario%4==0)?11:(scenario%4==1)?12:(scenario%4==2)?0:31;
            v.attr.r_mode=scenario&1;v.everKeyedOn=(i%3==0);
            v.attr.volume={(short)random32(),(short)random32()};
            v.attr.volmode.left=v.attr.volmode.right=SPU_VOICE_DIRECT16;
            if(scenario>=48){
                v.curAddr=v.repeatAddr=(scenario&1)?0x7e000:0x2000;
                v.attr.pitch=4096;v.envCounter=0;v.attr.rr=0;v.everKeyedOn=false;
                v.envPhase=PsyX::EnvPhase::Release;
            }
        }
        s.SetVoiceNoiseMode((scenario&8)?0xaaaaaa:0,true);
        s.SetVoicePitchModEnable((scenario&16)?0xeeeeee:0,true);
        int16_t pcm[1026],taps[24][513],wet[1026],cd[1026];
        for(unsigned step=0;step<24;step++) {
            unsigned vi=(step*7)%24;
            if(step==4 || step==17){s.SetKey(SPU_ON,1u<<vi);}
            if(step==6 || step==19)s.SetKey(SPU_OFF,1u<<vi);
            if(step==8){s.m_voices[vi].attr.volmode.left=SPU_VOICE_EXPIncN;}
            if(step==9){s.m_voices[vi].attr.rr=12;}
            if(step==10){s.SetVoicePitch(vi,0x4000);s.SetKey(SPU_ON,1u<<vi);}
            if(step==12){s.m_ram[0x7e001]^=7;s.m_ram[0x2001]^=3;}
            if(step==15)s.SetVoicePitchModEnable(0xfffffe,true);
            if(step==16)s.SetVoicePitchModEnable(0xfffffe,false);
            unsigned n=lengths[(step+scenario)%10];
            PsyX::SPUCore::SplitOutput split{};
            for(unsigned i=0;i<24;i++)split.voiceMono[i]=taps[i];split.wetLR=wet;split.cdLR=cd;
            bool split_on=step==3 || step==13;
            std::memset(pcm,0x5a,sizeof(pcm));std::memset(taps,0x5a,sizeof(taps));
            std::memset(wet,0x5a,sizeof(wet));std::memset(cd,0x5a,sizeof(cd));
            s.SetCdAudioEnable(step%2);s.SetCdAudioReverb(step%3);
            s.PushCdStereoFrame((int16_t)random32(),(int16_t)random32());
            s.RenderFrames(step%11?pcm:nullptr,n,split_on?&split:nullptr);
            value(scenario);value(step);bytes(pcm,sizeof(pcm));
            if(split_on){bytes(taps,sizeof(taps));bytes(wet,sizeof(wet));bytes(cd,sizeof(cd));}
            snapshot(s);
        }
    }
    return std::fflush(stdout)?1:0;
}
