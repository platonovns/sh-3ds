"""Private pitch-writer trace plus runtime F0/F1 candidate; no MIDI/reset/affinity change."""
import hashlib
import json
import os
import re
import shlex
import subprocess
import zipfile
from pathlib import Path
from stage11a_baseline import verify
from prepare_stage11a_tracefix import prepare

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
DEST = PORT / 'build/stage11a-tracefix'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    verify()
    prior = json.loads((PORT / 'reports/stage11a-0-package.json').read_text())
    assert sha(ROOT / prior['archive']) == prior['sha256'], 'Preserved CONTROL package changed'
    DEST.mkdir(exist_ok=True)
    prior_lifetime=PORT/'baselines/stage11a-lifetime-4313d8f561bd508f.zip'
    assert sha(prior_lifetime)=='b954078614a04170ae76beee2a3fa1469c43c68b7b950185efe97bf47d41de71'
    audio=prepare(DEST/'audio')
    original_midi=ROOT/'src/bodyprog/libsd/smf_io.c'
    baseline=json.loads((PORT/'reports/stage11a-baseline.json').read_text())
    with zipfile.ZipFile(ROOT/baseline['source_snapshot']) as archive:
        midi=archive.read('3ds_port/build/audio/smf_io.c').decode()
    midi='#include "stage11a_pitch_trace.h"\n'+midi
    import re as regex
    for function,args,scope in [('control_change',r'u8 chan, u8 c1, u8 c2','1,chan,c1,c2'),('midi_vsync',r'void','2,0,0,0')]:
        pattern=r'(void '+function+r'\('+args+r'\)[^\n]*\n\{)'
        midi,count=regex.subn(pattern,lambda m:m.group(0)+'\n    SH_PITCH_SCOPE('+scope+');',midi)
        assert count==1,function
    (DEST/'smf_io.c').write_text(midi)
    flags = (PORT / 'build-game/flags').read_text().splitlines()
    engine, sdk, ld = map(shlex.split, flags[:3])
    raw = subprocess.check_output(['make', '-C', str(PORT), '-f', 'Makefile.game', '-pn'], text=True, stderr=subprocess.DEVNULL)
    objects = dict(re.findall(r'^(\w+) := (.*)$', raw, re.M))['OFILES'].split()
    original = {name: sha(Path(name)) for name in objects}
    names = ('main_game', 'game_cpu_audit', 'game_native', 'game_profile', 'game_cpu_recorder',
             'game_audio_ndsp', 'game_xa_thread', 'stage11a_perf', 'stage11a_lifetime', 'stage11a_alloc',
             'game_texture_cache', 'render_3ds', 'stage4_fs', 'game_io', 'game_spu', 'game_xa', 'game_gpu', 'stage11a_pitch_trace')
    sources = {n: PORT / 'source' / (n + ('.cpp' if n in ('game_spu', 'game_xa') else '.c')) for n in names}
    sources['smf_io']=DEST/'smf_io.c'
    sources['PsyX_SPUCore'] = audio / 'PsyX_SPUCore.cpp'
    defines = ['-DSH_STAGE11A=1', '-DSH_STAGE11A_LIFETIME=1', '-DSH_CPU_AUDIT_RECORDER=1', '-DSH_STAGE11A_SPU_DETAIL=0','-DSH_STAGE11A_TRACEFIX=1']
    provenance = dict(base_objects=original, flags=flags[:3], defines=defines, sources={})
    inputs = [*sources.values(), *sorted((PORT / 'include').glob('*.h')), audio / 'PsyX_SPUCore.h', Path(__file__), original_midi, PORT/'tools/prepare_stage11a_tracefix.py']
    digest = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode())
    for f in sorted(set(inputs)):
        name = f.relative_to(ROOT).as_posix();provenance['sources'][name] = sha(f)
        digest.update(name.encode() + b'\0' + f.read_bytes() + b'\0')
    identity = 'stage11a.0-tracefix-src-' + digest.hexdigest()[:16]
    (DEST / 'tracefix_identity.h').write_text('#define SH_BUILD_ID "' + identity + '"\n')
    main = sources['main_game'].read_text().replace('"build_identity.h"', '"tracefix_identity.h"')
    assert main.count('game_cpu_audit_init(game_prof_enabled);') == 1
    main = main.replace('game_cpu_audit_init(game_prof_enabled);', 'game_prof_enable(16);game_cpu_audit_init(game_prof_enabled);')
    (DEST / 'main_game.c').write_text(main);sources['main_game'] = DEST / 'main_game.c'
    prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
    replacements = {}
    for name, source in sources.items():
        is_cxx = source.suffix == '.cpp'
        ff = engine if name in ('game_native', 'game_profile', 'stage4_fs', 'game_io', 'game_spu', 'game_xa', 'PsyX_SPUCore', 'game_gpu', 'smf_io', 'stage11a_pitch_trace') else sdk
        if is_cxx:
            ff = [v for v in ff if not v.startswith(('-std=', '-Werror='))]
            ff += ['-std=gnu++17', '-fno-exceptions', '-fno-rtti']
        target = DEST / (name + '.o')
        compiled = subprocess.run([prefix + ('g++' if is_cxx else 'gcc'), '-I' + str(audio),
                        '-I' + str(ROOT / 'pc_port/PsyCross/src/audio'), *ff, *defines,
                        '-I' + str(DEST), '-c', str(source), '-o', str(target)], capture_output=True, text=True)
        (DEST/(name+'.compile.log')).write_text(compiled.stdout+compiled.stderr)
        if compiled.returncode:
            print('\n'.join(line for line in compiled.stderr.splitlines() if 'error:' in line),flush=True)
            compiled.check_returncode()
        replacements[str(PORT / 'build-game' / (name + '.o'))] = str(target)
    linked = [replacements.get(n, n) for n in objects]
    linked += [str(DEST / (n + '.o')) for n in ('game_cpu_recorder', 'stage11a_perf', 'stage11a_lifetime', 'stage11a_alloc', 'stage11a_pitch_trace')]
    ld = [v.replace(str(PORT / 'silenthill_game.map'), str(DEST / 'tracefix.map')) for v in ld]
    wrappers = ('malloc', 'calloc', 'realloc', 'free', 'memalign', 'linearAlloc', 'linearMemAlign', 'linearFree',
                'vramAlloc', 'vramAllocAt', 'vramMemAlign', 'vramMemAlignAt', 'vramFree')
    ld += ['-Wl,' + ','.join('--wrap=' + w for w in wrappers)]
    ctrulib = Path(next(v[2:] for v in sdk if v.startswith('-I') and v.endswith('/libctru/include'))).parent
    elf = DEST / 'silenthill_stage11a_tracefix.elf'
    subprocess.run([prefix + 'g++', *ld, *linked, '-L' + str(ctrulib / 'lib'), '-lcitro3d', '-lctru', '-lm', '-o', str(elf)], check=True)
    assert identity.encode() in elf.read_bytes()
    assert all(sha(Path(n)) == h for n, h in original.items())
    symbols = subprocess.check_output([prefix + 'nm', '-n', str(elf)], text=True)
    (DEST/'symbols.txt').write_text(symbols)
    assert not any(n in symbols for n in ('Game3ds_DevEnter', '__atomic_fetch_add_8', '__atomic_load_8'))
    assert all(sha(ROOT/name)==expected for name,expected in provenance['sources'].items()), 'Sources changed during build; relink from a stable snapshot'
    binary = DEST / 'silenthill_stage11a_tracefix.3dsx'
    subprocess.run(['3dsxtool', str(elf), str(binary), '--smdh=' + str(PORT / 'silenthill_game.smdh')], check=True)
    subprocess.run(['python3', str(PORT / 'dev_server/after_build.py'), str(binary)], check=True)
    size = subprocess.check_output([prefix + 'size', str(elf), str(PORT / 'build/hardware-stage10-cpu-recorder/silenthill_cpu_recorder.elf')], text=True)
    record = dict(build=identity, variant='STAGE11A_LIFETIME_TRACE_FIX_CANDIDATE', sha256=sha(binary),
                  size=binary.stat().st_size, elf_sha256=sha(elf), source_provenance=provenance,
                  normal_objects_unchanged=True, stage10_preserved=True, prior_control_preserved=True,
                  state_reset_added=False, midi_register_semantics_changed=False, silent_candidate_compiled=True, silent_candidate_default=0, spu_affinity=-2, spu_priority=24, block_frames=512,
                  internal_spu_sampled_profiling=False, runtime_profile_toggle=True, elf_size=size,
                  hardware_reproduction_pending=True, stage11a_accepted=False)
    (DEST / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    (PORT / 'reports/stage11a-tracefix-candidate.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: v for k, v in record.items() if k != 'source_provenance'}, indent=2))


if __name__ == '__main__':
    main()
