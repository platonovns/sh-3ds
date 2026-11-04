"""Private, state-preserving silent-voice candidate from the frozen SPU source."""
import json
from pathlib import Path
import zipfile
PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent


def prepare(dest):
    dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((PORT / 'reports/stage11a-baseline.json').read_text())
    with zipfile.ZipFile(ROOT / baseline['source_snapshot']) as archive:
        header = archive.read('3ds_port/build/audio/PsyX_SPUCore.h')
        source = archive.read('3ds_port/build/audio/PsyX_SPUCore.cpp').decode()
    source = source.replace('#ifdef SH_3DS_GAME', '#if defined(SH_3DS_GAME) && !defined(SH_STAGE11A_LIFETIME)')
    # No object-layout change, register write suppression, reset, lazy state or
    # block-wide decoder batching. Advance every voice in its original position
    # relative to RAM/reverb writes on EVERY output sample.
    decl = '''
#include <stdint.h>
#include <cstring>
#if defined(SH_STAGE11A_TRACEFIX)
extern "C" unsigned game_spu_silent_fast_enabled(void);
extern "C" void game_spu_silent_fast_observe(uint32_t eligible, uint32_t used, uint32_t grouped, unsigned frames);
#endif
'''
    source = decl + source
    decoder_fields = ('curAddr repeatAddr repeatAddrLatchedByBlock adpcmHist1 adpcmHist2 '
                      'blockSamplePos blockValid pitchCounter reachedLoopEnd blockLoopEnd '
                      'forceReleaseOnBlockEnd envPhase envLevel envCounter').split()
    helper = '''#if defined(SH_STAGE11A_TRACEFIX)
// Identical unkeyed ADPCM machines see the same RAM image on each sample:
// voice stepping only reads RAM; reverb writes occur AFTER all voices. Step
// one representative at the original sample cadence, then copy decoder state
// before returning under the core lock. No read is moved across a reverb tick.
static bool SameSilentDecoder(const SPUVoiceState& a,const SPUVoiceState& b)
{
    return ''' + ' &&\n        '.join('a.'+f+' == b.'+f for f in decoder_fields) + ''' &&
        std::memcmp(a.blockSamples,b.blockSamples,sizeof(a.blockSamples)) == 0 &&
        std::memcmp(a.interpTaps,b.interpTaps,sizeof(a.interpTaps)) == 0;
}
static void CopySilentDecoder(SPUVoiceState& a,const SPUVoiceState& b)
{
''' + '\n'.join('    a.'+f+' = b.'+f+';' for f in decoder_fields) + '''
    std::memcpy(a.blockSamples,b.blockSamples,sizeof(a.blockSamples));
    std::memcpy(a.interpTaps,b.interpTaps,sizeof(a.interpTaps));
}
#endif
'''
    source = source.replace('void SPUCore::RenderFrames(', helper+'\nvoid SPUCore::RenderFrames(',1)
    anchor = '    uint32_t frozenVoices = 0;'
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '''
#if defined(SH_STAGE11A_TRACEFIX)
    uint32_t silentAdvanceVoices = 0, silentEligibleVoices = 0;
    uint32_t silentGroupedVoices = 0;
    unsigned silentParent[kNumVoices] = {};
    uint32_t silentSteps[kNumVoices] = {};
    const bool silentFastEnabled = game_spu_silent_fast_enabled() != 0;
#endif''')
    anchor = '            if (v.attr.pitch == 0 && frozenEnvelope &&'
    assert source.count(anchor) == 1
    source = source.replace(anchor, '''#if defined(SH_STAGE11A_TRACEFIX)
            // RR<=11 at level zero leaves the low 15 envelope-counter bits
            // unchanged, for linear AND exponential release. Decode may set
            // Release/level=0/counter=0 on End+Mute; this remains stationary.
            // PMON and sweeps fall back; split taps use the original path.
            const bool silentEligible = v.attr.pitch != 0 && v.envLevel == 0 &&
                frozenEnvelope && (v.attr.rr & 31) <= 11 && v.envCounter < 0x8000u &&
                !v.pitchModEnable && v.attr.volmode.left == SPU_VOICE_DIRECT16 &&
                v.attr.volmode.right == SPU_VOICE_DIRECT16;
            if (silentEligible) silentEligibleVoices |= 1u << vi;
            if ((v.attr.pitch == 0 || (silentFastEnabled && silentEligible)) && frozenEnvelope &&
#else
            if (v.attr.pitch == 0 && frozenEnvelope &&
#endif''')
    anchor = '                frozenVoices |= 1u << vi;'
    assert source.count(anchor) == 1
    source = source.replace(anchor, '''#if defined(SH_STAGE11A_TRACEFIX)
                if (v.attr.pitch != 0)
                {
                    silentAdvanceVoices |= 1u << vi;
                    silentSteps[vi] = ResolveVoiceStep(v, vi, 0);
                }
                else
#endif
                frozenVoices |= 1u << vi;''')
    anchor = '    for (int f = 0; f < frameCount; ++f)'
    # Native and other renderers contain similar loops. First is RenderFrames.
    at = source.index(anchor, source.index('void SPUCore::RenderFrames('))
    source = source[:at] + '''#if defined(SH_STAGE11A_TRACEFIX)
    for (unsigned vi=0;vi<kNumVoices;vi++) if ((silentAdvanceVoices & (1u<<vi)) &&
        !m_voices[vi].everKeyedOn && !m_voices[vi].ovrPcm)
    {
        for (unsigned parent=0;parent<vi;parent++) if ((silentAdvanceVoices & (1u<<parent)) &&
            !m_voices[parent].everKeyedOn && !m_voices[parent].ovrPcm &&
            silentSteps[vi] == silentSteps[parent] && SameSilentDecoder(m_voices[vi],m_voices[parent]))
        {
            silentParent[vi]=parent;silentGroupedVoices |= 1u<<vi;
            silentAdvanceVoices &= ~(1u<<vi);frozenVoices |= 1u<<vi;break;
        }
    }
    game_spu_silent_fast_observe(silentEligibleVoices, silentAdvanceVoices | silentGroupedVoices, silentGroupedVoices,
                                frameCount > 0 ? (unsigned)frameCount : 0);
#endif
''' + source[at:]
    anchor = '''            SPUVoiceState& v = m_voices[vi];

            // Hardware always keeps decoding/advancing every voice'''
    assert source.count(anchor) == 1
    source = source.replace(anchor, '''            SPUVoiceState& v = m_voices[vi];
#if defined(SH_STAGE11A_TRACEFIX)
            if (silentAdvanceVoices & (1u << vi))
            {
                // Same pitch ticks, raw-sample shifts, decoder history,
                // loop/repeat/ENDX and reverb/RAM chronology as the reference.
                // Gaussian interpolation has no state; zero envelope makes
                // interpolation/noise/pan/reverb-send contributions exactly 0.
                v.pitchCounter += silentSteps[vi];
                while (v.pitchCounter >= kPitchUnity)
                {
                    ShiftInNextRawSample(v, vi);
                    v.pitchCounter -= kPitchUnity;
                }
                prevVoiceOutX = 0;
                continue;
            }
#endif

            // Hardware always keeps decoding/advancing every voice''')
    anchor = '''    if (split)
    {
        /* End-of-block pan'''
    assert source.count(anchor)==1
    source=source.replace(anchor,'''#if defined(SH_STAGE11A_TRACEFIX)
    for (unsigned vi=0;vi<kNumVoices;vi++) if (silentGroupedVoices & (1u<<vi))
        CopySilentDecoder(m_voices[vi],m_voices[silentParent[vi]]);
#endif

''' + anchor)
    (dest / 'PsyX_SPUCore.cpp').write_text(source)
    (dest / 'PsyX_SPUCore.h').write_bytes(header)
    return dest


if __name__ == '__main__':
    print(prepare(PORT / 'build/stage11a-tracefix/audio'))
