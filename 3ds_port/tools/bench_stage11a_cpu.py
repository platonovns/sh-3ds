import hashlib,json,subprocess,os
from pathlib import Path
from prepare_stage11a_cpu import prepare
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
DEST=PORT/'build/stage11a-cpu-bench';DEST.mkdir(exist_ok=True)
allowed=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{allowed[-1]})
candidate=prepare(PORT/'build/stage11a-cpu/audio')
common=ROOT/'pc_port/PsyCross/src/audio'
result={};checks=[]
for name,audio in [('F1',PORT/'build/stage11a-tracefix/audio'),('CPU',candidate)]:
 binary=DEST/name
 subprocess.run(['g++','-std=c++17','-O2','-fwrapv','-ffunction-sections','-fdata-sections','-DSH_STAGE11A_TRACEFIX=1',
  '-I'+str(audio),'-I'+str(common),'-I'+str(ROOT/'pc_port/PsyCross/include'),'-I'+str(ROOT/'pc_port/PsyCross/include/psx'),
  str(audio/'PsyX_SPUCore.cpp'),str(common/'PsyX_SPUReverb.cpp'),str(PORT/'tests/stage11a_cpu_bench.cpp'),
  str(PORT/'tests/stage9_core_stubs.cpp'),'-Wl,--gc-sections','-o',str(binary)],check=True)
 run=subprocess.run([str(binary)],capture_output=True,text=True,check=True);checks.append(run.stderr)
 result[name]=[dict(workload=['idle24','sfx4','music_like12','xa_sfx4','reverb4','future_keyon'][int(a)],
  median_us=float(b),min_us=float(c),max_us=float(d)) for a,b,c,d in map(str.split,run.stdout.splitlines())]
assert checks[0]==checks[1],checks
record=dict(scope='HOST_SYNTHETIC_NOT_HARDWARE_NOT_RETAIL_MUSIC',host_affinity=[allowed[-1]],repeats=7,measured_blocks_per_trial=480,frames_per_block=512,
 results=result,checksums=checks,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
  for p in [Path(__file__),PORT/'tests/stage11a_cpu_bench.cpp',candidate/'PsyX_SPUCore.cpp']})
(PORT/'reports/stage11a-cpu-spu-bench.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
