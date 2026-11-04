"""Frozen vs F0/F1 canonical PCM/state, plus targeted stationary/future-KeyOn cases."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from prepare_stage11a_cpu import prepare
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
DEST=PORT/'build/stage11a-cpu-tests';DEST.mkdir(exist_ok=True)
audio=ROOT/'pc_port/PsyCross/src/audio';candidate=prepare(PORT/'build/stage11a-cpu/audio')
reference=DEST/'reference';reference.mkdir(exist_ok=True)
baseline=json.loads((PORT/'reports/stage11a-baseline.json').read_text())
with zipfile.ZipFile(ROOT/baseline['source_snapshot']) as z:
    for n in ('PsyX_SPUCore.h','PsyX_SPUCore.cpp'):(reference/n).write_bytes(z.read('3ds_port/build/audio/'+n))
    for n in ('PsyX_SPUReverb.cpp','PsyX_SPUReverb.h'):(reference/n).write_bytes(z.read('pc_port/PsyCross/src/audio/'+n))
callbacks=DEST/'callbacks.cpp';callbacks.write_text('''#include <stdint.h>
#include <cstdio>
static uint64_t calls,used_frames,grouped_frames;
extern "C" unsigned game_spu_silent_fast_enabled(void){return FIX_MODE;}
extern "C" void game_spu_silent_fast_observe(uint32_t,uint32_t used,uint32_t grouped,unsigned frames){
 calls++;used_frames+=(uint64_t)__builtin_popcount(used)*frames;grouped_frames+=(uint64_t)__builtin_popcount(grouped)*frames;}
struct Stats{~Stats(){std::fprintf(stderr,"%llu,%llu,%llu\\n",(unsigned long long)calls,(unsigned long long)used_frames,(unsigned long long)grouped_frames);}}stats;
''')
original=(PORT/'tests/stage11a_spu_oracle.cpp').read_text()
# Reuse the complete canonical field serializer; do not serialize candidate-only
# observer counters as native SPU state. New cases explicitly reach the fast path.
targeted=original.split('int main()')[0]+(PORT/'tests/stage11a_tracefix_targeted.inc').read_text()
target_file=DEST/'targeted.cpp';target_file.write_text(targeted)
flags=['-std=c++17','-O2','-g','-fwrapv','-ffunction-sections','-fdata-sections','-fsanitize=address',
       '-I'+str(PORT/'include'),'-I'+str(audio),'-I'+str(ROOT/'pc_port/PsyCross/include'),'-I'+str(ROOT/'pc_port/PsyCross/include/psx')]
results={}
with tempfile.TemporaryDirectory(prefix='tracefix-oracle-') as tmp:
    for fixture in (PORT/'tests/stage11a_spu_oracle.cpp',target_file):
        series={};expected=None
        for label,src,mode in [('frozen',reference,0),('F0',candidate,0),('F1',candidate,1)]:
            binary=DEST/(fixture.stem+'-'+label)
            command=['g++','-I'+str(src),*flags,'-DSH_STAGE11A_TRACEFIX=1','-DFIX_MODE='+str(mode),
                str(src/'PsyX_SPUCore.cpp'),str(reference/'PsyX_SPUReverb.cpp'),str(fixture),str(callbacks),
                str(PORT/'tests/stage9_core_stubs.cpp'),'-Wl,--gc-sections','-o',str(binary)]
            subprocess.run(command,check=True)
            output=Path(tmp)/(fixture.stem+'-'+label)
            with output.open('wb') as f:run=subprocess.run([str(binary)],stdout=f,stderr=subprocess.PIPE,text=True,check=True)
            observed=list(map(int,run.stderr.strip().split(',')))
            if label=='F0':assert observed[1:]==[0,0]
            if label=='F1' and fixture==target_file:assert observed[1]>0 and observed[2]>0
            with output.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if expected is None:expected=(digest,output.stat().st_size)
            assert (digest,output.stat().st_size)==expected,(fixture,label,digest,expected)
            series[label]=dict(bytes=output.stat().st_size,sha256=digest,byte_exact=True,observer_calls_used_grouped_frames=observed)
        results[fixture.stem]=series
result=dict(status='PASS',scope='HOST_PCM_AND_STATE_NOT_HARDWARE',comparisons=results,
    targeted_cases='stationary release/off, RR boundaries, PMON/noise/sweeps, reverb RAM overlap, End+Mute, pitch clipping, split/null output, RAM writes, future KeyOn and volume/ADSR changes',
    inputs={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in
        (candidate/'PsyX_SPUCore.cpp',candidate/'PsyX_SPUCore.h',Path(__file__),PORT/'tools/prepare_stage11a_cpu.py',PORT/'tools/prepare_stage11a_tracefix.py',PORT/'tests/stage11a_tracefix_targeted.inc',PORT/'tests/stage11a_spu_oracle.cpp')})
(PORT/'reports/stage11a-cpu-pcm.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
