"""Normal quick boot must hold at Title without synthetic New Game input."""
import json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
class TitleRunner(game.GameRunner):
    def read_pad(self,*_):self.ret(0)
    def vblank(self,*_):
        self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0
        if self.title_age>=3 or self.frames>4000:self.stopped=True;self.uc.emu_stop()
        self.ret(0)
r=TitleRunner();report=game.run(r,seconds=90)
assert r.state==7 and r.title_age>=3 and r.scene_frame is None
assert not report['failure'] and not report['invalid'] and not report['exception'],report
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0]);obj=p/'build/stage8_title_probe.o';elf=p/'build/stage8_title_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage8_gpu_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2]=='stage8_title_idle_probe':game.symbols[s[2]]=int(s[0],16)
result=r.call('stage8_title_idle_probe');assert result==7 and not r.failure
report.update(idle_title_counter_fixture=2400,component_timer_injection=True,title_after_idle_threshold=result)
print(json.dumps(report,indent=2))
