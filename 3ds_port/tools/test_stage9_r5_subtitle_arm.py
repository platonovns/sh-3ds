"""Actual native subtitle gate: loading, ready, playing and fail-open."""
from pathlib import Path
import subprocess,shlex,os,struct,json,hashlib
from unicorn.arm_const import UC_ARM_REG_R0
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
ns={'__file__':str(fixture),'__name__':'subtitle_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
m=ns['Machine']();p=ns['port'];symbols=ns['symbols']
game_elf=Path(os.environ.get('SH_GAME_ELF',str(p/'silenthill_game.elf')))
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage9_r5_subtitle_probe.o';elf=p/'build/stage9_r5_subtitle_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage9_r5_subtitle_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0x900000,--just-symbols='+str(game_elf),str(obj),'-o',str(elf)],check=True)
m.uc.mem_map(0x900000,0x10000)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    v=line.split()
    if len(v)==3 and v[2].startswith('stage9_r5_message_'):symbols[v[2]]=int(v[0],16)
state=[2];pending=[1];ready=[0];draws=[]
def ret(v=0):m.uc.reg_write(UC_ARM_REG_R0,v);m.ret()
m.hook('Sd_AudioStreamingCheck',lambda *_:ret(state[0]))
m.hook('game_audio_xa_pending',lambda *_:ret(pending[0]))
m.hook('game_xa_ready',lambda *_:ret(ready[0]))
for name in ('func_8004C564','Gfx_MapMsg_DefaultStringInfoSet','Gfx_MapMsg_CalculateWidths',
             'Gfx_StringSetColor','Gfx_StringSetPosition'):
    m.hook(name,lambda *_:ret())
m.hook('Gfx_MapMsg_SelectionUpdate',lambda *_:(draws.append(1),ret(0)))
cases=[]
for idx,(name,initial,queued,release) in enumerate([
    ('queued ID is not playback',1,1,1),('preload flag is not PCM',4,1,1),
    ('no voice request',0,0,0),('failed request cleaned up',3,0,0)],100):
    m.call('stage9_r5_message_setup',idx);draws.clear();state[0]=initial;pending[0]=queued;ready[0]=0
    if queued:
        for _ in range(20):assert m.call('stage9_r5_message_draw',idx)==4096
        assert not draws,'subtitle timer/render advanced during pending load'
    state[0]=release;ready[0]=1 if queued else 0
    assert m.call('stage9_r5_message_draw',idx)==4096-137,(name,draws)
    assert len(draws)==1
    # Gate is latched open; later task-state changes cannot pause the page.
    state[0]=2;pending[0]=1
    assert m.call('stage9_r5_message_draw',idx)==4096-274
    cases.append(name)
report=dict(status='PASS',scope=__doc__,cases=cases,loading_frames_timer_unchanged=20,
    authored_timer_step_unchanged=137,elf_sha256=hashlib.sha256(game_elf.read_bytes()).hexdigest())
(p/'reports/stage9-r5-subtitle-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
