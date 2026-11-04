"""Seed the second-sewer entry using the original disc and game ELF."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
os.environ.setdefault('SH_BLOCK3_ELF', str(port/'silenthill_game.elf'))
source = (port/'tools/test_block3_runtime.py').read_text().split('\ncases = [', 1)[0]
exec(compile(source, str(port/'tools/test_block3_runtime.py'), 'exec'))

class SewerEntry(Entry):
    def __init__(self):
        super().__init__(36, 'map6_s00', 11, (350, 352, 358, 391, 402, 403, 410, 411, 423, 424, 425, 426), require_control=True)
        self.recoverable = []
        self.gpu_flush_calls = 0
        self.bridge('game3ds_recoverable', self.record_recoverable)
        # The offline runner has no libctru GPU service. Preserve the game
        # path and substitute only its cache-flush system call.
        self.bridge('GSPGPU_FlushDataCache', self.gpu_flush)
    def place(self, uc, *_):
        if not self.placed:
            self.placed = True
            uc.reg_write(UC_ARM_REG_R0, game.symbols['map6_s00_MAP_POINTS']+self.point*12)
    def read_pad(self, *_):
        if self.map == 36:
            self.ret((1 << 3) if self.frames % 8 == 0 else 0)
        else:
            super().read_pad()
    def record_recoverable(self, operation, detail, *_):
        message = bytes(self.uc.mem_read(operation, 64)).split(b'\0')[0].decode()
        self.recoverable.append((message, detail))
        self.ret()
    def gpu_flush(self, *_):
        self.gpu_flush_calls += 1
        self.ret(0)

r = SewerEntry()
result = game.run(r, seconds=240)
result.update(observed_map=r.map, room=r.room, update_calls=r.ticks,
              control_ticks=r.ready, recoverable=r.recoverable, gpu_flush_calls=r.gpu_flush_calls)
print(json.dumps(result, indent=2), flush=True)
unexpected = [x for x in r.recoverable if x != ('FMV audio', 0)]
if result['failure'] or result['invalid'] or result['exception'] or unexpected or r.map != 36 or r.ready < 21:
    raise SystemExit(1)
