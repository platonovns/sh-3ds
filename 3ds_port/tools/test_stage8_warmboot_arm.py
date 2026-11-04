"""Original warm reset from initialized gameplay, not just a pause UI request."""
import json
import run_arm_game as game
r=game.GameRunner();report=game.run(r)
assert report['first_map_state_frame'] is not None and not report['failure'] and not report['invalid'] and not report['exception'],report
for handle,f in list(r.handles.items()):
    if f.closed:r.handles[handle]=open(f.name,'rb')
r.stopped=False
def wait_fixture(*_):r.frames+=1;r.ret(0)
r.bridge('game3ds_wait_vblank',wait_fixture)
r.call('Game_WarmBoot');r.call('Game3ds_Observe')
result=dict(status='PASS',execution='actual ARM original Game_WarmBoot after normal boot/New Game',
    game_state=r.state,first_failure=r.failure,invalid=r.invalid)
assert r.state==7 and not r.failure and not r.invalid,result
print(json.dumps(result,indent=2))
