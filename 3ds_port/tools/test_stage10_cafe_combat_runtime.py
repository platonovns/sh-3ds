"""Original Cafe AI/player/combat after development entry; world draw isolated.
The physical pad facade supplies aim/fire only. Health, hits and AI are never
set by this runner. This is not normal-route or hardware acceptance.
"""
import hashlib,json,math,os,shlex,struct,subprocess
from pathlib import Path
import run_arm_game as game
from unicorn import UC_HOOK_CODE
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
probe_dir=p/'build'/('stage10-combat-probe-'+hashlib.sha256(game.game_elf.read_bytes()).hexdigest()[:12])
probe_dir.mkdir(exist_ok=True)
obj=probe_dir/'probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_combat_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage10_'):game.symbols[s[2]]=int(s[0],16)
class CombatRunner(game.GameRunner):
    def __init__(self):
        super().__init__();self.ticks=0;self.rows=[];self.commands=[];self.positional_sfx=[]
        self.flags=[];self.map=1;self.room=0;self.outdoor_ticks=0
        for i in range(count):
            typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
            if typ==1 and length:self.uc.mem_write(addr,raw[pos:pos+length])
        values=struct.unpack('<48I',self.uc.mem_read(game.symbols['stage10_combat_fields'],192))
        self.fields=list(zip(values[0::2],values[1::2]))
        self.uc.hook_add(UC_HOOK_CODE,self.tick,begin=game.symbols['GameState_InGame_Update'],end=game.symbols['GameState_InGame_Update'])
        self.bridge('Gfx_InGameDraw',lambda *_:self.ret())
        self.bridge('SD_Call',lambda command,*_:(self.commands.append(command),self.ret()))
        self.bridge('func_8005DC1C',lambda sound,*_:(self.positional_sfx.append(sound),self.ret()))
        self.bridge('game3ds_map_observe',self.map_observe)
        self.event_flags_offset=struct.unpack('<I',self.uc.mem_read(game.symbols['stage10_save_event_flags'],4))[0]
    def map_observe(self,map,room,*_):
        self.map=map;self.room=room;self.ret()
    def tick(self,*_):
        self.ticks+=1
        save=struct.unpack('<I',self.uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
        bits=struct.unpack('<I',self.uc.mem_read(save+self.event_flags_offset+4,4))[0]
        for flag in (48,51):
            if bits&(1<<(flag-32)) and not any(f['flag']==flag for f in self.flags):
                self.flags.append(dict(flag=flag,tick=self.ticks))
        if self.ticks==2 and (os.environ.get('SH_CAFE_FACE_AWAY') or os.environ.get('SH_CAFE_PLAYER_YAW')):
            yaw=int(os.environ.get('SH_CAFE_PLAYER_YAW','2048'))&4095
            a,n=self.fields[15];self.uc.mem_write(game.symbols['g_SysWork']+a,yaw.to_bytes(n,'little'))
        row=[int.from_bytes(self.uc.mem_read(game.symbols['g_SysWork']+a,n),'little',signed=True) for a,n in self.fields]
        self.pose=row
        if self.ticks%10==0 or not self.rows or row[:5]!=self.rows[-1]['v'][:5]:self.rows.append(dict(t=self.ticks,v=row))
        if self.ticks%100==0:print(json.dumps(dict(tick=self.ticks,state=row[:5],ammo=row[17],
            pose=row[13:16],map=self.map,flags=self.flags)),flush=True)
        if self.map==10 and row[0]==0:self.outdoor_ticks+=1
        if self.ticks>=int(os.environ.get('SH_CAFE_TICKS','600')) or row[0]==13 or self.outdoor_ticks>=20:
            self.stopped=True;self.uc.emu_stop()
    def read_pad(self,*_):
        if self.state==11:
            held=0 if os.environ.get('SH_CAFE_NO_FIRE') else (1<<15)|(2 if self.ticks%20<2 else 0)
            if os.environ.get('SH_CAFE_EXIT') and any(f['flag']==51 for f in self.flags):
                row=self.pose
                if self.map==10:
                    held=((1<<3) if row[0]==10 and self.ticks%30==0 else 0)|(2 if self.ticks%20<2 else 0)
                elif row[0]!=0:held=2 if self.ticks%20<2 else 0
                else:
                    # Camera-independent original tank pad; no position/yaw,
                    # event or HP writes occur after the diagnostic entry.
                    x,z=row[13]/4096,row[14]/4096
                    dx,dz=.95-x,269.5-z;distance=math.hypot(dx,dz)
                    desired=3072 if distance<.2 else round(math.atan2(dx,dz)*4096/(2*math.pi))&4095
                    error=(desired-row[15]+2048)%4096-2048
                    held=(1<<(4 if error>0 else 5)) if abs(error)>40 else 0
                    if distance>.2 and abs(error)<256:held|=1<<6
                    if distance<.5 and abs(error)<160 and self.ticks%20<2:held|=2
            self.ret(held)
        else:super().read_pad()
    def vblank(self,*_):
        self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0;self.ret(0)
r=CombatRunner();run=game.run(r,seconds=600)
r.call('stage10_combat_snapshot',0x20008000)
final=list(struct.unpack('<29I',r.uc.mem_read(0x20008000,116)))
report=dict(scope=__doc__,run=run,ticks=r.ticks,fields=['sys','harry_hp','enemy_hp','player_state','upper_state',
    'player_anim','player_frame','enemy_control','enemy_step','enemy_anim','enemy_x','enemy_y','enemy_z',
    'player_x','player_z','player_yaw','weapon_slot','loaded_ammo','player_damage','enemy_damage','attack_received',
    'aiming','weapon_attack','enemy_attack'],rows=r.rows,sound_commands=r.commands,
    final_snapshot=final,natural_event_flags=r.flags,map=r.map,room=r.room,outdoor_ticks=r.outdoor_ticks,
    positional_sfx=r.positional_sfx,face_away=bool(os.environ.get('SH_CAFE_FACE_AWAY')),
    fixture_player_yaw=int(os.environ.get('SH_CAFE_PLAYER_YAW','2048' if os.environ.get('SH_CAFE_FACE_AWAY') else '0') or '0'),
    weapon_sfx=list(struct.unpack('<3h',r.uc.mem_read(game.symbols['g_Player_EquippedWeaponInfo'],6))),
    elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False)
if os.environ.get('SH_AIR_SNAPSHOT'):
    folder=p/'build'/os.environ['SH_AIR_SNAPSHOT'];folder.mkdir(exist_ok=True)
    layout=struct.unpack('<3I',r.uc.mem_read(game.symbols['stage10_air_runtime_layout'],12))
    (folder/'sys.bin').write_bytes(bytes(r.uc.mem_read(game.symbols['g_SysWork'],layout[0])))
    metadata=struct.unpack('<12I',r.uc.mem_read(game.symbols['stage10_air_runtime_fields'],48))
    report['air_snapshot']=dict(layout=layout,fields=[list(metadata[i:i+2]) for i in range(0,12,2)])
    for name,length in [('map0_s01_sharedData_800E21D0_0_s01',0x200),('g_DeltaTime',4),('g_DeltaTimeRaw',4),('g_Player_IsAiming',2)]:
        (folder/(name+'.bin')).write_bytes(bytes(r.uc.mem_read(game.symbols[name],length)))
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
dest=p/'reports'/('stage10-cafe-no-fire-runtime.json' if os.environ.get('SH_CAFE_NO_FIRE') else 'stage10-cafe-fire-runtime.json')
if os.environ.get('SH_CAFE_EXIT'):dest=p/'reports/stage10-cafe-original-exit-runtime.json'
if os.environ.get('SH_CAFE_REPORT'):dest=p/'reports'/os.environ['SH_CAFE_REPORT']
dest.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(ticks=r.ticks,run=run,last_rows=r.rows[-3:]),indent=2))
assert r.ticks>=100 and not run['failure'] and not run['invalid'] and not run['exception'],run
if os.environ.get('SH_CAFE_EXIT'):
    assert r.map==10 and r.outdoor_ticks>=20 and {f['flag'] for f in r.flags}=={48,51},(r.ticks,r.map,r.flags,final)
elif os.environ.get('SH_CAFE_NO_FIRE'):
    assert min(row['v'][1] for row in r.rows)<r.rows[0]['v'][1],'Harry must receive original AI damage'
else:
    assert min(row['v'][17] for row in r.rows)<15,'No ammunition consumed'
    assert min(row['v'][2] for row in r.rows)<=0 and final[22] and final[28],final
    assert final[0]==0 and not final[23],'Original Cafe death event must return control'
