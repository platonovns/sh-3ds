"""Short real-disc map initialization checks; synthetic chapter entry states.

Original MainLoop, retail map/ANM/IPD reads and native init/update execute.
No continuous route replay; audio/SDK/GPU use the established ARM runner hooks.
"""
from pathlib import Path
import hashlib,json,os,struct,sys
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
ELF=PORT/'build/alchemilla/alchemilla-content.elf'
os.environ['SH_GAME_ELF']=str(ELF);os.environ['SH_STAGE9_REGRESSION']='1'
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
import run_arm_game as game
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0

class Entry(game.GameRunner):
    def __init__(self,map,pose_map,point,flags):
        super().__init__();self.wanted=map;self.pose_map=pose_map;self.point=point;self.seeded=False;self.placed=False
        self.flags=flags;self.ready=0;self.map=None;self.room=None;self.game_ticks=0
        self.uc.hook_add(UC_HOOK_CODE,self.seed,begin=game.symbols['GameBoot_MapLoad'],end=game.symbols['GameBoot_MapLoad'])
        self.uc.hook_add(UC_HOOK_CODE,self.place,begin=game.symbols['Chara_PositionSet'],end=game.symbols['Chara_PositionSet'])
        self.uc.hook_add(UC_HOOK_CODE,self.tick,begin=game.symbols['GameState_InGame_Update'],end=game.symbols['GameState_InGame_Update'])
        self.bridge('game3ds_map_observe',self.map_observe)
    def seed(self,uc,*_):
        if self.seeded:return
        self.seeded=True
        save=struct.unpack('<I',uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
        uc.mem_write(save+0xa4,bytes([self.wanted]))
        # Completed school/church and bridge: a nearby original save-like
        # entry for resource/lifecycle validation, never a shipping shortcut.
        for flag in (132,134,146,164,165,166,176,179,181,182)+self.flags:
            p=save+0x168+(flag//32)*4
            word=struct.unpack('<I',uc.mem_read(p,4))[0]|(1<<(flag%32))
            uc.mem_write(p,struct.pack('<I',word))
        uc.reg_write(UC_ARM_REG_R0,self.wanted)
    def place(self,uc,*_):
        if self.placed:return
        self.placed=True
        # Retail transition eventParam indexes the SOURCE overlay's arrival
        # pose, copied before loading the destination (D_800BCDB0).
        uc.reg_write(UC_ARM_REG_R0,game.symbols[self.pose_map+'_MAP_POINTS']+self.point*12)
    def map_observe(self,map,room,*_):
        self.map=map;self.room=room
        self.ret()
    def tick(self,uc,*_):
        if self.map==self.wanted:
            self.game_ticks+=1
            disabled=uc.mem_read(game.symbols['g_Player_DisableControl'],1)[0]
            sysstate=int.from_bytes(uc.mem_read(game.symbols['g_SysWork']+8,4),'little')
            self.ready=self.ready+1 if not disabled and sysstate==0 else 0
            # Stop at the next tick entry, after 20 completed update calls.
            if self.ready>=21:self.stopped=True;uc.emu_stop()
    def vblank(self,*_):
        self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0;self.ret()

results=[]
for map,pose_map,point,flags in ((15,'map2_s02',19,(195,196,197,198)),
    (18,'map3_s02',15,(195,196,197,198,210,211,224,237,238)),
    (21,'map3_s04',39,(195,196,197,198,210,211,224,237,238,294,295,297)),
    (12,'map3_s06',1,(195,196,197,198,210,211,224,237,238,294,295,296,297))):
    r=Entry(map,pose_map,point,flags);result=game.run(r,seconds=180)
    result.update(map=map,arrival_pose_source=pose_map,arrival_pose_index=point,room=r.room,stable_control_ticks=max(r.ready-1,0),game_ticks=r.game_ticks)
    results.append(result)
    print(json.dumps(result,indent=2),flush=True)
    if r.ready<20 or result['failure'] or result['invalid'] or result['exception']:break
report=dict(status='PASS' if len(results)==4 and all(x['stable_control_ticks']>=20 and not x['failure'] and not x['invalid'] and not x['exception'] for x in results) else 'FAIL',
    execution=__doc__,results=results,elf_sha256=hashlib.sha256(ELF.read_bytes()).hexdigest(),
    hardware_accepted=False,full_playthrough=False,original_memcard_written=False)
(PORT/'reports/alchemilla-runtime-arm.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['status']=='PASS',report

