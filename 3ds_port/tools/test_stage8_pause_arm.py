"""Execute the linked pause loop; replace only SDK HID/display/clock calls."""
import json,struct
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'stage8_pause_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
Machine=ns['Machine'];symbols=ns['symbols'];p=ns['port']
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1
results=[]
for name,keys,want_title,want_fps in [
    ('resume',[8,0,2,0],0,30),
    ('title',[8,0,128,0,2,0],1,30),
    ('fps',[8,0,128,0,128,0,16,0,1,0],0,60)]:
    m=Machine();m.word('game_state',11);m.word('fps_limit',30)
    # SDK pause-loop fixture. Engine eligibility is exercised independently
    # by the R2 cutscene/state contract test.
    m.hook('Game3ds_CanPause',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,1),m.ret()))
    sequence=list(keys);polls=[0];tick=[0]
    def ret_value(value):m.uc.reg_write(UC_ARM_REG_R0,value);m.ret()
    def held(*_):
        polls[0]+=1;assert polls[0]<64,(name,'pause input loop stuck')
        ret_value(sequence.pop(0) if sequence else 0)
    def clock(*_):
        tick[0]+=1000000;m.uc.reg_write(UC_ARM_REG_R0,tick[0]);m.uc.reg_write(UC_ARM_REG_R1,0);m.ret()
    for sdk in ('hidScanInput','consoleClear','gfxFlushBuffers','render3ds_console_bottom','gspWaitForEvent'):
        m.hook(sdk,lambda *_:m.ret())
    m.hook('aptMainLoop',lambda *_:ret_value(1))
    m.hook('printf',lambda *_:ret_value(0));m.hook('hidKeysHeld',held)
    m.hook('svcGetSystemTick',clock)
    assert m.call('game3ds_read_pad')==0
    title=m.call('game3ds_take_title_request');fps=m.call('game3ds_fps_limit')
    assert (title,fps)==(want_title,want_fps),(name,title,fps)
    assert m.call('game3ds_take_title_request')==0
    assert not sequence,(name,sequence)
    results.append(dict(case=name,title_request=title,fps=fps,HID_polls=polls[0]))
m=Machine()
for sdk in ('hidScanInput',):m.hook(sdk,lambda *_:m.ret())
m.hook('aptMainLoop',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,1),m.ret()))
m.hook('hidKeysHeld',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,8),m.ret()))
eligible=[0]
m.hook('Game3ds_CanPause',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,eligible[0]),m.ret()))
assert m.call('game3ds_read_pad')==8
eligible[0]=1
assert m.call('game3ds_read_pad')==8
results.append(dict(case='cutscene_START_passes_through_and_held_skip_does_not_open_pause',passed=True))
report=dict(status='PASS',execution='actual linked ARM pause loop; SDK input/output and clock mocked',cases=results)
(p/'reports/stage8-pause-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
