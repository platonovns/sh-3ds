"""Original main/Boot warning hand-off retains artwork under the original fade."""
import hashlib,json,struct
import run_arm_game as game
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP
class WarningRunner(game.GameRunner):
    def __init__(self):
        super().__init__();self.boot_calls=0;self.warning_frames={};self.startup_art=set();self.boot_art=set()
        self.title_load=None;self.warning_after_title=[]
        self.uc.hook_add(UC_HOOK_CODE,lambda *_:setattr(self,'boot_calls',self.boot_calls+1),
            begin=game.symbols['GameState_Boot_Update'],end=game.symbols['GameState_Boot_Update'])
        def load(*_):
            status=struct.unpack('<I',self.uc.mem_read(game.symbols['g_Screen_FadeStatus'],4))[0]
            self.title_load=dict(boot_call=self.boot_calls,fade_status=status,fade_finished=(status&7)==5)
        # Observe actual calls; keep the original FS/title loading implementation.
        self.uc.hook_add(UC_HOOK_CODE,load,begin=game.symbols['GameFs_TitleGfxLoad'],end=game.symbols['GameFs_TitleGfxLoad'])
        def background(u,*_):
            if self.title_load and u.reg_read(game.runtime.UC_ARM_REG_R0)==game.symbols['g_MainImg0']:
                self.warning_after_title.append(self.boot_calls)
        self.uc.hook_add(UC_HOOK_CODE,background,begin=game.symbols['Screen_BackgroundImgDraw'],end=game.symbols['Screen_BackgroundImgDraw'])
    def draw(self,ptr,count,page,clut):
        tex,blend=struct.unpack('<2I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),8))
        if tex and (not self.boot_calls or self.state==0):
            v=struct.unpack('<'+'f'*(count*9),self.uc.mem_read(ptr,count*36))
            signature=(page,clut,v)
            (self.boot_art if self.boot_calls else self.startup_art).add(signature)
        if self.boot_calls and self.state==0:
            tex,blend=struct.unpack('<2I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),8))
            row=self.warning_frames.setdefault(self.boot_calls,dict(sprites=0,fade=[]))
            if tex:row['sprites']+=1
            elif blend==3:
                v=struct.unpack('<'+'f'*(count*9),self.uc.mem_read(ptr,count*36))
                row['fade'].append(v[5])
        return super().draw(ptr,count,page,clut)
    def read_pad(self,*_):self.ret(0)
    def vblank(self,*_):
        self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0
        if self.title_age>=3 or self.frames>4000:self.stopped=True;self.uc.emu_stop()
        self.ret(0)
r=WarningRunner();run=game.run(r,seconds=120)
assert r.state==7 and not run['failure'] and not run['invalid'] and not run['exception'],run
faded=[row for row in r.warning_frames.values() if row['fade']]
assert len(faded)>=3 and all(row['sprites']>=2 for row in faded),r.warning_frames
assert r.startup_art and r.startup_art==r.boot_art,'main/Boot environment, XY or UV changed'
levels=[max(row['fade']) for row in faded]
assert max(levels)>min(levels),levels
assert r.title_load and r.title_load['fade_finished'] and not r.warning_after_title,(r.title_load,r.warning_after_title)
report=dict(status='PASS',scope=__doc__,boot_frames=r.boot_calls,
    frames_with_artwork_and_subtractive_fade=len(faded),fade_levels=levels,
    boot_to_title=True,title_asset_handoff=r.title_load,no_warning_draw_after_title_upload=True,
    main_boot_identical_xy_uv=True,elf_sha256=hashlib.sha256(game.game_elf.read_bytes()).hexdigest(),
    hardware_acceptance=False)
(game.port/'reports/stage10-boot-warning-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
