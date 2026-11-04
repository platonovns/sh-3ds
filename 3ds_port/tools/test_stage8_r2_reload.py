"""Test-only Cafe start + actual map reload spawn; no application shortcuts."""
import json,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage8_r2_probe.o';elf=p/'build/stage8_r2_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage8_r2_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage8_r2_'):game.symbols[s[2]]=int(s[0],16)
cases=[]
for fps in (30,60):
    r=game.GameRunner();r.uc.mem_write(game.symbols['fps_limit'],struct.pack('<I',fps))
    r.uc.hook_add(UC_HOOK_CODE,lambda uc,*_:uc.reg_write(UC_ARM_REG_R0,1),begin=game.symbols['GameBoot_SavegameInitialize'],end=game.symbols['GameBoot_SavegameInitialize'])
    boot=game.run(r,seconds=90)
    assert boot['first_map_state_frame'] is not None and not boot['failure'] and not boot['invalid'],boot
    for h,f in list(r.handles.items()):
        if f.closed:r.handles[h]=open(f.name,'rb')
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
    r.stopped=False;r.scene_frame=None
    r.bridge('game3ds_wait_vblank',lambda *_:(setattr(r,'frames',r.frames+1),r.ret(0)))
    generated=[]
    r.bridge('game3ds_model_observe',lambda character,n,fade,*_:(generated.append((character,n,fade)),r.ret()))
    r.call('stage8_r2_reload',0x20008000)
    values=struct.unpack('<5I',r.uc.mem_read(0x20008000,20))
    assert values[0]==values[3]==2 and values[1]==0xfffff000,values
    states=[]
    for tick in range(fps*2):
        r.call('stage8_r2_flight',4096//fps,0x20008100)
        state=struct.unpack('<9I',r.uc.mem_read(0x20008100,36));states.append(state)
        assert state[0]==2,state
    # Exercise the original Cafe skip dispatch, with a component timer fixture.
    skip=r.call('stage8_r2_skip');assert skip in (52,53),skip
    cases.append(dict(fps=fps,reload=values,AI_ticks=len(states),first=states[0],last=states[-1],
        model_emission_calls=len([x for x in generated if x[0]==2]),
        model_emitted_bytes=sum(x[1] for x in generated if x[0]==2),
        original_Cafe_skip_state=skip,halt=r.failure,invalid=r.invalid))
    assert not r.failure and not r.invalid,cases[-1]
report=dict(status='PASS',elf=str(game.game_elf),cases=cases,
    scope='test-only Cafe map selection and reload flags; original NPC update. Not natural encounter/hardware visibility acceptance')
print(json.dumps(report,indent=2))
(p/'reports'/('stage8-r2-reload-'+os.environ.get('SH_TEST_LABEL','working')+'.json')).write_text(json.dumps(report,indent=2)+'\n')
