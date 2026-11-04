#!/usr/bin/env python3
"""Normal Cafe initialization then original Triangle/Status via pad input."""
import json,os,struct
from pathlib import Path
fixture=Path(__file__).with_name('test_stage6_game.py')
ns={'__file__':str(fixture),'__name__':'stage7_cafe_fixture'}
exec(compile(fixture.read_text().split('r=CafeRunner();')[0],str(fixture),'exec'),ns)
game=ns['game']
class Inventory(ns['CafeRunner']):
    opened=False;inventory_frames=0;inventory_submissions=0
    def read_pad(self,*_):
        self.synthetic_clock+=1;self.pad_polls+=1
        pad=2 if self.title_age in (90,150) else 0
        if self.state==11 and self.sys==10 and self.s0>5 and self.s0<47:pad=8
        elif self.state==11 and self.sys in (7,10) and self.pad_polls%90==0:pad=2
        if self.map==1 and self.z>269*4096 and self.state==11 and self.sys==0 and not self.disabled and self.health>0 and not self.opened:
            pad=1<<10;self.opened=True
        if self.opened and self.state==11 and self.sys in (0,2):pad=1<<10
        if self.state==14:
            self.inventory_frames+=1
        self.ret(pad)
    def sync(self,*args):
        if self.state==14 and self.frame_draws:
            self.inventory_submissions+=1
            if self.inventory_submissions>=30:self.stopped=True;self.uc.emu_stop()
        return super().sync(*args)
    def vblank(self,*_):
        self.synthetic_clock+=1;self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0
        if self.frames>26000:self.stopped=True;self.uc.emu_stop()
        self.ret(0)
r=Inventory();report=game.run(r,seconds=int(os.environ.get('SH_TEST_SECONDS','300')))
report.update({'opened_with_triangle':r.opened,'inventory_pad_polls':r.inventory_frames,'inventory_submissions':r.inventory_submissions,
    'map':r.map,'sys':r.sys,'disabled':r.disabled,'route':r.route[-20:]})
(game.port/'reports/stage7-inventory-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
assert r.opened and r.inventory_submissions>=30 and not report['failure'] and not report['exception'] and not report['invalid'],report
