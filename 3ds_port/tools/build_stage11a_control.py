"""Private Stage 11A CONTROL build. Frozen Stage 10 binaries/objects stay intact."""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from prepare_stage11a_spu import prepare
from stage11a_baseline import verify

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detail', type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    verify()
    dest = PORT / ('build/stage11a-control-' + ('profile' if args.detail else 'timing'))
    dest.mkdir(exist_ok=True)
    audio = prepare(dest / 'audio')
    base = PORT / 'silenthill_game.elf'
    assert sha(base) == '8c41fc2a3281f71bb3583b058c7d56ce2e3e6ae59667c4a217262b96807cd981'
    flags = (PORT / 'build-game/flags').read_text().splitlines()
    engine, sdk, ld = map(shlex.split, flags[:3])
    raw = subprocess.check_output(['make', '-C', str(PORT), '-f', 'Makefile.game', '-pn'],
                                  text=True, stderr=subprocess.DEVNULL)
    objects = dict(re.findall(r'^(\w+) := (.*)$', raw, re.M))['OFILES'].split()
    original = {name: sha(Path(name)) for name in objects}
    sources = {name: PORT / 'source' / (name + '.c') for name in
               ('main_game', 'game_cpu_audit', 'game_native', 'game_profile',
                'game_cpu_recorder', 'game_audio_ndsp', 'stage11a_perf')}
    sources['PsyX_SPUCore'] = audio / 'PsyX_SPUCore.cpp'
    extra = ['-DSH_STAGE11A=1', '-DSH_CPU_AUDIT_RECORDER=1',
             '-DSH_STAGE11A_SPU_DETAIL=' + str(args.detail), '-I' + str(dest)]
    provenance = dict(base_elf_sha256=sha(base), base_objects=original,
                      flags=flags[:3], defines=extra[:3], sources={})
    inputs = [*sources.values(), *sorted((PORT / 'include').glob('*.h')),
              audio / 'PsyX_SPUCore.h', Path(__file__), PORT / 'tools/prepare_stage11a_spu.py']
    digest = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode())
    for path in sorted(set(inputs)):
        name = path.relative_to(ROOT).as_posix()
        provenance['sources'][name] = sha(path)
        digest.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    identity = 'stage11a.0-control-' + ('profile' if args.detail else 'timing') + '-src-' + digest.hexdigest()[:16]
    (dest / 'stage11a_identity.h').write_text('#define SH_BUILD_ID "' + identity + '"\n')
    main = sources['main_game'].read_text().replace('"build_identity.h"', '"stage11a_identity.h"')
    needle = 'game_cpu_audit_init(game_prof_enabled);'
    assert main.count(needle) == 1
    main = main.replace(needle, 'game_prof_enable(16);' + needle)
    (dest / 'main_game.c').write_text(main)
    sources['main_game'] = dest / 'main_game.c'
    prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
    replacements = {}
    for name, source in sources.items():
        ff = engine if name in ('game_native', 'game_profile', 'PsyX_SPUCore') else sdk
        compiler = 'g++' if name == 'PsyX_SPUCore' else 'gcc'
        if name == 'PsyX_SPUCore':
            ff = [v for v in ff if not v.startswith('-std=') and not v.startswith('-Werror=')]
            ff += ['-std=gnu++17', '-fno-exceptions', '-fno-rtti', '-I' + str(audio),
                   '-I' + str(ROOT / 'pc_port/PsyCross/src/audio')]
        target = dest / (name + '.o')
        subprocess.run([prefix + compiler, *ff, *extra, '-c', str(source), '-o', str(target)], check=True)
        replacements[str(PORT / 'build-game' / (name + '.o'))] = str(target)
    linked = [replacements.get(n, n) for n in objects]
    linked += [str(dest / (n + '.o')) for n in ('game_cpu_recorder', 'stage11a_perf')]
    ld = [v.replace(str(PORT / 'silenthill_game.map'), str(dest / 'control.map')) for v in ld]
    ctrulib = Path(next(v[2:] for v in sdk if v.startswith('-I') and v.endswith('/libctru/include'))).parent
    elf = dest / 'silenthill_stage11a_control.elf'
    subprocess.run([prefix + 'g++', *ld, *linked, '-L' + str(ctrulib / 'lib'),
                    '-lcitro3d', '-lctru', '-lm', '-o', str(elf)], check=True)
    assert identity.encode() in elf.read_bytes()
    assert all(sha(Path(n)) == h for n, h in original.items()), 'Normal objects changed'
    symbols = subprocess.check_output([prefix + 'nm', '-n', str(elf)], text=True)
    assert not any(n in symbols for n in ('Game3ds_DevEnter', 'Game3ds_DevCafePad', '__atomic_load_8', '__atomic_fetch_add_8'))
    binary = dest / 'silenthill_stage11a_control.3dsx'
    subprocess.run(['3dsxtool', str(elf), str(binary), '--smdh=' + str(PORT / 'silenthill_game.smdh')], check=True)
    # Every successful hardware game build must immediately be delivered.
    subprocess.run(['python3', str(PORT / 'dev_server/after_build.py'), str(binary)], check=True)
    size = subprocess.check_output([prefix + 'size', str(elf), str(base),
        str(PORT / 'build/hardware-stage10-cpu-recorder/silenthill_cpu_recorder.elf')], text=True)
    result = dict(build=identity, variant='STAGE11A_CONTROL_INSTRUMENTED',
                  spu_detail=args.detail, optimizations=0, requested_spu_core=-2,
                  block_frames=512, priority=0x18, automatic_scene_start=False,
                  size=binary.stat().st_size, sha256=sha(binary), elf_sha256=sha(elf),
                  normal_objects_unchanged=True, normal_elf_sha256=sha(base),
                  hardware_accepted=False, hardware_measurements_pending=True,
                  elf_size_comparison=size, provenance=provenance)
    (dest / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    (PORT / ('reports/stage11a-control-' + ('profile' if args.detail else 'timing') + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'provenance'}, indent=2))


if __name__ == '__main__':
    main()
