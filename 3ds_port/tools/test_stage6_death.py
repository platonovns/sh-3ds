#!/usr/bin/env python3
"""Isolate actual ARM player death after original boot, with a test-only setup."""
import json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game

p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage6_death_probe.o';elf=p/'build/stage6_death_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage6_death_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
class DeathRunner(game.GameRunner):
    in_fixture=False
    def vblank(self,*args):
        if not self.in_fixture:return super().vblank(*args)
        self.frames+=1;self.ret(0)

r=DeathRunner();boot=game.run(r)
assert not boot['failure'] and not boot['invalid'] and not boot['exception'] and boot['first_map_state_frame'] is not None,boot
r.stopped=False;r.in_fixture=True
for handle,f in list(r.handles.items()):
    if f.closed:r.handles[handle]=open(f.name,'rb')
data=elf.read_bytes();off=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',data,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,data[pos:pos+length])
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
for line in nm.splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage6_death_'):game.symbols[s[2]]=int(s[0],16)
r.call('stage6_death_begin',bool(os.environ.get('SH_TEST_NPCS')));samples=[];previous=None;completed=False
tick_error=None
for tick in range(300):
    try:r.call('stage6_death_tick');r.call('stage6_death_snapshot',0x20008000)
    except Exception as error:tick_error=repr(error);break
    row=list(struct.unpack('<13I',r.uc.mem_read(0x20008000,52)))
    if row!=previous:samples.append({'tick':tick,'state':row});previous=row
    if row[11]:completed=True;break
overlay_loaded=None;overlay_error=None
if os.environ.get('SH_TEST_TRANSITION') and completed:
    # Boot's CPU fixture closes SDK handles when it stops. Restore those host
    # handles for this additional loader call; every retail read seeks itself.
    for handle,f in list(r.handles.items()):
        if f.closed:r.handles[handle]=open(f.name,'rb')
    try:overlay_loaded=bool(r.call('stage6_death_overlay_load'))
    except Exception as error:overlay_error=repr(error)
report={'execution':'linked ARM player update after original boot; test-only death entry',
        'normal_route_acceptance':False,'death_completed':completed,'ticks':tick+1,
        'fields':['state','body_anim','upper_anim','body_frame','upper_frame','body_flags','upper_flags',
                  'body_ctrl','upper_ctrl','body_step','upper_step','flag25','health'],
        'samples':samples,'halt':r.failure,'tick_error':tick_error,
        'with_npcs':bool(os.environ.get('SH_TEST_NPCS')),'overlay_loaded':overlay_loaded,'overlay_error':overlay_error,
        'loader_events':r.events}
print(json.dumps(report,indent=2))
assert completed and not r.failure,'Death animation did not complete the original flag25 transition'
if os.environ.get('SH_TEST_TRANSITION'):assert overlay_loaded and not overlay_error,overlay_error
