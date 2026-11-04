"""Nearby starts, original physical pickup/door/save triggers, real serialization.
Fixture moves between nearby subsystem starts, not a continuous route replay.
No item/event flag injection; memory-card transport uses a fresh test-only card.
"""
import ctypes as ct,hashlib,json,os,shlex,struct,subprocess,tempfile,time
from pathlib import Path
import run_arm_game as game
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
scope=os.environ.get('SH_PROGRESS_SCOPE','town');assert scope in ('town','school')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build'/('stage10_progression_'+scope+'_probe.o');elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_progression_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage10_progression_'):game.symbols[s[2]]=int(s[0],16)
folder=p/'build'/('stage10-r5-progression-'+scope);folder.mkdir(exist_ok=True)
subprocess.run(['cc','-shared','-fPIC','-O1','-g','-I'+str(p/'include'),str(p/'source/game_card_image.c'),'-o',str(folder/'card.so')],check=True)
core=ct.CDLL(str(folder/'card.so'))
class Progress(game.GameRunner):
    def __init__(self,card):
        super().__init__();self.card=card;self.ticks=0;self.ready=0;self.leg=-1;self.leg_age=0;self.action=None
        self.map=0;self.room=0;self.rows=[];self.completed=[];self.room_before=None;self.error=None
        for i in range(count):
            typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
            if typ==1 and length:self.uc.mem_write(addr,raw[pos:pos+length])
        self.meta=struct.unpack('<8I',self.uc.mem_read(game.symbols['stage10_progression_meta'],32))
        self.sysmeta=struct.unpack('<5I',self.uc.mem_read(game.symbols['stage10_progression_sys_meta'],20))
        self.savepose=struct.unpack('<3I',self.uc.mem_read(game.symbols['stage10_progression_savepose'],12))
        self.targets=[list(struct.unpack('<4I',self.uc.mem_read(game.symbols['stage10_progression_targets']+i*16,16))) for i in range(6)]
        self.bridge('Gfx_InGameDraw',lambda *_:self.ret())
        self.bridge('game3ds_map_observe',self.map_observe)
        self.bridge('game_card_mount',lambda *_:self.ret(core.game_card_mount(str(card).encode())))
        self.bridge('game_card_ready',lambda *_:self.ret(core.game_card_ready()))
        self.bridge('game_card_find',lambda name,*_:self.ret(core.game_card_find(self.string(name))))
        self.bridge('game_card_create',lambda name,n,*_:self.ret(core.game_card_create(self.string(name),n)))
        self.bridge('game_card_entry',self.entry);self.bridge('game_card_read',self.read);self.bridge('game_card_write',self.write)
        self.bridge('game_card_erase',lambda name,*_:self.ret(core.game_card_erase(self.string(name))))
        self.bridge('game_card_format',lambda *_:self.ret(core.game_card_format()))
        self.uc.hook_add(UC_HOOK_CODE,self.tick,begin=game.symbols['GameState_InGame_Update'],end=game.symbols['GameState_InGame_Update'])
        self.uc.hook_add(UC_HOOK_CODE,self.save_screen,begin=game.symbols['SaveScreen_LogicUpdate'],end=game.symbols['SaveScreen_LogicUpdate'])
    def string(self,ptr):return bytes(self.uc.mem_read(ptr,64)).split(b'\0')[0]
    def entry(self,block,name,size,*_):
        buf=ct.create_string_buffer(21);n=ct.c_uint();ok=core.game_card_entry(block,buf,ct.byref(n))
        if ok:
            if name:self.uc.mem_write(name,buf.raw)
            if size:self.uc.mem_write(size,struct.pack('<I',n.value))
        self.ret(ok)
    def read(self,block,offset,dest,n):
        buf=ct.create_string_buffer(n);ok=core.game_card_read(block,offset,buf,n)
        if ok:self.uc.mem_write(dest,buf.raw)
        self.ret(ok)
    def write(self,block,offset,src,n):self.ret(core.game_card_write(block,offset,ct.create_string_buffer(bytes(self.uc.mem_read(src,n))),n))
    def map_observe(self,map,room,*_):self.map=map;self.room=room;self.ret()
    def state_row(self):
        save=struct.unpack('<I',self.uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
        base=game.symbols['g_SysWork'];sys_off,sys_size,steps,position,yaw=self.sysmeta
        flags=[bool(int.from_bytes(self.uc.mem_read(save+self.meta[2]+(t[2]//32)*4,4),'little')&(1<<(t[2]%32))) for t in self.targets]
        inventory={}
        for i in range(40):
            item,n=bytes(self.uc.mem_read(save+self.meta[0]+i*self.meta[1],2))
            if item not in (0,255):inventory[item]=n
        return dict(tick=self.ticks,game=self.state,sys=int.from_bytes(self.uc.mem_read(base+sys_off,sys_size),'little'),
            steps=list(self.uc.mem_read(base+steps,4)),map=self.map,room=self.room,
            position=list(struct.unpack('<3i',self.uc.mem_read(base+position,12))),
            yaw=struct.unpack('<h',self.uc.mem_read(base+yaw,2))[0],flags=flags,inventory=inventory,
            location=int.from_bytes(self.uc.mem_read(save+self.meta[7],1),'little'),
            save_map=int.from_bytes(self.uc.mem_read(save+self.meta[5],1),'little'),
            save_room=int.from_bytes(self.uc.mem_read(save+self.meta[6],1),'little'),
            save_position=[int.from_bytes(self.uc.mem_read(save+a,n),'little',signed=True) for a,n in zip(self.savepose,(4,4,2))])
    def tick(self,*_):
        self.ticks+=1;self.leg_age+=1;row=self.state_row();self.pose=row
        if self.ticks%20==0:self.rows.append(row)
        if self.ticks%100==0:print(json.dumps(dict(leg=self.leg,age=self.leg_age,**row)),flush=True)
        if self.leg<0:
            self.ready=self.ready+1 if row['sys']==0 else 0
            if self.ready>=10:self.action='next';self.uc.emu_stop()
        elif scope=='town' and self.leg<6:
            if row['flags'][self.leg] and row['sys']==0:
                self.completed.append(dict(leg=self.leg,result=row));self.action='next';self.uc.emu_stop()
        elif scope=='town' and self.leg in (6,7,9):
            if self.leg_age>30 and row['room']!=self.room_before and row['sys']==0:
                self.completed.append(dict(leg=self.leg,room_before=self.room_before,result=row));self.action='next';self.uc.emu_stop()
        elif scope=='town' and self.leg==8 and self.leg_age>=90 and row['sys']==0:
            assert all(row['flags'][:5]),row
            assert all(row['inventory'].get(t[3])==1 for t in self.targets[2:5]),row
            self.completed.append(dict(leg=self.leg,result=row));self.action='next';self.uc.emu_stop()
        if self.leg_age>1400:self.error=dict(reason='event stalled',leg=self.leg,row=row);self.action='stop';self.uc.emu_stop()
    def save_screen(self,*_):
        if self.leg>=0:self.action='save';self.uc.emu_stop()
    def read_pad(self,*_):
        if self.state==11:self.ret((2 if self.leg_age%12<2 else 0)|((1<<3) if self.leg<0 and self.ticks%30<2 else 0))
        else:super().read_pad()
    def vblank(self,*_):self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0;self.ret()
with tempfile.TemporaryDirectory(prefix='sh-stage10-progress-') as temp:
    card=Path(temp)/'memcard.mcr';r=Progress(card);u=r.uc
    u.reg_write(UC_ARM_REG_SP,0x1001ffc0);u.reg_write(UC_ARM_REG_LR,0x30000000)
    u.reg_write(UC_ARM_REG_R0,game.symbols['fs_result']);u.reg_write(UC_ARM_REG_R1,game.symbols['vram'])
    pc=game.symbols['game3ds_run'];deadline=time.monotonic()+1800;save_result=loaded=None
    try:
        while time.monotonic()<deadline and not r.failure and not r.invalid and not r.error:
            u.emu_start(pc,0x30000000,timeout=30_000_000,count=200_000_000);pc=u.reg_read(UC_ARM_REG_PC)
            if r.action=='next':
                r.action=None;r.leg+=1;r.leg_age=0;r.room_before=r.room
                if scope=='school':poi,obb=89,1
                elif r.leg<6:poi,obb=r.targets[r.leg][:2]
                else:poi,obb={6:(22,1),7:(23,1),8:(17,1),9:(22,1),10:(107,1)}[r.leg]
                # Runner.call uses the emulated game's stack. Preserve its
                # suspended MainLoop locals as well as CPU registers when a
                # nearby fixture entry calls the original setup functions.
                context=u.context_save();stack=bytes(u.mem_read(0x10000000,0x20000))
                valid=r.call('stage10_progression_place',poi,obb)
                u.mem_write(0x10000000,stack);u.context_restore(context)
                assert valid,('fixture must face the original trigger',r.leg,poi)
                print(json.dumps(dict(start_leg=r.leg,poi=poi,room=r.room)),flush=True)
            elif r.action=='save':
                before=r.state_row();save_result=r.call('stage10_progression_save_current');assert save_result==0,save_result
                core.game_card_unmount();(folder/'memcard.mcr').write_bytes(card.read_bytes())
                second=Progress(card);second.call('PsxMemory_Init');loaded=second.call('stage10_progression_load');assert loaded==0,loaded
                after=second.state_row();assert after['flags']==before['flags'] and after['inventory']==before['inventory'],(before,after)
                assert after['location']==(4 if scope=='school' else 5),(scope,before,after)
                assert (after['save_map'],after['save_room'],after['save_position'])==(before['save_map'],before['save_room'],before['save_position']),(before,after)
                r.completed.append(dict(save=before,reloaded=after));break
            elif r.action=='stop' or r.stopped:break
        else:r.error=r.error or 'deadline'
    except Exception as error:r.error=repr(error)
    finally:
        core.game_card_unmount()
        for f in r.handles.values():f.close()
    report=dict(scope=__doc__,scenario=scope,status='PASS' if save_result==0 and loaded==0 and not r.error else 'FAIL',
        ticks=r.ticks,completed=r.completed,rows=r.rows,error=r.error,failure=r.failure,invalid=r.invalid,
        elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False)
    (p/'reports'/('stage10-r5-progression-'+scope+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
    assert report['status']=='PASS',report['error']
