"""Original START fallback and GameOver must have real native dispatch entries."""
import hashlib,json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0]);obj=p/'build/stage10_pause_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_pause_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
r=game.GameRunner();boot=game.run(r,seconds=120)
assert boot['first_map_state_frame'] is not None and not boot['failure'] and not boot['invalid'],boot
table=struct.unpack('<15I',r.uc.mem_read(game.symbols['g_SysStateFuncs'],60))
assert table[13]==game.symbols['SysState_GameOver_Update']
assert table[14]==game.symbols['SysState_GamePaused_Update']
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2]=='stage10_original_pause':game.symbols[s[2]]=int(s[0],16)
r.stopped=False
states=[]
for resume in (0,1):
    r.call('stage10_original_pause',resume,0x20008000)
    states.append(struct.unpack('<2I',r.uc.mem_read(0x20008000,8)))
assert states[0]==(14,1) and states[1][0]==0,states
assert not r.failure and not r.invalid
report=dict(status='PASS',scope=__doc__,original_pause_enter_resume=states,
    gameover_and_original_pause_dispatch=True,elf_sha256=hashlib.sha256(game.game_elf.read_bytes()).hexdigest())
(p/'reports/stage10-original-pause-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
