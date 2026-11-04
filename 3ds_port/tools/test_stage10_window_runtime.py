"""Full Cafe window scene: original door trigger, DMS, effects and packet producers.
Only IO/GPU/audio boundaries are isolated. Never replaces original world draw.
"""
import bisect, collections, hashlib, json, os, struct,subprocess
import run_arm_game as game
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

nm=subprocess.check_output([os.environ['DEVKITARM']+'/bin/arm-none-eabi-nm','-n',str(game.game_elf)],text=True)
names=sorted((int(s[0],16),s[2]) for line in nm.splitlines() if len(s:=line.split())==3 and s[1] in ('T','t','W','w') and not s[2].startswith('$'))
addresses=[a for a,n in names]
class WindowRunner(game.GameRunner):
    def __init__(self):
        super().__init__();self.ticks=0;self.rows=[];self.producers=collections.Counter();self.last=0
        self.pose=[];self.window_seen=False;self.after_window=0
        self.frame_base=0;self.legacy_crossing=None
        # Packet arena overflow is detected before OT submission. Preserve all
        # world/character/effect producers; isolate only the packet consumer.
        self.bridge('DrawOTag',lambda *_:self.ret())
        self.bridge('game3ds_player_observe',self.player)
        self.bridge('game3ds_gpu_resolve',lambda *_:self.ret(1))
        self.uc.hook_add(UC_HOOK_CODE,self.tick,begin=game.symbols['GameState_InGame_Update'],end=game.symbols['GameState_InGame_Update'])
        self.uc.hook_add(UC_HOOK_CODE,self.packet,begin=game.symbols['game3ds_packet_observe'],end=game.symbols['game3ds_packet_observe'])
        self.uc.hook_add(UC_HOOK_MEM_WRITE,self.cursor,begin=game.symbols['GsOUT_PACKET_P'],end=game.symbols['GsOUT_PACKET_P']+3)
    def cursor(self,u,access,address,size,value,_):
        delta=value-self.last;self.last=value
        if 0<delta<100000:
            lr=u.reg_read(UC_ARM_REG_PC);i=bisect.bisect_right(addresses,lr)-1
            self.producers[names[i][1]]+=delta
            if self.frame_base and value-self.frame_base>131072 and self.legacy_crossing is None:
                self.legacy_crossing=dict(producer=names[i][1],pc=hex(lr),bytes=value-self.frame_base)
    def player(self,x,z,yaw,state):
        self.pose=[state,*struct.unpack('<4I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),16))]
        if state==10 and self.pose[-1]==5:self.window_seen=True
        if self.window_seen and state==0:self.after_window+=1
        self.ret()
    def tick(self,*_):
        self.ticks+=1;self.producers.clear();self.legacy_crossing=None
        self.frame_base=struct.unpack('<I',self.uc.mem_read(game.symbols['GsOUT_PACKET_P'],4))[0]
        if self.ticks%50==0:print('window tick',self.ticks,self.pose,flush=True)
        if self.ticks>=int(os.environ.get('SH_WINDOW_TICKS','850')) or self.after_window>=20:self.stopped=True;self.uc.emu_stop()
    def packet(self,u,*_):
        used=u.reg_read(UC_ARM_REG_R0);capacity=u.reg_read(UC_ARM_REG_R1)
        row=dict(tick=self.ticks,used=used,capacity=capacity,pose=self.pose,producers=self.producers.most_common(12),
            first_128k_crossing=self.legacy_crossing)
        if used>131072:
            cursor=struct.unpack('<I',u.mem_read(game.symbols['GsOUT_PACKET_P'],4))[0]
            at=cursor-used;packets=0
            while at<cursor:
                length=u.mem_read(at+4,1)[0];at+=8+4*length;packets+=1
            row.update(packet_walk_exact=at==cursor,packet_count=packets,
                retail_tag_equivalent=used-4*packets if at==cursor else None)
        self.rows.append(row)
    def vblank(self,*_):
        self.frames+=int(os.environ.get('SH_WINDOW_VBLANKS','1')) if self.state==11 else 1
        self.title_age=self.title_age+1 if self.state==7 else 0;self.ret(0)
    def read_pad(self,*_):
        if self.state==11:self.ret(2 if self.ticks%20<2 else 0)
        else:super().read_pad()

r=WindowRunner();result=game.run(r,seconds=900)
report=dict(scope=__doc__,run=result,rows=r.rows,window_seen=r.window_seen,after_window=r.after_window,
    vblanks=int(os.environ.get('SH_WINDOW_VBLANKS','1')),elf_sha256=hashlib.sha256(game.runtime.ELF).hexdigest(),hardware_accepted=False)
dest=game.port/'reports'/os.environ.get('SH_WINDOW_REPORT','stage10-window-runtime.json')
dest.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(run=result,peak=max(r.rows,key=lambda x:x['used']) if r.rows else None),indent=2))
if not os.environ.get('SH_WINDOW_EXPECT_FAILURE'):
    assert not result['failure'] and not result['invalid'] and not result['exception'],result
    assert r.window_seen and r.after_window>=20,'Window itinerary did not finish'
