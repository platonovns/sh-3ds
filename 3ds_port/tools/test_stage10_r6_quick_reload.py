"""Physical ZR+Y shortcut through original Joy/player/reload, with seeded ammunition.
The fixture changes magazine/reserve once after normal equip/aim, then supplies
only physical pad inputs. No reload state, animation or ammo result is injected.
"""
import hashlib,json,os,struct
from pathlib import Path
path=Path(__file__).with_name('test_stage10_cafe_combat_runtime.py');ns={'__file__':str(path),'__name__':'quick_reload_fixture'}
exec(compile(path.read_text().split('r=CombatRunner();run=')[0],str(path),'exec'),ns)
game=ns['game'];p=game.port
class Quick(ns['CombatRunner']):
    def __init__(self,rate,reserve,repeat):
        super().__init__();self.rate=rate;self.reserve=reserve;self.repeat=repeat;self.seed=None;self.request=None;self.steps=[]
        self.bridge('game3ds_fps_limit',lambda *_:self.ret(rate))
        values=struct.unpack('<30I',self.uc.mem_read(game.symbols['stage10_reload_fields'],120));self.rf=list(zip(values[::2],values[1::2]))
    def tick(self,*_):
        self.ticks+=1
        row=[int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little',signed=True) for a,n in self.rf]
        if self.seed is None and self.ticks>=20 and row[2]==19 and row[9]:
            self.seed=self.ticks
            for idx,value in ((10,5),(11,self.reserve)):
                a,n=self.rf[idx];self.uc.mem_write(game.symbols['g_SysWork']+a,value.to_bytes(n,'little'))
            layout=struct.unpack('<3I',self.uc.mem_read(game.symbols['stage10_reload_inventory_layout'],12))
            save=struct.unpack('<I',self.uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
            for i in range(40):
                at=save+layout[0]+i*layout[1];item=self.uc.mem_read(at,1)[0]
                if item in (160,192):self.uc.mem_write(at+layout[2],bytes([5 if item==160 else self.reserve]))
        if self.seed and self.request is None and self.ticks==self.seed+(50 if os.environ.get('SH_QUICK_FROM_STANCE') else 10):self.request=self.ticks
        row=[int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little',signed=True) for a,n in self.rf]
        dt=int.from_bytes(self.uc.mem_read(game.symbols['g_DeltaTime'],4),'little',signed=True)
        self.steps.append(dict(tick=self.ticks,frames=self.frames,dt=dt,v=row))
        if self.ticks>=260 or self.request and self.ticks>=self.request+150:self.stopped=True;self.uc.emu_stop()
    def read_pad(self,*_):
        if self.state!=11:return game.GameRunner.read_pad(self)
        if os.environ.get('SH_QUICK_FROM_STANCE') and self.seed and self.ticks>self.seed+1 and self.request is None:self.ret(0);return
        if self.request and self.ticks>=self.request+100:self.ret(0);return
        held=1<<15
        if self.request:
            age=self.ticks-self.request
            if (age%12<2 if self.repeat else age<2):held|=1<<11
        self.ret(held)
cases=[]
spec=[(30,60,False)] if os.environ.get('SH_QUICK_OBSERVE') else [(rate,reserve,repeat) for rate in (30,60) for reserve,repeat in ((60,False),(3,True),(0,True))]
for rate,reserve,repeat in spec:
    r=Quick(rate,reserve,repeat);run=game.run(r,seconds=360)
    assert r.seed and r.request and not any(run[k] for k in ('failure','invalid','exception')),run
    steps=[s for s in r.steps if s['tick']>=r.seed]
    reload=[s for s in steps if s['v'][2]==26]
    changed=[s for s in steps if s['v'][10]!=5]
    result=dict(rate=rate,reserve=reserve,repeat=repeat,seed=r.seed,request=r.request,reload_frames=len(reload),
        from_stance=bool(os.environ.get('SH_QUICK_FROM_STANCE')),
        reload_sim_ms=sum(s['dt'] for s in reload)*1000/4096,
        first_ammo_change=changed[0]['tick'] if changed else None,final=steps[-1]['v'],steps=steps,run=run)
    cases.append(result)
    (p/'reports'/os.environ.get('SH_QUICK_REPORT','stage10-r6-quick-reload.json')).write_text(json.dumps(dict(scope=__doc__,cases=cases,elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False),indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('steps','run')}),flush=True)
    if not os.environ.get('SH_QUICK_OBSERVE'):
        if reserve:
            assert reload and changed and changed[0]['tick']>reload[0]['tick']+1,'Must play real reload before changing ammo'
            # State selection precedes animation dispatch by one MainLoop tick.
            track=reload[1:]
            assert len({s['v'][5] for s in track})>=3 and all(s['v'][4] in (62,63) for s in track),'Must execute the authored reload track'
            assert steps[-1]['v'][10]==min(15,5+reserve)
        else:assert not changed and not reload
        assert all(s['v'][10]+s['v'][11]==5+reserve for s in steps),'Ammunition conservation'
        assert steps[-1]['v'][2] in (0,1,2) and not steps[-1]['v'][9],'Aim must release normally'
