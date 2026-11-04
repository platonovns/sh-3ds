"""Prepare an exact-only SPU and native copies of the original sound driver.

Desktop enhanced renderers and their multi-MiB delay lines are excluded.
No edits to the accepted renderer, maps, or original audio sources are needed.
"""
from pathlib import Path
import hashlib, json, re

p = Path(__file__).resolve().parents[1]
root = p.parent
out = p/'build/audio'
out.mkdir(parents=True, exist_ok=True)
inputs = []
def read(path):
    path = root/path
    inputs.append(path)
    return path.read_text()
def write(name, text):
    target = out/name
    if not target.exists() or target.read_text() != text:
        target.write_text(text)
def function(text, name, body):
    match = re.search(r'^.*\b'+re.escape(name)+r'\([^\n]*\)[^\n]*\n\{', text, re.M)
    assert match, name
    start = text.index('{', match.start())
    depth = 1; end = start+1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}'); end += 1
    return text[:start]+'{\n'+body+'\n}'+text[end:]

audio = 'pc_port/PsyCross/src/audio/'
h = read(audio+'PsyX_SPUCore.h')
h = h.replace('    PsyX_IdealReverb::Reverb m_idealReverb;','').replace('    PsyX_ReferenceReverb::Reverb m_referenceReverb;','')
h = re.sub(r'    struct ReferenceVoiceState\n    \{.*?    ReferenceVoiceState m_referenceVoices\[kNumVoices\];', '', h, flags=re.S)
h = h.replace('    void ClearCdQueue();', '''    void ClearCdQueue();
    // Native diagnostics only: samples actually added at the CD mix boundary.
    uint32_t nativeCdNonzero = 0, nativeCdPeak = 0;''')
write('PsyX_SPUCore.h', h)
c = read(audio+'PsyX_SPUCore.cpp')
# Everything following RenderFrames is exclusively enhanced/high-rate output.
c = c[:c.index('bool SPUCore::SetRenderer(')]+'\n} // namespace PsyX\n'
c = c.replace('    m_idealReverb.Reset();\n','').replace('    m_referenceReverb.Reset();\n','')
c = re.sub(r'^.*m_referenceVoices\[i\].*\n', '', c, flags=re.M)
# Key-on and decode contain optional Reference-resampler ingress only.
c = re.sub(r'    if \(voiceIndex >= 0 && voiceIndex < kNumVoices\)\n    \{\n        m_referenceVoices.*?\n    \}', '', c, flags=re.S)
c = re.sub(r'    if \(m_renderer == RendererMode::Reference && voiceIndex >= 0 && voiceIndex < kNumVoices\)\n        m_referenceVoices.*?;\n', '', c)
c = re.sub(r'    m_idealReverb\.[^\n]*\n','',c)
c = re.sub(r'    PsyX_IdealReverb::PsyQParameters ideal\{\};.*?    m_referenceReverb.SetPsyQParameters\(reference\);\n', '', c, flags=re.S)
c = re.sub(r'    PsyX_ReferenceReverb::PsyQParameters reference\{\};.*?    m_referenceReverb.SetPsyQParameters\(reference\);\n', '', c, flags=re.S)
assert not re.search(r'm_referenceVoices|m_referenceReverb|m_idealReverb', c)
# A zero-pitch, fixed-volume voice with a stationary envelope has no state that changes
# between samples. Mirror its direct volume registers once per locked block.
# Keep decoding all nonzero-pitch voices, including released/off voices: ENDX,
# loop position, sweeps and PMON semantics remain intact. Split taps use the
# original path. This removes idle hardware-voice overhead on the ARM11.
signature='void SPUCore::RenderFrames(int16_t* outInterleavedLR, int frameCount, SplitOutput* split)\n{'
assert signature in c
c = c.replace(signature,signature+'''
    uint32_t frozenVoices = 0;
    if (frameCount > 0 && !split)
    {
        for (int vi = 0; vi < kNumVoices; ++vi)
        {
            SPUVoiceState& v = m_voices[vi];
            // libsd stops unused voices in Release with RR=0. At zero level
            // and shift <=11, each envelope tick adds 0x8000 then masks it
            // off, leaving both level and counter unchanged. Preserve that
            // Release phase rather than normalizing it to Off.
            const bool frozenEnvelope = v.envPhase == EnvPhase::Off ||
                (v.envPhase == EnvPhase::Release && v.envLevel == 0 && (v.attr.rr & 31) <= 11);
            if (v.attr.pitch == 0 && frozenEnvelope &&
                v.attr.volmode.left == SPU_VOICE_DIRECT16 &&
                v.attr.volmode.right == SPU_VOICE_DIRECT16)
            {
                v.curVolL = static_cast<int32_t>(v.attr.volume.left) * 2;
                v.curVolR = static_cast<int32_t>(v.attr.volume.right) * 2;
                v.attr.volumex.left = SaturateS16(v.curVolL);
                v.attr.volumex.right = SaturateS16(v.curVolR);
                v.attr.envx = 0;
                v.lastOutX = 0;
                frozenVoices |= 1u << vi;
            }
        }
    }
''')
render_start=c.index(signature)
before,render=c[:render_start],c[render_start:]
needle='            SPUVoiceState& v = m_voices[vi];'
assert needle in render
at=render.rindex(needle)
render=render[:at]+'''            if (frozenVoices & (1u << vi))
            {
                prevVoiceOutX = 0;
                continue;
            }
'''+render[at:]
c=before+render
# Sample one rotating PCM frame per render block. Clock reads never run in
# the other 511 frames. Estimates are separate from the exact block total;
# neither arithmetic nor SPU state is changed. Host fidelity tests compile
# without SH_3DS_GAME and exercise the unchanged math.
c='#ifdef SH_3DS_GAME\n#include "game_profile.h"\n#endif\n'+c
needle='    for (int f = 0; f < frameCount; ++f)\n    {'
assert c.count(needle)==1
c=c.replace(needle,'''#ifdef SH_3DS_GAME
    static unsigned profile_phase;
    const int profile_frame = game_prof_enabled && frameCount > 0 ?
        (int)((profile_phase++ * 73u) % (unsigned)frameCount) : -1;
#endif
'''+needle+'''
#ifdef SH_3DS_GAME
        uint64_t profile_voice = f == profile_frame ? game_prof_clock() : 0;
#endif
''')
needle='''        if (m_muted)
        {'''
