"""Exercise blood spawn/update/OT on the nearby compiled Cafe debug state."""
import json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage8_combat_probe.o';elf=p/'build/stage8_combat_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage8_combat_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
r=game.GameRunner();boot=game.run(r,seconds=90)
assert boot['first_map_state_frame'] is not None and not boot['failure'] and not boot['invalid'],boot
for handle,f in list(r.handles.items()):
    if f.closed:r.handles[handle]=open(f.name,'rb')
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage8_'):game.symbols[s[2]]=int(s[0],16)
error=None;ticks=0
try:
    r.call('stage8_blood_begin')
    for tick in range(120):r.call('stage8_blood_tick');ticks+=1
except Exception as e:error=repr(e)
report=dict(execution='actual ARM Cafe initialization, real blood spawn/update/OT; test-only contact',
    elf=str(game.game_elf),ticks=ticks,halt=r.failure,invalid=r.invalid,error=error,draws=r.draw_count)
print(json.dumps(report,indent=2))
(p/'reports/stage8-blood-arm.json').write_text(json.dumps(report,indent=2)+'\n')
assert ticks==120 and not r.failure and not r.invalid and not error,report
