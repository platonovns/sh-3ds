"""CPU texture/cache exactness, original R5/R6 decode/readback oracles, sanitizers."""
import hashlib,json,subprocess
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
DEST=PORT/'build/stage11a-cpu-host';DEST.mkdir(exist_ok=True)
cases=[]
for name,sources in [
 ('tiles',['tests/stage11a_cpu_tiles_test.c','source/game_texture_cache.c','source/game_texture_decode.c']),
 ('full_decode',['tests/stage10_r6_decode_test.c','source/game_texture_decode.c']),
 ('readback',['tests/stage10_r6_readback_test.c']),
 ('feedback',['tests/stage10_feedback_test.c']),
 ('culling',['tests/stage10_culling_test.c']),
 ('controls',['tests/stage10_modern_controls_test.c']),
 ('cadence',['tests/stage10_cadence_test.c'])]:
 exe=DEST/name
 subprocess.run(['gcc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
  '-I'+str(PORT/'include'),*[str(PORT/s) for s in sources],'-lm','-o',str(exe)],check=True)
 run=subprocess.run([str(exe)],capture_output=True,text=True,check=True);assert 'PASS' in run.stdout and not run.stderr,run
 cases.append(dict(name=name,result=run.stdout.strip()))
result=dict(status='PASS',scope=__doc__,cases=cases,inputs={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
 for f in [Path(__file__),PORT/'tests/stage11a_cpu_tiles_test.c',PORT/'source/game_texture_cache.c',PORT/'source/game_texture_decode.c']})
(PORT/'reports/stage11a-cpu-host.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
