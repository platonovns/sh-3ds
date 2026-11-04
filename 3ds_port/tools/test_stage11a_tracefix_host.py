"""F0/F1 input safety and isolated host cost; no hardware speed claim."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
DEST=PORT/'build/stage11a-tracefix-host';DEST.mkdir(exist_ok=True)
source=(PORT/'tests/stage11a_lifetime_test.c').read_text()
source=source.replace('"../source/', '"'+(PORT/'source').as_posix()+'/')
source=source.replace('static unsigned fake_voices=6,audit_on=1;','''static unsigned fake_voices=6,audit_on=1,fix_mode;
unsigned game_spu_silent_fast_enabled(void){return fix_mode;}
int game_spu_silent_fast_toggle(void){fix_mode^=1;return fix_mode;}
void game_spu_pitch_trace_report(FILE *out){fprintf(out,"silent_fast_mode=%u\\n",fix_mode);}
''')
source=source.replace('chord(&c,DOWN_BIT);assert(active);','''chord(&c,LEFT_BIT);assert(fix_mode==1);
    chord(&c,DOWN_BIT);assert(active);
    chord(&c,LEFT_BIT);assert(fix_mode==1);''',1)
source=source.replace('assert(boundary[0].spu[8]==6', 'chord(&c,LEFT_BIT);assert(fix_mode==0);\n    assert(boundary[0].spu[8]==6',1)
source=source.replace('strstr(label,"P0")','strstr(label,"P0 F0")')
fixture=DEST/'input.c';fixture.write_text(source)
flags=['-std=gnu11','-O2','-g','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations',
    '-DSH_STAGE11A=1','-DSH_STAGE11A_LIFETIME=1','-DSH_STAGE11A_TRACEFIX=1','-DSH_CPU_AUDIT_RECORDER=1','-DSH_STAGE11A_SPU_DETAIL=0',
    '-I'+str(PORT/'tests/lifetime_mock'),'-I'+str(PORT/'include')]
binary=DEST/'input-test'
subprocess.run(['gcc',*flags,'-fsanitize=address,undefined',str(fixture),str(PORT/'source/game_profile.c'),str(PORT/'source/stage11a_perf.c'),'-o',str(binary)],check=True)
with tempfile.TemporaryDirectory(prefix='tracefix-input-') as tmp:
    run=subprocess.run([str(binary),tmp],capture_output=True,text=True,check=True)
    assert 'PASS' in run.stdout and not run.stderr
    for f in Path(tmp).glob('cpu_audit_*.txt'):(DEST/f.name).write_bytes(f.read_bytes())
bench=DEST/'bench.cpp';bench.write_text('''#include <chrono>
#include <cstdio>
#include <cassert>
#include "PsyX_SPUCore.h"
static unsigned mode,max_used;
extern "C" unsigned game_spu_silent_fast_enabled(void){return mode;}
extern "C" void game_spu_silent_fast_observe(uint32_t,uint32_t used,uint32_t,unsigned){unsigned n=__builtin_popcount(used);if(n>max_used)max_used=n;}
int main(){for(unsigned m: {0u,1u})for(unsigned count: {0u,3u,24u}){
 mode=m;max_used=0;PsyX::SPUCore s;
 for(unsigned i=0;i<count;i++){SpuVoiceAttr a{};a.voice=1u<<i;a.mask=SPU_VOICE_PITCH|SPU_VOICE_WDSA|SPU_VOICE_LSAX;a.pitch=4096;a.addr=a.loop_addr=0x2000;s.SetVoiceAttr(a);}
 s.SetKey(SPU_OFF,0xffffff);s.RamData()[0x2000]=4;s.RamData()[0x2001]=3;
 short pcm[1024];for(unsigned i=0;i<64;i++)s.RenderFrames(pcm,512);
 auto start=std::chrono::steady_clock::now();for(unsigned i=0;i<2048;i++)s.RenderFrames(pcm,512);
 double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/2048;
 for(auto x:pcm)assert(x==0);assert(max_used==(mode?count:0));
 printf("%u %u %.6f %u\\n",mode,count,us,max_used);
}}
''')
audio=PORT/'build/stage11a-tracefix/audio';common=ROOT/'pc_port/PsyCross/src/audio';binary=DEST/'bench'
subprocess.run(['g++','-std=c++17','-O2','-fwrapv','-ffunction-sections','-fdata-sections','-DSH_STAGE11A_TRACEFIX=1',
    '-I'+str(audio),'-I'+str(common),'-I'+str(ROOT/'pc_port/PsyCross/include'),'-I'+str(ROOT/'pc_port/PsyCross/include/psx'),
    str(audio/'PsyX_SPUCore.cpp'),str(common/'PsyX_SPUReverb.cpp'),str(bench),str(PORT/'tests/stage9_core_stubs.cpp'),'-Wl,--gc-sections','-o',str(binary)],check=True)
cost=[]
for line in subprocess.check_output([str(binary)],text=True).splitlines():
    mode,count,us,used=line.split();cost.append(dict(mode=int(mode),silent_voices=int(count),host_us_per_block=float(us),fast_used=int(used)))
result=dict(status='PASS',scope='HOST_NOT_HARDWARE',input_safety='F0/F1 release debounce, no Harry movement, in-window mode lock, P0/F0 label, bounded observer',cost=cost,
    inputs={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in
        (Path(__file__),PORT/'source/game_cpu_recorder.c',PORT/'source/stage11a_lifetime.c',PORT/'include/stage11a_pitch_trace.h',audio/'PsyX_SPUCore.cpp')})
(PORT/'reports/stage11a-tracefix-host.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
