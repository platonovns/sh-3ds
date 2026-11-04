"""Compile integration objects only: no 3DSX, promotion or server changes."""
import hashlib,json,os,shlex,shutil,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'3ds_port';ORIG=R.parent/'silent-hill-decomp'
B=P/'build/fmv-arm';B.mkdir(parents=True,exist_ok=True)
sdkroot=R.parent/'.toolchain/rootfs/opt/devkitpro'
gcc=sdkroot/'devkitARM/bin/arm-none-eabi-gcc'
deps=P/'build/fmv-deps/psycross'
if not deps.exists():
    for name in ['include','src']:
        shutil.copytree(ORIG/'pc_port/PsyCross'/name,deps/name)
captured=json.loads((P/'fmv/compile-flags.json').read_text())
engine,sdk=[shlex.split(captured[x].replace('{ROOT}',str(R)).replace('{SDK}',str(sdkroot)).replace(str(R/'pc_port/PsyCross'),str(deps))) for x in ('engine','sdk')]
common=['-I'+str(deps/'include/psx'),'-I'+str(deps/'include'),'-DSH_3DS_FMV=1','-DSH_STAGE11A=1','-DSH_STAGE11A_LIFETIME=1','-DSH_STAGE11A_CPU=1','-DSH_CPU_AUDIT_RECORDER=1','-DSH_STAGE11A_SPU_CORE=2']
sources={n:P/'source'/f'{n}.c' for n in ['game_fmv','fmv_mdec','fmv_stream','main_game','game_audio_ndsp','psx_disc']}
sources['stream']=R/'src/screens/stream/stream.c'
result={}
for n,src in sources.items():
    target=B/(n+'.o');ff=engine if n=='stream' else sdk
    cmd=[str(gcc),*ff,*common,'-Wno-unused-const-variable','-c',str(src),'-o',str(target)]
    r=subprocess.run(cmd,capture_output=True,text=True,cwd=P)
    (B/(n+'.log')).write_text(r.stdout+r.stderr)
    if r.returncode:print(r.stdout+r.stderr,flush=True);r.check_returncode()
    result[n]=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),object_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),flags=ff+common)
target=B/'main_game_dev.o'
r=subprocess.run([str(gcc),*sdk,*common,'-DSH_FMV_DEV_MOVIE=2056','-c',str(sources['main_game']),'-o',str(target)],capture_output=True,text=True,cwd=P)
if r.returncode:print(r.stdout+r.stderr);r.check_returncode()
# Read the compiler's actual 32-bit ABI allocation budget from its data section.
dump=B/'memory.bin'
subprocess.run([str(sdkroot/'devkitARM/bin/arm-none-eabi-objcopy'),'-O','binary','--only-section=.rodata.game_fmv_memory_budget',str(B/'game_fmv.o'),str(dump)],check=True)
import struct
result['memory_budget']=dict(zip(('movie_heap','linear_pcm','disc_cache','worker_stack','video_slots','rgb_frame_bytes'),struct.unpack('<6I',dump.read_bytes())))
(P/'reports/fmv-arm-compile.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: ARM11 integration objects; no game binary produced')
