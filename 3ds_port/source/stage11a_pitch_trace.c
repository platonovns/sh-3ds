/* Original libsd context, sampled only when an unused voice changes pitch.
 * Scope nesting is on the main MIDI caller, not on the PCM worker. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/libsd.h"
#include "stage11a_pitch_trace.h"
static Stage11aPitchScope current;
Stage11aPitchScope stage11a_pitch_enter(unsigned kind,unsigned channel,unsigned cc1,unsigned cc2,uintptr_t caller)
{
    Stage11aPitchScope saved=current;
    current=(Stage11aPitchScope){kind,channel,cc1,cc2,(uint32_t)caller};return saved;
}
void stage11a_pitch_leave(Stage11aPitchScope *saved){current=*saved;}
void stage11a_pitch_midi_snapshot(unsigned voice,uint32_t out[SH_PITCH_MIDI_WORDS])
{
    out[0]=current.kind;out[1]=current.channel;out[2]=current.cc1;out[3]=current.cc2;
    out[14]=current.caller;
    if(voice>=24)return;
    const PORT *p=&smf_port[voice];
    out[4]=p->vc_0;out[5]=p->stat_16;out[6]=p->midi_ch_3;out[7]=(uint32_t)p->note_wk_8;
    out[8]=(uint32_t)p->pbend_wk_4E;out[9]=p->vibdm_26;out[10]=p->rdms_43;
    if((unsigned)p->midi_ch_3<32) {
        const MIDI *m=&smf_midi[(unsigned)p->midi_ch_3];
        out[11]=m->pbend_7;out[12]=m->mod_2;out[13]=m->porta_28;
    }
}
