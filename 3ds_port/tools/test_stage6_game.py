#!/usr/bin/env python3
"""Execute real ARM New Game/Cafe code; host boundaries only, no state injection."""
import json, os, struct
import run_arm_game as game
from unicorn.arm_const import UC_ARM_REG_SP

class CafeRunner(game.GameRunner):
    def __init__(self):
        super().__init__()
        self.map=0;self.room=0;self.health=0;self.disabled=1
        self.sys=0;self.s0=0;self.s1=0;self.event_id=0;self.x=0;self.z=0;self.yaw=0
        self.route=[];self.media=[];self.functional_frame=None;self.functional=False
        self.synthetic_clock=0;self.pad_polls=0
        self.bridge('game3ds_map_observe',self.map_observe)
        self.bridge('game3ds_player_observe',self.player_observe)
        self.bridge('game3ds_media_skip',self.media_skip)
        # The renderer recorder returns instantly; a wait-only fake clock can
        # stop forever in retail's unlocked frames. Advance host time at pad
        # polls too. This fixture tests state progression, never frame pacing.
        self.bridge('game3ds_vblank_clock',lambda *_:self.ret(self.synthetic_clock))
        self.bridge('game3ds_hblank_clock',lambda *_:self.ret(self.synthetic_clock*263))
    def map_observe(self,map,room,health,disabled):
        self.map=map;self.room=room;self.health=health;self.disabled=disabled;self.ret()
    def player_observe(self,x,z,yaw,sys):
        self.x=x;self.z=z;self.yaw=yaw;self.sys=sys
        _,self.s0,self.s1,self.event_id=struct.unpack('<4I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),16))
        r=(self.map,self.room,self.state,self.step,sys,self.s0,self.s1,self.event_id)
        if not self.route or tuple(self.route[-1]['state'])!=r:
            self.route.append({'frame':self.frames,'state':r,'x':x,'z':z,'health':self.health})
        self.ret()
    def media_skip(self,kind,id,offset,_):
        r=(kind,id,offset)
        if r not in self.media:self.media.append(r)
        self.ret()
    def vblank(self,*_):
        self.synthetic_clock+=1
        self.frames+=1
        self.title_age=self.title_age+1 if self.state==7 else 0
        if self.map==1 and self.state==11 and self.sys==0 and not self.disabled and self.health>0:
            if self.functional_frame is None:self.functional_frame=self.synthetic_clock
            if self.synthetic_clock-self.functional_frame>=120:self.functional=True;self.stopped=True;self.uc.emu_stop()
        if self.frames>=26000:self.stopped=True;self.uc.emu_stop()
        self.ret(0)
    def read_pad(self,*_):
        self.synthetic_clock+=1;self.pad_polls+=1
        pad=2 if self.title_age in (90,150) else 0
        # Ordinary message-dismiss button, no cutscene skip unless explicitly requested.
        if self.state==11 and self.sys in (7,10) and self.pad_polls%90==0:pad|=2
        if os.environ.get('SH_TEST_SKIP') and self.map==1 and self.sys==10 and self.s0>5 and self.pad_polls%120==0:pad|=8
        if self.map==1 and self.state==11 and self.sys==0 and not self.disabled and self.health>0:
            if self.functional_frame is None:self.functional_frame=self.synthetic_clock
            if self.synthetic_clock-self.functional_frame>=120:self.functional=True;self.stopped=True;self.uc.emu_stop()
        self.ret(pad)

r=CafeRunner();report=game.run(r,seconds=int(os.environ.get('SH_TEST_SECONDS','600')))
report.update({'elf':str(game.game_elf),'functional_cafe':r.functional,'map':r.map,'synthetic_clock':r.synthetic_clock,
    'route':r.route,'skipped_media':r.media})
print(json.dumps(report,indent=2))
assert not report['failure'] and not report['exception'] and not report['invalid'],report
assert r.functional,'Cafe did not reach 120 functional frames'
