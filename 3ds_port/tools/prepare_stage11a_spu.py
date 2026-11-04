"""Instrument the exact frozen native SPU in a private directory; no math edits.

The normal prepare_audio.py and build/audio are intentionally untouched. Detail
is compiled away with SH_STAGE11A_SPU_DETAIL=0 (the frame-pacing control build).
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

PORT = Path(__file__).resolve().parents[1]


def prepare(dest):
    receipt = json.loads((PORT / 'reports/stage11a-baseline.json').read_text())
    snapshot = PORT.parent / receipt['source_snapshot']
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == receipt['source_snapshot_sha256']
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(snapshot) as archive:
        for name in ('PsyX_SPUCore.h', 'PsyX_SPUCore.cpp'):
            (dest / name).write_bytes(archive.read('3ds_port/build/audio/' + name))
    c = (dest / 'PsyX_SPUCore.cpp').read_text()

    def replace(old, new):
        nonlocal c
        assert c.count(old) == 1, (old[:90], c.count(old))
        c = c.replace(old, new)

    c = '''#if SH_STAGE11A_SPU_DETAIL
#include "stage11a_perf.h"
#include "game_profile.h"
static bool stage11a_sampling;
Stage11aSpuScope::~Stage11aSpuScope() {
    if(begin)stage11a_perf_add(metric,game_prof_clock()-begin);
}
#endif
''' + c
    for name, metric in [('DecodeAdpcmBlock(SPUVoiceState& v, int voiceIndex)', 'S11_DECODE'),
                         ('StepAdsr(SPUVoiceState& v)', 'S11_ADSR')]:
        anchor = 'void SPUCore::' + name + '\n{'
        replace(anchor, anchor + f'''
#if SH_STAGE11A_SPU_DETAIL
    Stage11aSpuScope detail({metric},stage11a_sampling,game_prof_clock);
#endif''')
    anchor = 'int32_t SPUCore::StepVoiceOneSample(SPUVoiceState& v, int voiceIndex, int32_t prevVoiceOutX)\n{'
    replace(anchor, anchor + '''
#if SH_STAGE11A_SPU_DETAIL
    uint64_t advance=stage11a_sampling?game_prof_clock():0;
#endif''')
    anchor = '    int interpIndex = static_cast<int>((v.pitchCounter >> 4) & 0xFF);'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
    if(advance)stage11a_perf_add(S11_ADVANCE,game_prof_clock()-advance);
    Stage11aSpuScope interpolation(S11_INTERPOLATE,stage11a_sampling,game_prof_clock);
#endif
''' + anchor)
    anchor = '    for (int f = 0; f < frameCount; ++f)\n    {'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
    static unsigned detail_block;
    const unsigned block=detail_block++;
    const int detail_frame=stage11a_perf_active() && frameCount>0 && block%16==0 ?
        (int)(((block/16)*73u)%(unsigned)frameCount) : -1;
#endif
''' + anchor + '''
#if SH_STAGE11A_SPU_DETAIL
        stage11a_sampling=f==detail_frame;
#endif''')
    anchor = '            if (frozenVoices & (1u << vi))\n            {'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
            if(stage11a_sampling)stage11a_perf_add(S11_VOICE,0);
#endif
''' + anchor + '''
#if SH_STAGE11A_SPU_DETAIL
                if(stage11a_sampling)stage11a_perf_add(S11_FROZEN,0);
#endif''')
    anchor = '            int32_t interpolated = StepVoiceOneSample(v, vi, prevVoiceOutX);'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
            if(stage11a_sampling) {
                if(v.envLevel)stage11a_perf_add(S11_ACTIVE,0);
                if(v.noiseMode)stage11a_perf_add(S11_NOISE,0);
                if(v.pitchModEnable)stage11a_perf_add(S11_PMON,0);
            }
#endif
''' + anchor)
    anchor = '            if (v.attr.volmode.left == SPU_VOICE_DIRECT16)'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
            uint64_t volume=stage11a_sampling?game_prof_clock():0;
#endif
''' + anchor)
    anchor = '            /* Pre-pan mono tap for the spatialiser:'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
            if(volume)stage11a_perf_add(S11_VOLUME,game_prof_clock()-volume);
            uint64_t accumulation=stage11a_sampling?game_prof_clock():0;
#endif
''' + anchor)
    anchor = '''                reverbInR += voiceR;
            }
        }'''
    replace(anchor, anchor[:-len('        }')] + '''#if SH_STAGE11A_SPU_DETAIL
            if(accumulation)stage11a_perf_add(S11_ACCUMULATE,game_prof_clock()-accumulation);
#endif
        }''')
    anchor = '        // CD Audio input (post CD volume), matching the mixer path described'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
        uint64_t cd_mix=stage11a_sampling?game_prof_clock():0;
#endif
''' + anchor)
    anchor = '        int32_t reverbOutL = 0;'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
        if(cd_mix)stage11a_perf_add(S11_CD,game_prof_clock()-cd_mix);
        uint64_t reverb=stage11a_sampling?game_prof_clock():0;
#endif
''' + anchor)
    anchor = '                         &reverbOutL, &reverbOutR);'
    replace(anchor, anchor + '''
#if SH_STAGE11A_SPU_DETAIL
        if(reverb)stage11a_perf_add(S11_REVERB,game_prof_clock()-reverb);
        uint64_t output=stage11a_sampling?game_prof_clock():0;
#endif''')
    anchor = '            outInterleavedLR[f * 2 + 1] = SaturateS16(static_cast<int32_t>(mixR));\n        }'
    replace(anchor, anchor + '''
#if SH_STAGE11A_SPU_DETAIL
        if(output)stage11a_perf_add(S11_OUTPUT,game_prof_clock()-output);
#endif''')
    anchor = '    if (split)\n    {\n        /* End-of-block pan'
    replace(anchor, '''#if SH_STAGE11A_SPU_DETAIL
    stage11a_sampling=false;
#endif
''' + anchor)
    (dest / 'PsyX_SPUCore.cpp').write_text(c)
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PORT / 'build/stage11a-control/audio')
    prepare(parser.parse_args().output)
