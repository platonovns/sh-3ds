"""Host sanitizer observer/input tests and isolated frozen-SPU accumulation lead."""
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
DEST = PORT / 'build/stage11a-lifetime-tests'
DEST.mkdir(exist_ok=True)
flags = ['-std=gnu11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations',
         '-DSH_STAGE11A=1', '-DSH_STAGE11A_LIFETIME=1', '-DSH_CPU_AUDIT_RECORDER=1', '-DSH_STAGE11A_SPU_DETAIL=0',
         '-I'+str(PORT/'tests/lifetime_mock'), '-I'+str(PORT/'include')]
binary = DEST / 'observer-test'
subprocess.run(['gcc', *flags, '-fsanitize=address,undefined', str(PORT/'tests/stage11a_lifetime_test.c'),
                str(PORT/'source/game_profile.c'), str(PORT/'source/stage11a_perf.c'), '-o', str(binary)], check=True)
with tempfile.TemporaryDirectory(prefix='lifetime-test-') as directory:
    run = subprocess.run([str(binary), directory], capture_output=True, text=True, check=True)
    assert not run.stderr and 'PASS' in run.stdout, run
    for f in Path(directory).glob('cpu_audit_*.txt'):
        (DEST/f.name).write_bytes(f.read_bytes())
baseline = json.loads((PORT/'reports/stage11a-baseline.json').read_text())
with zipfile.ZipFile(ROOT/baseline['source_snapshot']) as archive:
    for name in ('PsyX_SPUCore.cpp', 'PsyX_SPUCore.h'):
        (DEST/name).write_bytes(archive.read('3ds_port/build/audio/'+name))
audio = ROOT/'pc_port/PsyCross/src/audio'
bench = DEST/'spu-cost'
subprocess.run(['g++', '-std=c++17', '-O2', '-fwrapv', '-ffunction-sections', '-fdata-sections',
    '-I'+str(DEST), '-I'+str(audio), '-I'+str(ROOT/'pc_port/PsyCross/include'),
    '-I'+str(ROOT/'pc_port/PsyCross/include/psx'), str(DEST/'PsyX_SPUCore.cpp'), str(audio/'PsyX_SPUReverb.cpp'),
    str(PORT/'tests/stage11a_lifetime_spu_cost.cpp'), str(PORT/'tests/stage9_core_stubs.cpp'),
    '-Wl,--gc-sections', '-o', str(bench)], check=True)
cost = subprocess.check_output([str(bench)], text=True)
rows=[]
for line in cost.splitlines():
    n,us,nz,before,after,size=line.split()
    rows.append(dict(silent_nonzero_pitch_voices=int(n),host_us_per_512_block=float(us),
                     pcm_nonzero=int(nz),first_decoder_pos_before=int(before),first_decoder_pos_after=int(after),spu_object_bytes=int(size)))
assert len(rows)==4 and len(set(r['spu_object_bytes'] for r in rows))==1
result=dict(status='PASS',scope='HOST_SYNTHETIC_NOT_HARDWARE',observer=run.stdout.strip(),frozen_spu_cost=rows,
    finding='Silent nonzero-pitch voices continue decoder work in frozen Stage 10; this lead requires hardware correlation. No optimization adopted.',
    hardware_reproduction_pending=True)
result['inputs']={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in
    (PORT/'source/stage11a_lifetime.c', PORT/'source/game_profile.c', PORT/'source/game_cpu_recorder.c',
     PORT/'tests/stage11a_lifetime_test.c', PORT/'tests/stage11a_lifetime_spu_cost.cpp')}
(PORT/'reports/stage11a-lifetime-host.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
