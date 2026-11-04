#!/usr/bin/env python3
"""CPU regression of original boot/menu/New Game using real BIN reads.

SDK IO, vblank and GPU submission are host boundaries. Two pad pulses exercise
the original menu; no game-state/resource/geometry changes are injected.
This is a CPU diagnostic, never Level B visual or hardware acceptance.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import time
import run_arm_tim as runtime
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R0,UC_ARM_REG_R1

port=runtime.PORT
game_elf=Path(os.environ.get('SH_GAME_ELF',str(port/'silenthill_game.elf')))
runtime.ELF=game_elf.read_bytes()
nm=subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-nm'),'-n',str(game_elf)],text=True)
runtime.SYMBOLS=symbols={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3 and s[0]!='w'}
runtime.PHOFF=struct.unpack_from('<I',runtime.ELF,28)[0]
runtime.PHSIZE,runtime.PHCOUNT=struct.unpack_from('<HH',runtime.ELF,42)

class GameRunner(runtime.Runner):
    def bridge(self,name,fn):
        if name not in symbols and name in ('mallinfo','linearSpaceFree','C3D_TexBind','__errno','game3ds_gpu_dirty'):return
        # Subclass fixtures replace boundaries. Stacking both hooks at one PC
        # let the old ret(0) overwrite R0 before the observer read its argument
        # (Cafe map 1 was recorded as map 0, making completion unreachable).
        if not hasattr(self,'named_hooks'):self.named_hooks={}
        if name in self.named_hooks:
            old=self.named_hooks.pop(name);self.uc.hook_del(old);self.hooks.remove(old)
        super().bridge(name,fn)
        self.named_hooks[name]=self.hooks[-1]
    def fopen(self,path,mode,*_):
        name=bytes(self.uc.mem_read(path,1024)).split(b'\0')[0].decode()
        assert name in ('sdmc:/3ds/silenthill/sh1.bin','sdmc:/3ds/silenthill/sh1.cue'),name
        f=(runtime.ROOT/'sh1_data'/name.rsplit('/',1)[1]).open('rb')
        h=0x21000000+self.next_handle*0x1000;self.next_handle+=1
        self.handles[h]=f;self.ret(h)
    def __init__(self):
        super().__init__()
        self.state=None;self.step=None;self.frames=0;self.title_age=0
        self.events=[];self.failure=None;self.draw_count=0;self.stopped=False
        self.frame_draws=0;self.max_draws=0;self.scene_frame=None
        self.last_packets=[];self.texture_pairs=set();self.max_texture_pairs=0
        self.bridge('printf',lambda *_:self.ret(0))
        if os.environ.get('SH_STAGE9_REGRESSION')=='1':
            # Graphics/gameplay regression isolation, matching accepted R2's
            # silent boundary. The native audio path has its own ARM tests.
            for name in ('SD_Init','SD_Call','Sd_TaskPoolExecute','Sd_PlaySfx','Sd_SfxStop',
                         'Sd_SfxAttributesUpdate','Sd_XaPreLoadAudioPreTaskAdd','SpuInit',
                         'func_8005DC1C','func_8005DC3C','func_8005DD44','func_8005DE0C',
                         'Sfx_WithFalloffAndPitchPlay','Sd_SetVolume','Sd_AudioStreamingCheck'):
                if name in symbols:self.bridge(name,lambda *_:self.ret(0))
        if 'game_card_mount' in symbols:self.bridge('game_card_mount',lambda *_:self.ret(0))
        self.bridge('game3ds_gpu_sync',self.sync)
        if 'game3ds_feedback_capture' in symbols:self.bridge('game3ds_feedback_capture',lambda *_:self.ret())
        # Optional backend prefetch is covered by cache ARM/byte tests and
        # actual Azahar. Keep this original CPU-path fixture disk-backed.
        self.bridge('stage4_fs_game_preload',lambda *_:self.ret())
        self.bridge('game3ds_gpu_dirty',lambda *_:self.ret())
        self.bridge('game3ds_gpu_dirty_rect',lambda *_:self.ret())
        self.bridge('game3ds_ticks',lambda *_:(self.uc.reg_write(UC_ARM_REG_R1,0),self.ret(0)))
        # CPU-only fixture advances its independent clock at each synthetic wait.
        self.bridge('game3ds_vblank_clock',lambda *_:self.ret(self.frames))
        self.bridge('game3ds_hblank_clock',lambda *_:self.ret(self.frames*263))
        if 'game3ds_q12_clock' in symbols:self.bridge('game3ds_q12_clock',lambda *_:self.ret(self.frames*4096//60))
        self.bridge('game3ds_primitive_ticks',lambda *_:self.ret())
        self.bridge('game3ds_player_observe',lambda *_:self.ret())
        self.bridge('game3ds_animation_observe',lambda *_:self.ret())
        if 'game3ds_map_observe' in symbols:self.bridge('game3ds_map_observe',lambda *_:self.ret())
        if 'game3ds_media_skip' in symbols:self.bridge('game3ds_media_skip',lambda *_:self.ret())
        self.bridge('game3ds_timestep',lambda *_:self.ret())
        if 'game3ds_status_begin' in symbols:self.bridge('game3ds_status_begin',lambda *_:self.ret())
        self.bridge('game3ds_gpu_rect',self.draw)
        self.bridge('game3ds_observe',self.observe)
        self.bridge('game3ds_progress',self.progress)
        self.bridge('game3ds_wait_vblank',self.vblank)
        self.bridge('game3ds_read_pad',self.read_pad)
        if 'game3ds_read_analog' in symbols:
            self.bridge('game3ds_read_analog',lambda *args:([self.uc.mem_write(a,b'\0'*4) for a in args],self.ret()))
        self.bridge('game3ds_halt',self.halt)
        def packet_trace(uc,address,size,arg):
            ptr=uc.reg_read(UC_ARM_REG_R0)
            try:
                head=bytes(uc.mem_read(ptr,8));length=struct.unpack_from('<H',head,4)[0]
                payload=bytes(uc.mem_read(ptr+8,min(length,16)*4))
                self.last_packets=(self.last_packets+[{'ptr':hex(ptr),'length':length,
                    'words':[hex(x) for x in struct.unpack('<'+'I'*(len(payload)//4),payload)]}])[-8:]
            except Exception:pass
        self.uc.hook_add(UC_HOOK_CODE,packet_trace,begin=symbols['DrawPrim'],end=symbols['DrawPrim'])
    def event(self,value):
        self.events=(self.events+[value])[-24:]
        (port/'reports/game-path-arm-live.json').write_text(json.dumps({
            'frames':self.frames,'state':self.state,'step':self.step,
            'draw_packets':self.draw_count,'events':self.events},indent=2)+'\n')
    def observe(self,state,step,fs,sub):
        if (state,step)!=(self.state,self.step):self.event({'state':state,'step':step,'frame':self.frames})
        self.state=state;self.step=step;self.ret()
        if state in (11,12) and self.scene_frame is None:self.scene_frame=self.frames
    def progress(self,ptr,detail,*_):
        self.event({'phase':bytes(self.uc.mem_read(ptr,128)).split(b'\0')[0].decode(),'detail':detail,'frame':self.frames});self.ret()
    def draw(self,ptr,count,page,clut):
        self.draw_count+=1;self.frame_draws+=1
        if struct.unpack('<I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),4))[0]:self.texture_pairs.add((page,clut))
        self.ret()
    def sync(self,*_):
        self.max_draws=max(self.max_draws,self.frame_draws)
        self.max_texture_pairs=max(self.max_texture_pairs,len(self.texture_pairs))
        self.frame_draws=0;self.texture_pairs.clear();self.ret()
    def vblank(self,*_):
        self.frames+=1
        self.title_age=self.title_age+1 if self.state==7 else 0
        if self.frames>=3500 or self.scene_frame is not None and self.frames>=self.scene_frame+3:
            self.stopped=True;self.uc.emu_stop()
        self.ret(0)
    def read_pad(self,*_):
        self.ret(2 if self.title_age in (90,150) else 0) # Physical 3DS B, original Joy path.
    def halt(self,code,ptr,detail,*_):
        self.failure={'code':code,'operation':bytes(self.uc.mem_read(ptr,128)).split(b'\0')[0].decode(),'detail':detail}
        self.stopped=True;self.uc.emu_stop()

def run(r, seconds=180):
    u=r.uc
    u.reg_write(UC_ARM_REG_SP,0x1001ffc0);u.reg_write(UC_ARM_REG_LR,0x30000000)
    u.reg_write(UC_ARM_REG_R0,symbols['fs_result']);u.reg_write(UC_ARM_REG_R1,symbols['vram'])
    start=time.monotonic();error=None
    try:
        pc=symbols['game3ds_run']
        while not r.stopped and time.monotonic()-start<seconds:
            u.emu_start(pc,0x30000000,timeout=30_000_000,count=200_000_000)
            pc=u.reg_read(UC_ARM_REG_PC)
            if pc==0x30000000:break
    except Exception as e:error=repr(e)
    finally:
        for f in r.handles.values():f.close()
    return {'context':'CPU diagnostic, original MainLoop; no visual/hardware acceptance',
        'frames':r.frames,'state':r.state,'step':r.step,'draw_packets':r.draw_count,
        'max_draws_per_submission':r.max_draws,'first_map_state_frame':r.scene_frame,'last_events':r.events,
        'max_texture_pairs_per_submission':r.max_texture_pairs,'last_packets':r.last_packets,
        'failure':r.failure,'invalid':r.invalid,'exception':error,'pc':hex(u.reg_read(UC_ARM_REG_PC)),
        'elapsed_seconds':round(time.monotonic()-start,3)}

if __name__=='__main__':
    result=run(GameRunner())
    print(json.dumps(result,indent=2))
    if result['exception'] or result['invalid'] or result['failure']:raise SystemExit(1)
