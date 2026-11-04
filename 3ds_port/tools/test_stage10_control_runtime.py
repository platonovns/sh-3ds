"""Actual native MainLoop/player locomotion from a loaded MAP2 checkpoint.
Physical HID vectors and camera-pose boundaries are fixture inputs. Original
player states, speeds, animation and world collision execute without shims.
"""
import hashlib,json,math,os,struct,time
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_R0
path=Path(__file__).with_name('test_stage10_cafe_combat_runtime.py');ns={'__file__':str(path),'__name__':'control_runtime'}
exec(compile(path.read_text().split('r=CombatRunner();run=')[0],str(path),'exec'),ns)
game=ns['game'];p=game.port
class Movement(ns['CombatRunner']):
    def __init__(self):
        super().__init__();self.ready=0;self.phase='boot';self.case=None;self.age=0;self.rows=[]
        self.bridge('game3ds_read_analog',self.analog)
        self.bridge('vwGetViewAngle',self.camera)
        self.bridge('vwGetViewPosition',self.camera_position)
        raw=struct.unpack('<30I',self.uc.mem_read(game.symbols['stage10_reload_fields'],120))
        self.reload_fields=list(zip(raw[::2],raw[1::2]))
    def camera(self,ptr,*_):
        yaw=1024
        if self.case and self.case.get('cut') and self.age>=25:yaw=3072
        if self.case and self.case.get('pan'):yaw+=self.age*2
        self.uc.mem_write(ptr,struct.pack('<4h',0,yaw,0,0));self.ret()
    def camera_position(self,ptr,*_):self.uc.mem_write(ptr,b'\0'*12);self.ret()
    def analog(self,cx,cy,rx,ry):
        values=(0,0,0,0) if self.phase=='boot' else self.case.get('analog',(0,0,0,0))
        for address,value in zip((cx,cy,rx,ry),values):self.uc.mem_write(address,struct.pack('<i',value))
        self.ret()
    def read_pad(self,*_):
        if self.state!=11:return game.GameRunner.read_pad(self)
        if self.phase=='boot':self.ret((2|(1<<3)) if self.ticks%20<2 else 0)
        else:self.ret(self.case['keys'])
    def tick(self,*_):
        self.ticks+=1
        row=[int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little',signed=True) for a,n in self.fields]
        if self.phase=='boot':
            self.ready=self.ready+1 if row[0]==0 and self.map==10 else 0
            if self.ready==10:
                self.file_state={h:(f.name,f.tell()) for h,f in self.handles.items()}
                self.stopped=True;self.uc.emu_stop()
        else:
            self.age+=1
            a,n=self.reload_fields[3]
            debug={name:int.from_bytes(self.uc.mem_read(game.symbols[name],2 if name in ('g_Player_IsAiming',) else 4),'little',signed=True) for name in ('modern','have_travel','g_DeltaTime','g_Player_DisableControl','g_Player_IsAiming')}
            self.rows.append(dict(age=self.age,sys=row[0],x=row[13],z=row[14],yaw=row[15],state=row[3],upper=row[4],lower=int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little'),debug=debug))
            if self.age>=75:self.stopped=True;self.uc.emu_stop()
    def vblank(self,*_):self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0;self.ret()
r=Movement();boot=game.run(r,seconds=240)
assert r.ready==10 and not any(boot[k] for k in ('failure','invalid','exception')),boot
regions=[(start,bytes(r.uc.mem_read(start,end-start+1))) for start,end,permissions in r.uc.mem_regions()]
context=r.uc.context_save();baseline_frames=r.frames;baseline_ticks=r.ticks
cases=[
    dict(name='tank_dpad',mode=0,keys=1<<6,expected=(0,-1)),
    dict(name='tank_circle',mode=0,keys=1<<30,analog=(0,156,0,0),expected=(0,-1)),
    dict(name='modern_dpad',mode=1,keys=1<<6,expected=(1,0)),
    dict(name='modern_analog',mode=1,keys=1<<30,analog=(83,119,0,0),expected=(119,-83)),
    dict(name='hybrid_dpad',mode=2,keys=1<<6,expected=(0,-1)),
    dict(name='hybrid_circle',mode=2,keys=1<<30,analog=(0,156,0,0),expected=(1,0)),
    dict(name='hybrid_dpad_priority',mode=2,keys=(1<<6)|(1<<31),analog=(0,-156,0,0),expected=(0,-1)),
    dict(name='modern_cstick',mode=1,keys=(1<<30)|(1<<24),analog=(0,156,156,60),expected=(1,0)),
    dict(name='modern_cut',mode=1,keys=1<<6,cut=True,expected=(1,0)),
    dict(name='modern_pan',mode=1,keys=1<<6,pan=True,expected=(1,0))]
results=[]
for case in cases:
    if os.environ.get('SH_CONTROL_CASE') and case['name']!=os.environ['SH_CONTROL_CASE']:continue
    for start,data in regions:r.uc.mem_write(start,data)
    r.uc.context_restore(context)
    r.handles={h:open(name,'rb') for h,(name,pos) in r.file_state.items()}
    for h,(name,pos) in r.file_state.items():r.handles[h].seek(pos)
    r.phase='case';r.case=case;r.age=0;r.rows=[];r.frames=baseline_frames;r.ticks=baseline_ticks;r.stopped=False
    r.uc.mem_write(game.symbols['control_mode'],struct.pack('<I',case['mode']))
    a,n=r.fields[15];r.uc.mem_write(game.symbols['g_SysWork']+a,struct.pack('<h',2048))
    for index,value in ((13,0),(14,265*4096)):
        a,n=r.fields[index];r.uc.mem_write(game.symbols['g_SysWork']+a,struct.pack('<i',value))
    start=time.monotonic();error=None
    try:
        while not r.stopped and time.monotonic()-start<180:
            r.uc.emu_start(r.uc.reg_read(UC_ARM_REG_PC),0x30000000,timeout=30_000_000,count=200_000_000)
    except Exception as e:error=repr(e)
    for f in r.handles.values():f.close()
    first,last=r.rows[0],r.rows[-1];dx=last['x']-first['x'];dz=last['z']-first['z'];ex,ez=case['expected']
    dot=dx*ex+dz*ez;cross=dx*ez-dz*ex
    cosine=dot/math.sqrt(max(1,(dx*dx+dz*dz)*(ex*ex+ez*ez)))
    result=dict(case=case,updates=r.age,delta=[dx,dz],alignment=cosine,rows=r.rows,error=error,failure=r.failure,invalid=r.invalid)
    results.append(result)
    (p/'reports/stage10-r5-control-runtime.json').write_text(json.dumps(dict(scope=__doc__,cases=results,elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest()),indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
    assert not error and not r.failure and not r.invalid and r.age==75,result
    assert dx*dx+dz*dz>4096**2 and cosine>.9,(case,dx,dz,cosine)
    if case.get('cut'):assert all(row['x']>=r.rows[i-1]['x'] for i,row in enumerate(r.rows) if i>0),'Camera cut reversed travel'
print('PASS: actual Tank/Modern/Hybrid movement, analog vector, priority, C-stick and camera cut/pan.')
