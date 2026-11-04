"""Repeat the linked native pause loop; HID/display are recorded SDK boundaries."""
import hashlib,json,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
ns={'__file__':str(fixture),'__name__':'stage10_pause_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
m=ns['Machine']();p=ns['port'];symbols=ns['symbols']
def ret(value=0):m.uc.reg_write(UC_ARM_REG_R0,value);m.ret()
for name in ('hidScanInput','consoleClear','gfxFlushBuffers','render3ds_console_bottom',
             'gspWaitForEvent','game_audio_pause'):
    m.hook(name,lambda *_:ret())
m.hook('aptMainLoop',lambda *_:ret(1));m.hook('printf',lambda *_:ret())
eligible=[1];m.hook('Game3ds_CanPause',lambda *_:ret(eligible[0]))
keys=[];polls=[0];ticks=[0]
def held(*_):
    polls[0]+=1
    assert keys,'Unexpected HID poll'
    ret(keys.pop(0))
def clock(*_):
    ticks[0]+=100000
    m.uc.reg_write(UC_ARM_REG_R1,ticks[0]>>32);ret(ticks[0]&0xffffffff)
m.hook('hidKeysHeld',held);m.hook('svcGetSystemTick',clock)
m.word('game_state',11)
for i in range(256):
    keys[:]=[8,0,8 if i%2 else 2,0]
    assert m.call('game3ds_read_pad')==0
    assert not keys
    assert m.call('game3ds_take_title_request')==0
    # Holding Skip across the end of a cutscene must not open pause until
    # release and a fresh press. Original non-gameplay START passes through.
    eligible[0]=0;keys[:]=[0,8];assert m.call('game3ds_read_pad')==0
    assert m.call('game3ds_read_pad')==8
    eligible[0]=1;keys[:]=[8,0]
    assert m.call('game3ds_read_pad')==8
    assert m.call('game3ds_read_pad')==0
assert m.get_word('start_pauses')==m.get_word('start_resumes')==256
assert m.get_word('start_passthrough')==256
report=dict(status='PASS',scope=__doc__,pause_resume_cycles=256,
    skip_held_across_context_changes=256,HID_polls=polls[0],hardware_crash_reproduced=False,
    limitation='GPU, HID, APT, clocks and audio pause are SDK recorders; real GPU/threads need hardware or Azahar',
    elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest())
(p/'reports/stage10-pause-stress-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
