"""Original aim/fire/reload with released and held aim after completion."""
import hashlib,json,os,struct
from pathlib import Path
path=Path(__file__).with_name('test_stage10_cafe_combat_runtime.py')
ns={'__file__':str(path),'__name__':'reload_fixture'}
exec(compile(path.read_text().split('r=CombatRunner();run=')[0],str(path),'exec'),ns)
game=ns['game'];p=game.port
class Reload(ns['CombatRunner']):
    def __init__(self,hold):
        super().__init__();self.hold=hold;self.seen_reload=None;self.completed=None;self.released=None
        self.ammo_seed_tick=None
        raw=struct.unpack('<30I',self.uc.mem_read(game.symbols['stage10_reload_fields'],120))
        self.reload_fields=list(zip(raw[::2],raw[1::2]));self.steps=[]
    def tick(self,*_):
        self.ticks+=1
        row=[int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little',signed=True) for a,n in self.reload_fields]
        # Seed a nearly empty magazine only AFTER original equip/top-off and
        # aim startup finish. The old tick-1 setup was immediately topped off
        # to 15 by original equip, so it still replayed a full magazine.
        if self.ammo_seed_tick is None and os.environ.get('SH_RELOAD_START_AMMO') and self.ticks>=20 and row[2]==19 and row[9] and row[10]>0:
            ammo=int(os.environ['SH_RELOAD_START_AMMO']);assert 1<=ammo<=15
            offset,length=self.reload_fields[10]
            self.uc.mem_write(game.symbols['g_SysWork']+offset,ammo.to_bytes(length,'little'))
            offset,length=self.fields[16]
            slot=int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+offset,length),'little')
            items,stride,count_offset=struct.unpack('<3I',self.uc.mem_read(game.symbols['stage10_reload_inventory_layout'],12))
            save=struct.unpack('<I',self.uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
            self.uc.mem_write(save+items+slot*stride+count_offset,bytes([ammo]))
            self.ammo_seed_tick=self.ticks
        row=[int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little',signed=True) for a,n in self.reload_fields]
        row.append(int.from_bytes(self.uc.mem_read(game.symbols['g_Player_IsAiming'],2),'little'))
        self.steps.append(dict(t=self.ticks,v=row))
        if row[2]==26 and self.seen_reload is None:self.seen_reload=self.ticks
        if self.seen_reload and self.completed is None and row[2]!=26 and row[10]>0:self.completed=self.ticks
        if self.completed and self.released is None and self.ticks>=self.completed+self.hold:self.released=self.ticks
        if self.ticks%100==0:print(json.dumps(dict(hold=self.hold,tick=self.ticks,v=row)),flush=True)
        if self.ticks>=1200 or self.released and self.ticks>=self.released+180:
            self.stopped=True;self.uc.emu_stop()
    def read_pad(self,*_):
        if self.state!=11:return game.GameRunner.read_pad(self)
        if self.released:
            self.ret((1<<6) if 40<=self.ticks-self.released<100 else 0)
        else:
            ready=self.ammo_seed_tick is not None or not os.environ.get('SH_RELOAD_START_AMMO')
            self.ret((1<<15)|(2 if ready and not self.completed and self.ticks%20<2 else 0))
cases=[]
for hold in (0,60):
    r=Reload(hold);run=game.run(r,seconds=480)
    case=dict(initial_ammo=int(os.environ.get('SH_RELOAD_START_AMMO','15')),ammo_seed_tick=r.ammo_seed_tick,hold_after_reload=hold,run=run,reload_start=r.seen_reload,reload_done=r.completed,
        aim_released=r.released,steps=r.steps,final=r.steps[-1]['v'])
    cases.append(case)
    (p/'reports'/os.environ.get('SH_RELOAD_REPORT','stage10-reload-runtime.json')).write_text(json.dumps(dict(cases=cases,
        fields=['sys','player','upper','lower','upper_anim','upper_frame','upper_time','upper_control','upper_step',
            'combat_aim','ammo','reserve','flags','lower_anim','lower_frame','input_aim'],
        elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False),indent=2)+'\n')
    assert not any(run[k] for k in ('failure','invalid','exception')),run
    assert r.seen_reload and r.completed and r.released,case['final']
    if r.ammo_seed_tick:
        assert all(s['v'][10]<=case['initial_ammo'] for s in r.steps if r.ammo_seed_tick<=s['t']<r.seen_reload),'Original equip overwrote fixture magazine'
        assert min(s['v'][10] for s in r.steps if r.ammo_seed_tick<=s['t']<=r.seen_reload)==0,'Reload must follow real empty magazine'
    assert all(s['v'][9] and s['v'][15] for s in r.steps if r.completed+2<=s['t']<r.released),case
    assert not case['final'][9] and not case['final'][15] and case['final'][2] in (0,1,2),case['final']
print(json.dumps(dict(status='PASS',cases=[{k:v for k,v in c.items() if k not in ('steps','run')} for c in cases]),indent=2))
