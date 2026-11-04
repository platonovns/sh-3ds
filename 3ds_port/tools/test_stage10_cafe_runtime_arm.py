"""Run the original Cafe loop from a development start, recording all GPU packets."""
import hashlib,json,os,struct
import run_arm_game as game
from unicorn import UC_HOOK_CODE
class CafeRunner(game.GameRunner):
    def __init__(self):
        super().__init__();self.game_ticks=0;self.halt_packet=None
        self.uc.hook_add(UC_HOOK_CODE,self.tick,begin=game.symbols['GameState_InGame_Update'],end=game.symbols['GameState_InGame_Update'])
    def tick(self,*_):
        self.game_ticks+=1
        if self.game_ticks>150:self.stopped=True;self.uc.emu_stop()
    def vblank(self,*_):
        self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0
        self.ret(0)
    def halt(self,*args):
        self.halt_packet=self.last_packets.copy();super().halt(*args)
r=CafeRunner();report=game.run(r,seconds=240)
report.update(game_ticks=r.game_ticks,halt_packets=r.halt_packet,
    elf_sha256=hashlib.sha256(game.game_elf.read_bytes()).hexdigest())
(game.port/'reports/stage10-cafe-runtime-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert r.game_ticks>=150 and not report['failure'] and not report['invalid'] and not report['exception'],report