assert c.count(needle)==1
c=c.replace(needle,'''#ifdef SH_3DS_GAME
        if (f == profile_frame) game_prof_audio_add(GP_SPU_VOICES,
            (game_prof_clock() - profile_voice) * frameCount);
#endif
'''+needle)
needle='''        m_reverb.Process(m_ram, kSpuRamSize,'''
assert c.count(needle)==1
c=c.replace(needle,'''#ifdef SH_3DS_GAME
        uint64_t profile_reverb = f == profile_frame ? game_prof_clock() : 0;
#endif
'''+needle)
needle='''                         &reverbOutL, &reverbOutR);'''
assert c.count(needle)==1
c=c.replace(needle,needle+'''
#ifdef SH_3DS_GAME
        if (f == profile_frame) game_prof_audio_add(GP_SPU_REVERB,
            (game_prof_clock() - profile_reverb) * frameCount);
        uint64_t profile_mix = f == profile_frame ? game_prof_clock() : 0;
#endif
''')
needle='''    if (split)
    {
        /* End-of-block pan'''
assert c.count(needle)==1
at=c.index(needle)
before,after=c[:at],c[at:]
needle='''        }
    }

'''
assert before.endswith(needle)
before=before[:-len(needle)]+'''        }
#ifdef SH_3DS_GAME
        if (f == profile_frame) game_prof_audio_add(GP_SPU_MIX,
            (game_prof_clock() - profile_mix) * frameCount);
#endif
    }

'''
c=before+after
# Observe the actual post-CD-volume contribution without selecting SplitOutput
# (which would disable the native idle-voice fast path). PCM math is unchanged.
needle='''            mixL += cdL;
            mixR += cdR;'''
assert c.count(needle)==1
c=c.replace(needle,needle+'''
            nativeCdNonzero += (cdL != 0) + (cdR != 0);
            uint32_t cdPeakL = cdL < 0 ? -cdL : cdL;
            uint32_t cdPeakR = cdR < 0 ? -cdR : cdR;
            if (cdPeakL > nativeCdPeak) nativeCdPeak = cdPeakL;
            if (cdPeakR > nativeCdPeak) nativeCdPeak = cdPeakR;
''')
write('PsyX_SPUCore.cpp', c)

