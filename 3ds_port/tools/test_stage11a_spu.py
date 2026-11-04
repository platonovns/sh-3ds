"""Host-only byte-for-byte SPU oracle and bounded concurrent recorder validation."""
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from prepare_stage11a_spu import prepare

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
AUDIO = ROOT / 'pc_port/PsyCross/src/audio'
DEST = PORT / 'build/stage11a-tests'
DEST.mkdir(exist_ok=True)
candidate = prepare(DEST / 'candidate')
reference = DEST / 'reference'
reference.mkdir(exist_ok=True)
baseline = json.loads((PORT / 'reports/stage11a-baseline.json').read_text())
with zipfile.ZipFile(ROOT / baseline['source_snapshot']) as archive:
    for name in ('PsyX_SPUCore.h', 'PsyX_SPUCore.cpp'):
        (reference / name).write_bytes(archive.read('3ds_port/build/audio/' + name))
    for name in ('PsyX_SPUReverb.h', 'PsyX_SPUReverb.cpp'):
        (reference / name).write_bytes(archive.read('pc_port/PsyCross/src/audio/' + name))
flags = ['-std=c++17', '-O2', '-g', '-fwrapv', '-ffunction-sections', '-fdata-sections', '-fsanitize=address',
         '-I' + str(PORT / 'include'), '-I' + str(AUDIO),
         '-I' + str(ROOT / 'pc_port/PsyCross/include'), '-I' + str(ROOT / 'pc_port/PsyCross/include/psx')]
results = {}
with tempfile.TemporaryDirectory(prefix='stage11a-oracle-') as directory:
    original = None
    for name, source, detail in [('frozen', reference, 0), ('timing', candidate, 0), ('profile', candidate, 1)]:
        binary = DEST / ('oracle-' + name)
        reverb = reference if name == 'frozen' else AUDIO
        command = ['g++', '-I' + str(source), *flags, '-DSH_STAGE11A_SPU_DETAIL=' + str(detail),
                   str(source / 'PsyX_SPUCore.cpp'), str(reverb / 'PsyX_SPUReverb.cpp'),
                   str(PORT / 'tests/stage11a_spu_oracle.cpp'), str(PORT / 'tests/stage9_core_stubs.cpp'),
                   '-Wl,--gc-sections', '-o', str(binary)]
        subprocess.run(command, check=True)
        output = Path(directory) / name
        with output.open('wb') as stream:
            subprocess.run([str(binary)], stdout=stream, check=True)
        with output.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if original is None:
            original = output
        else:
            with original.open('rb') as before, output.open('rb') as after:
                offset = 0
                while True:
                    a, b = before.read(65536), after.read(65536)
                    assert a == b, f'PCM/internal state mismatch in {name} at chunk {offset}'
                    if not a:
                        break
                    offset += len(a)
        results[name] = dict(bytes=output.stat().st_size, sha256=digest, byte_exact=True)
    metric = DEST / 'perf-test'
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-DSH_STAGE11A_SPU_DETAIL=1',
                    '-I' + str(PORT / 'include'), str(PORT / 'tests/stage11a_perf_test.c'),
                    '-pthread', '-o', str(metric)], check=True)
    run = subprocess.run([str(metric)], text=True, capture_output=True, check=True)
    assert 'PASS' in run.stdout and not run.stderr, (run.stdout, run.stderr)
    recorder = DEST / 'recorder-test'
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-DSH_STAGE11A=1', '-DSH_STAGE11A_SPU_DETAIL=1',
                    '-DSH_CPU_AUDIT_RECORDER=1', '-I' + str(PORT / 'include'),
                    str(PORT / 'tests/stage11a_recorder_test.c'), str(PORT / 'source/game_profile.c'),
                    str(PORT / 'source/stage11a_perf.c'), '-o', str(recorder)], check=True)
    recorded = subprocess.run([str(recorder), directory], capture_output=True, text=True, check=True)
    assert 'PASS' in recorded.stdout and not recorded.stderr, (recorded.stdout, recorded.stderr)
result = dict(status='PASS', scope='HOST_NOT_HARDWARE', checkpoints=256, comparisons=results,
              coverage=['PCM', 'split taps', 'all voice/register fields', 'ADPCM history', 'ADSR',
                        'pitch', 'sweep', 'PMON', 'noise', 'ENDX', 'entire SPU RAM',
                        'reverb registers and FIR history', 'CD queue', 'transfer and allocator state'],
              metrics=run.stdout.strip(), recorder=recorded.stdout.strip(), hardware_audio_listening_pending=True,
              performance_improvement_claimed=False)
result['inputs'] = {f.relative_to(ROOT).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                    for f in (PORT / 'tests/stage11a_spu_oracle.cpp', PORT / 'tests/stage11a_perf_test.c',
                              PORT / 'source/stage11a_perf.c', PORT / 'source/game_cpu_recorder.c',
                              PORT / 'source/game_profile.c', candidate / 'PsyX_SPUCore.cpp',
                              AUDIO / 'PsyX_SPUReverb.cpp', Path(__file__))}
(PORT / 'reports/stage11a-spu-oracle.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
