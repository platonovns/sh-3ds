"""Original motion-blur/fog producers and native warning on linked ARM."""
import json,os,shlex,struct,subprocess
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'r2_gpu'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
Machine=ns['Machine'];symbols=ns['symbols'];p=ns['port']
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage8_r2_probe.o';elf=p/'build/stage8_r2_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage8_r2_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage8_r2_'):symbols[s[2]]=int(s[0],16)
def machine():
    m=Machine()
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
    m.word('GsOUT_PACKET_P',symbols['g_PsxRam']+0x1a2600)
    m.word('game3ds_canonical',symbols['vram'])
    return m
from unicorn.arm_const import UC_ARM_REG_R0
result={}
m=machine()
assert m.call('stage8_r2_pause',0,1,0)==1
assert m.call('stage8_r2_pause',0,20,0)==0
assert m.call('stage8_r2_pause',0,1,10)==0
assert m.call('stage8_r2_pause',0xffffffff,1,0)==0
result['pause_engine_state_and_cutscene_gates']='PASS'
m=machine()
m.hook('game3ds_gpu_resolve',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,1),m.ret()))
m.call('stage8_r2_transition',224)
feedback=[d for d in m.draws if d['textured']]
assert len(feedback)==2,len(feedback)
extents=[]
for d in feedback:
    v=d['vertices'];xs=v[0::9];ys=v[1::9]
    extents.append([min(xs),max(xs),min(ys),max(ys)])
    assert d['page']&0x10000
    assert max(v[3::9])*512<=400.001
assert sorted(extents)==[[0,320,0,240],[320,400,0,240]],extents
result['original_motion_blur_native_extent']=extents
result['feedback_samples_native_framebuffer_without_rescale']=True
m=machine()
m.hook('game3ds_gpu_resolve',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,1),m.ret()))
m.call('stage8_r2_transition',448)
fields=[d for d in m.draws if d['textured']]
assert len(fields)==4,len(fields)
assert min(min(d['vertices'][1::9]) for d in fields)==.5
assert max(max(d['vertices'][1::9]) for d in fields)==448.5
result['interlaced_feedback_both_fields']=True
m=machine();m.call('stage8_r2_fog')
assert len(m.draws)==1,m.draws
v=m.draws[0]['vertices'];ys=v[1::9]
assert min(ys)<=0 and max(ys)>=240,ys
result['original_masked_fog_vertical_extent']=[min(ys),max(ys)]
m=machine();m.call('Game3ds_WarningInit');m.call('Game3ds_WarningFrame',0)
art=[d for d in m.draws if d['textured']]
assert len(art)==2 # Original third SPRT is entirely outside the 320-pixel clip.
assert all(min(d['vertices'][1::9])==.5 and max(d['vertices'][1::9])==256.5 for d in art)
result['warning_original_progressive_canvas']='PASS'
# Stop after the fade assignment: exercise original entry branch without running
# unrelated map/event updates in an uninitialized fixture.
for previous,want in ((14,0),(11,6)):
    m=machine();m.word('g_Screen_FadeStatus',5)
    m.hook('func_80037154',lambda *_:m.uc.emu_stop())
    m.uc.reg_write(ns['UC_ARM_REG_SP'],0x1001ffc0)
    m.uc.reg_write(ns['UC_ARM_REG_LR'],0x30000000)
    m.uc.reg_write(UC_ARM_REG_R0,previous)
    m.uc.emu_start(symbols['stage8_r2_status_return'],0x30000000,count=100000)
    assert m.get_word('g_Screen_FadeStatus')==want,(previous,m.get_word('g_Screen_FadeStatus'))
result['status_return_does_not_start_top_fade']='PASS'
result.update(status='PASS',execution='actual linked ARM producers; SDK recorders; not hardware acceptance')
(p/'reports/stage8-r2-gpu-arm.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
