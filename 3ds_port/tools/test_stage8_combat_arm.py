"""Run actual hit registration on every NPC slot, including frozen Stage 7."""
import json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage8_combat_probe.o';elf=p/'build/stage8_combat_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage8_combat_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage8_'):game.symbols[s[2]]=int(s[0],16)
r=game.GameRunner()
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
# Isolate hit bookkeeping from blood-particle resource allocation.
r.bridge('func_8005F6B0',lambda *_:r.ret())
indices=[]
for i in range(6):indices.append(r.call('stage8_hit_index',i))
r.call('stage8_hit_twice',0x20008000)
damage=list(struct.unpack('<2I',r.uc.mem_read(0x20008000,8)))
report=dict(execution='actual ARM func_8008B714; particle emission isolated',
    elf=str(game.game_elf),indices=indices,expected=list(range(6)),
    player_work_bytes=r.call('stage8_combat_layout',0),npc_offset=r.call('stage8_combat_layout',1),
    damage_after_first_and_repeated_hit=damage,
    passed=indices==list(range(6)) and damage[0]>0 and damage[0]==damage[1],failure=r.failure,invalid=r.invalid)
print(json.dumps(report,indent=2))
(p/'reports'/('stage8-combat-baseline.json' if os.environ.get('SH_EXPECT_BASELINE_FAILURE') else 'stage8-combat-arm.json')).write_text(json.dumps(report,indent=2)+'\n')
if not os.environ.get('SH_EXPECT_BASELINE_FAILURE'):assert report['passed'] and not r.failure and not r.invalid