for name in ('smf_io.c','smf_main.c','smf_mid.c','smf_snd.c'):
    text = read('src/bodyprog/libsd/'+name)
    # Retain only the portable original driver, without desktop mods/threads.
    text = text.replace('#ifdef SH_PC_PORT', '#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)')
    text = text.replace('SpuGetKeyStatus(spu_ch_tbl[vo] == 1)', 'SpuGetKeyStatus(spu_ch_tbl[vo])')
    text = text.replace('SpuGetKeyStatus(spu_ch_tbl[voice] == 1)', 'SpuGetKeyStatus(spu_ch_tbl[voice])')
    if name == 'smf_main.c':
        for fn in ('smf_timer_set','smf_timer_end','smf_timer_stop'):
            text = function(text, fn, '    /* Native clock is pumped on the game thread. */')
    if name == 'smf_io.c':
        text = '#include "game.h"\n#include "bodyprog/sound/sound_system.h"\n'+text
        text = text.replace('addr_p = (u8*)vab_h[vabId].vh_addr_4 + (vab0->vab_h.ps * 512) + 2080',
                            'addr_p = (u16*)((u8*)vab_h[vabId].vh_addr_4 + (vab0->vab_h.ps * 512) + 2080)')
    if name == 'smf_snd.c':
        text = '#include "game.h"\n#include "bodyprog/sound/sound_system.h"\n'+text
        text = text.replace('SpuInitMalloc(16, &sd_vb_malloc_rec)', 'SpuInitMalloc(16, (char*)sd_vb_malloc_rec)')
        text = re.sub(r'addr_p = (\(u8\*\)[^;]+);', r'addr_p = (u16*)(\1);', text)
        text = text.replace('    prog  = vab_pro & 0x7F;',
            '    if ((u32)(vab_pro >> 8) >= SD_VAB_SLOTS) return -1;\n    prog  = vab_pro & 0x7F;')
        text = re.sub(r'(    sd_vh\s*= vab_h\[vabid\].vh_addr_4;)',
            r'\1\n    if (!sd_vh || (u32)sd_vh->vab_h.ps > 128) { sd_int_flag = false; return -1; }',text)
    write(name, text)
write('smf_tables.h', read('src/bodyprog/libsd/smf_tables.h'))
text = read('src/bodyprog/sound/sd_call.c')
text = text.replace('#ifdef SH_PC_PORT', '#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)')
text = text.replace('#include <psyq/libspu.h>', '#include <psyq/libspu.h>\n#include "game_audio_cd.h"')
# Preserve the original CD task machine. Its watchdog measures consumed audio
# ticks, including the authored 32-tick tail, instead of rendered frames.
text = text.replace('D_800C1688.field_4 = VSync(SyncMode_Count) - D_800C1688.field_8;',
                    'D_800C1688.field_4 = game_xa_elapsed60();')
# Explicit stop/skip cancels the producer immediately; queued driver cleanup
# still restores the original music and serial-input state.
text = text.replace('    Sd_TaskPoolAdd(2);\n    g_Sd_AudioWork.isXaNotPlaying_16',
                    '''    if (!native_cancel_reason) game_xa_cancel(XA_CANCEL_ORIGINAL, 0, 0);
    SdSetSerialAttr(0, 0, 0);
    /* A skip can arrive while seek/preload is still queued. Remove only XA
     * start/preload tasks; leave VAB/KDT tasks and original stop cleanup. */
    for (unsigned i=0; i<32; ) {
        if (g_Sd_TaskPool[i] == 1 || g_Sd_TaskPool[i] == 6) {
            for (unsigned j=i; j<31; ++j) g_Sd_TaskPool[j]=g_Sd_TaskPool[j+1];
            g_Sd_TaskPool[31]=0;
        } else ++i;
    }
    g_Sd_AudioStreamingStates.xaLoadState_1 = XaLoadState_Initialize;
    g_Sd_AudioStreamingStates.xaPreLoadState_3 = 0;
    D_800C37DC = false;
    Sd_TaskPoolAdd(2);
    g_Sd_AudioWork.isXaNotPlaying_16''')
text = text.replace('    g_Sd_CurrentTask = g_Sd_TaskPool[0];', '''    game_audio_tick();
    g_Sd_CurrentTask = g_Sd_TaskPool[0];
    {
        static uint32_t previous = ~0u;
        uint32_t states = g_Sd_AudioStreamingStates.xaLoadState_1 |
            (g_Sd_AudioStreamingStates.xaStopState_2 << 8) |
            (g_Sd_AudioStreamingStates.xaPreLoadState_3 << 16) | (g_Sd_CurrentTask << 24);
        if (states != previous) {
            previous=states;
            game_xa_note(XA_NOTE_DRIVER,g_Sd_CurrentTask,states,
                g_Sd_AudioWork.xaAudioIdx_4 | (D_800C37DC << 24));
        }
    }''')
