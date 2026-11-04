"""Original Air Screamer AI/attack and player reaction after nearby Cafe init."""
import json,struct
from pathlib import Path
fixture=Path(__file__).with_name('test_stage8_blood_arm.py')
exec(compile(fixture.read_text().split('error=None;ticks=0')[0],str(fixture),'exec'))
samples=[];error=None;slot=None;ticks=0
r.stopped=False;r.scene_frame=None
def wait_fixture(*_):r.frames+=1;r.ret(0)
r.bridge('game3ds_wait_vblank',wait_fixture)
try:
    slot=r.call('stage8_enemy_begin')
    for tick in range(240):
        r.call('stage8_enemy_tick',0x20008000);ticks+=1
        row=list(struct.unpack('<9I',r.uc.mem_read(0x20008000,36)))
        if not samples or row!=samples[-1]['values']:samples.append(dict(tick=tick,values=row))
except Exception as e:error=repr(e)
report=dict(execution='actual ARM Cafe debug init, AS resources, forced registered bite, original attack geometry/player reaction/effect tick; not natural AI encounter reproduction',
    elf=str(game.game_elf),slot=slot,ticks=ticks,samples=samples[-64:],halt=r.failure,invalid=r.invalid,error=error)
print(json.dumps(report,indent=2))
(p/'reports/stage8-enemy-arm.json').write_text(json.dumps(report,indent=2)+'\n')
assert ticks==240 and not r.failure and not r.invalid and not error,report
