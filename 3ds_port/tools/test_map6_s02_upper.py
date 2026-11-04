"""Exercise the upper lighthouse and Alessa scene with original disc assets.

CPU diagnostic only: GPU submission, cache service and audio are host boundaries.
The fixture starts at the original upper-room entrance with flag 409 set.
"""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port / 'tools/test_block3_runtime.py').read_text().split('\ncases = [', 1)[0]
exec(compile(source, str(port / 'tools/test_block3_runtime.py'), 'exec'))

class UpperLighthouse(Entry):
    def __init__(self):
        super().__init__(35, 'map6_s02', 3, (350, 352, 358, 391, 402, 403, 409, 423, 424))
        self.opened = self.scene_calls = self.alessa_calls = self.gpu_flushes = 0
        self.bridge('GSPGPU_FlushDataCache', self.gpu_flush)
        # The runner has no 3DS TLS; use the same newlib boundary as the
        # established playtest regression fixture.
        if '__syscall_getreent' in game.symbols:
            self.bridge('__syscall_getreent', lambda *_: self.ret(0x20004000))
        for symbol, attr in [('stage4_fs_open_read_tim', 'opened'),
                             ('map6_s02_func_800CF0B8', 'scene_calls'),
                             ('map6_s02_Alessa_Update', 'alessa_calls')]:
            self.uc.hook_add(UC_HOOK_CODE, self.count(attr), begin=game.symbols[symbol], end=game.symbols[symbol])
    def count(self, attr):
        def hook(*_):
            setattr(self, attr, getattr(self, attr) + 1)
        return hook
    def gpu_flush(self, *_):
        self.gpu_flushes += 1
        self.ret(0)
    def read_pad(self, *_):
        if self.map == 35:
            self.ret(2 if self.frames % 20 == 0 else 0)
        else:
            super().read_pad()
    def tick(self, uc, *_):
        if self.map != self.wanted:
            return
        self.ticks += 1
        save = struct.unpack('<I', uc.mem_read(game.symbols['g_SavegamePtr'], 4))[0]
        word = struct.unpack('<I', uc.mem_read(save + 0x168 + (410 // 32) * 4, 4))[0]
        disabled = uc.mem_read(game.symbols['g_Player_DisableControl'], 1)[0]
        self.ready = self.ready + 1 if word & (1 << (410 % 32)) and not disabled else 0
        if self.ready >= 21:
            self.stopped = True
            uc.emu_stop()

r = UpperLighthouse()
result = game.run(r, seconds=300)
result.update(observed_map=r.map, room=r.room, update_calls=r.ticks,
              control_ticks=r.ready, direct_tim_opens=r.opened,
              alessa_scene_calls=r.scene_calls, alessa_updates=r.alessa_calls,
              gpu_flush_calls=r.gpu_flushes)
print(json.dumps(result, indent=2), flush=True)
if (result['failure'] or result['invalid'] or result['exception'] or r.map != 35 or
        r.ready < 21 or not r.opened or not r.scene_calls or not r.alessa_calls):
    raise SystemExit(1)