text=text.replace('    g_Sd_AudioWork.xaAudioIdxCheck_2 = sfx & 0xFFF;', '''    g_Sd_AudioWork.xaAudioIdxCheck_2 = sfx & 0xFFF;
    game_xa_note(XA_NOTE_REQUEST,sfx & 0xFFF,0,0);''')
text=text.replace('    g_Sd_AudioWork.xaAudioIdxCheck_2 = xaIdx & 0xFFF;', '''    g_Sd_AudioWork.xaAudioIdxCheck_2 = xaIdx & 0xFFF;
    game_xa_note(XA_NOTE_PRELOAD,xaIdx & 0xFFF,0,0);''')
text=text.replace('        case XaLoadState_EnableAudio:', '''        case XaLoadState_EnableAudio:
            game_xa_note(XA_NOTE_ACTIVE,xaAudioIdx,0,0);''')
text=text.replace('''            if (g_Sd_AudioWork.isXaNotPlaying_16 == false)
            {
                Sd_TaskPoolAdd(2);''', '''            if (g_Sd_AudioWork.isXaNotPlaying_16 == false)
            {
                game_xa_note(XA_NOTE_WATCHDOG,D_800C1688.field_4,D_800C1688.field_0,g_Sd_AudioWork.xaAudioIdx_4);
                Sd_TaskPoolAdd(2);''')
text = text.replace('    SdInit();', '    PcPort_InitSdBuffers();\n    SdInit();')
text = text.replace('SdSeqOpen(g_Sd_KdtBuffer[g_Sd_AudioType], 3)', 'SdSeqOpen((s32*)g_Sd_KdtBuffer[g_Sd_AudioType], 3)')
text = '#include "game3ds.h"\n#include "game_audio.h"\n#include "game_xa.h"\nstatic uint32_t native_cancel_reason;\nvoid PcPort_InitSdBuffers(void);\n'+text
text += '''
void game_audio_xa_cancel(uint32_t reason,uint32_t context0,uint32_t context1)
{
    native_cancel_reason=reason;
    game_xa_cancel(reason,context0,context1);
    Sd_XaAudioStopTaskAdd();
    native_cancel_reason=0;
}
uint32_t game_audio_xa_ticks(void)
{
    uint32_t idx=g_Sd_AudioWork.xaAudioIdxCheck_2;
    return idx<727 ? g_XaItemData[idx].audioLength_8 : 0;
}
uint32_t game_audio_xa_pending(void)
{
    if (g_Sd_AudioWork.xaAudioIdx_4 || D_800C37DC) return 1;
    for (unsigned i=0; i<32; ++i)
        if (g_Sd_TaskPool[i] == 1 || g_Sd_TaskPool[i] == 6) return 1;
    return 0;
}
void game_audio_driver_report(FILE *out)
{
    fprintf(out,"audio_busy=%u\\naudio_task=%u\\naudio_task_head=%u\\naudio_load_state=%u\\naudio_bgm_id=%u\\n",
        Sd_AudioStreamingCheck(),g_Sd_CurrentTask,g_Sd_TaskPool[0],
        g_Sd_AudioStreamingStates.audioLoadState_0,g_Sd_AudioWork.bgmLoadedSongIdx_6);
}
'''
write('sd_call.c', text)
# Reuse the repository's disc ADPCM decoder without SDL, config or WAV paths.
xa = read('pc_port/src/xa_player_software.c')
decoder = xa[xa.index('static const int16_t g_FilterPos'):xa.index('/* Begin streaming XA file')]
decoder = decoder[:decoder.index('typedef struct {')]+decoder[decoder.index('static int16_t ClampS16'):]
decoder = decoder.replace('g_XaPlayer.lastSamples', 'history')
decoder = decoder.replace('static int DecodeXaSector(const uint8_t* sector, int16_t* pcmOut)',
                          'int game_xa_decode(const uint8_t* sector, int16_t* pcmOut, int32_t history[2][2])')
write('xa_decode.c', '/* Extracted from pc_port/src/xa_player_software.c (GPL-3.0-or-later). */\n#include <stdint.h>\n'+decoder)
# The native fileinfo build omits this table under SH_PC_PORT. Use the original
# USA table, matching the supported native disc/region, rather than clip offsets.
fi = read('src/main/fileinfo.c')
locations = fi[fi.index('u32 g_FileXaLoc[] = {'):]
locations = locations[locations.index('#if VERSION_IS(USA)')+len('#if VERSION_IS(USA)'):locations.index('#elif')]
write('xa_locations.h', 'u32 g_FileXaLoc[] = {'+locations+'};\n')
manifest = {str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
write('inputs.json', json.dumps(manifest, indent=2)+'\n')
