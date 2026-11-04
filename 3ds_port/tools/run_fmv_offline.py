"""Run on Linux/WSL. Only host binaries and metadata reports are created."""
import json, platform, subprocess, sys, time
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'3ds_port';B=P/'build/fmv-offline'
B.mkdir(parents=True,exist_ok=True)
def run(cmd):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True)
    if p.returncode: print(p.stdout+p.stderr,flush=True);p.check_returncode()
    return p.stdout
flags=['-O2','-g','-I'+str(P/'include')]
run(['gcc',*flags,'-Dmdec_init=oracle_init','-Dmdec_decode_frame=oracle_decode','-c',R/'pc_port/src/fmv/mdec.c','-o',B/'oracle.o'])
pc=(R/'pc_port/src/fmv/fmv_player.cpp').read_text()
xa=pc[pc.index('static const int16_t s_fmvXaFilterPos'):pc.index('/* FMV *movie* volume')]
xa=xa.replace('static int FmvDecodeXaSector','int oracle_xa_decode')
(B/'oracle_xa.c').write_text('#include <stdint.h>\n#include <string.h>\ntypedef uint32_t SDL_AudioDeviceID;\n'+xa+'\nvoid oracle_xa_reset(void){memset(&s_fmvAudio,0,sizeof(s_fmvAudio));}\n')
sources=[P/'source'/f for f in ['fmv_mdec.c','fmv_stream.c','psx_disc.c','sh_disc.c']]
sources+=[P/'build/audio/xa_decode.c',P/'tests/fmv_offline.c',B/'oracle.o',B/'oracle_xa.c']
run(['gcc',*flags,'-fsanitize=address,undefined','-fno-sanitize-recover=all',*sources,'-o',B/'fmv_offline'])
disc=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else R.parent/'silent-hill-decomp/sh1_data/sh1.bin'
start=time.monotonic()
result=run([B/'fmv_offline',disc,disc.with_suffix('.cue')])
out=P/'reports/fmv-offline.txt';out.parent.mkdir(exist_ok=True);out.write_text(result)
(P/'reports/fmv-host.json').write_text(json.dumps(dict(platform=platform.platform(),compiler=run(['gcc','--version']).splitlines()[0],elapsed=time.monotonic()-start),indent=2)+'\n')
print(result)
# Production lifecycle adapter behind a deterministic, threaded SDK boundary.
fake=P/'tests/fmv_fake'
run(['gcc',*flags,'-I'+str(fake),'-fsanitize=address,undefined','-fno-sanitize-recover=all','-pthread',
    *sources[:4],P/'build/audio/xa_decode.c',P/'tests/fmv_lifecycle.c',
    '-Wl,--wrap=PsxDisc_ReadRawSector','-o',B/'fmv_lifecycle'])
sd=B/'sdmc:/3ds/silenthill';sd.mkdir(parents=True,exist_ok=True)
for name,target in [('sh1.bin',disc),('sh1.cue',disc.with_suffix('.cue'))]:
    link=sd/name
    if not link.exists():link.symlink_to(target)
results=[]
for scenario in range(13):
    p=subprocess.run([str(B/'fmv_lifecycle'),str(scenario)],capture_output=True,text=True,cwd=B)
    if p.returncode:print(p.stdout+p.stderr,flush=True);p.check_returncode()
    results.append(p.stdout.strip());print(p.stdout.strip(),flush=True)
    if scenario==11:
        state=dict(line.split('=',1) for line in (sd/'fmv_last.txt').read_text().splitlines())
        assert int(state['dropped'])>0,state
    if scenario==12:
        state=dict(line.split('=',1) for line in (sd/'fmv_last.txt').read_text().splitlines())
        assert int(state['underflows'])>0 and int(state['clock_samples'])==112*2520,state
(P/'reports/fmv-lifecycle.txt').write_text('\n'.join(results)+'\n')
# Optimized host build without sanitizers; timing excludes demux and oracle checks.
run(['gcc',*flags,*sources[:5],P/'tests/fmv_bench.c',B/'oracle.o','-o',B/'fmv_bench'])
bench=run([B/'fmv_bench',disc,disc.with_suffix('.cue')])
(P/'reports/fmv-throughput.txt').write_text(bench);print(bench)
