#!/usr/bin/env python3
"""Check zero-flex preservation, cutscene isolation and nonzero composition."""
import contextlib,io,json,os,shlex,struct,subprocess,sys
from pathlib import Path
with contextlib.redirect_stdout(io.StringIO()):
    import test_game_gpu_arm as gpu
port=gpu.port
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((port/'build-game/flags').read_text().splitlines()[0])
obj=port/'build/pose_flex_probe.o'; elf=port/'build/pose_flex_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(port/'tests/pose_flex_probe.c'),'-o',str(obj)],check=True,stdout=subprocess.DEVNULL)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(port/'silenthill_game.elf'),str(obj),'-o',str(elf)],check=True,stdout=subprocess.DEVNULL)
probe=elf.read_bytes(); machine=gpu.Machine()
phoff=struct.unpack_from('<I',probe,28)[0]; size,count=struct.unpack_from('<HH',probe,42)
for i in range(count):
    typ,offset,addr,_,length,_,_,_=struct.unpack_from('<8I',probe,phoff+i*size)
    if typ==1 and length: machine.uc.mem_write(addr,probe[offset:offset+length])
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
gpu.symbols['test_pose_flex']=next(int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3 and s[2]=='test_pose_flex')
bits=machine.call('test_pose_flex')
report={'execution':'actual linked ARM func_8007D090 and matrix/GTE code',
        'zero_flex_preserves_animated_arms':not bool(bits&1),'cutscene_path_unchanged':not bool(bits&2),
        'nonzero_flex_composes_rotation':not bool(bits&4),'failure_bits':bits}
print(json.dumps(report,indent=2))
if '--expect-broken' in sys.argv: assert bits&1
else: assert bits==0,report
