#!/usr/bin/env python3
"""Actual ARM overlay isolation, original handgun grant and cutscene timer."""
import json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage6_contract.o';elf=p/'build/stage6_contract.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage6_contract.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
r=game.GameRunner();r.bridge('Game3ds_Progress',lambda *_:r.ret())
data=elf.read_bytes();off=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',data,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,data[pos:pos+length])
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
game.symbols['test_stage6_contract']=next(int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3 and s[2]=='test_stage6_contract')
bits=r.call('test_stage6_contract')
report={'execution':'linked ARM11 native code; host SDK boundaries', 'failure_bits':bits,
    'overlay_data_addresses':not bool(bits&1),'private_header_and_dispatch':not bool(bits&6),
    'original_handgun_grant_and_inventory_sort':not bool(bits&24),'original_cutscene_timer':not bool(bits&32),
    'halt':r.failure}
print(json.dumps(report,indent=2));assert bits==0 and not r.failure,report
