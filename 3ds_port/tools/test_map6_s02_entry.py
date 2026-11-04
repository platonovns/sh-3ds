"""Seed a post-boat lighthouse entry using original disc assets and game ELF."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port / 'tools/test_block3_runtime.py').read_text().split('\ncases = [', 1)[0]
exec(compile(source, str(port / 'tools/test_block3_runtime.py'), 'exec'))
class LighthouseEntry(Entry):
    def __init__(self):
        super().__init__(35, 'map6_s00', 8, (350, 352, 358, 402, 403, 423, 424))
        self.reent_caller = None
        self.snprintf_caller = None
        self.recoverable = []
        self.bridge('game3ds_recoverable', self.record_recoverable)
        if '__getreent' in game.symbols:
            self.uc.hook_add(UC_HOOK_CODE, self.track_reent, begin=game.symbols['__getreent'], end=game.symbols['__getreent'])
        if 'snprintf' in game.symbols:
            self.uc.hook_add(UC_HOOK_CODE, self.track_snprintf, begin=game.symbols['snprintf'], end=game.symbols['snprintf'])
    def track_reent(self, uc, *_):
        from unicorn.arm_const import UC_ARM_REG_LR
        self.reent_caller = hex(uc.reg_read(UC_ARM_REG_LR))
    def track_snprintf(self, uc, *_):
        from unicorn.arm_const import UC_ARM_REG_LR
        self.snprintf_caller = hex(uc.reg_read(UC_ARM_REG_LR))
    def record_recoverable(self, operation, detail, *_):
        message = bytes(self.uc.mem_read(operation, 64)).split(b'\0')[0].decode()
        self.recoverable.append((message, detail))
        self.ret()
r = LighthouseEntry()
result = game.run(r, seconds=180)
result.update(observed_map=r.map, room=r.room, update_calls=r.ticks, control_ticks=r.ready, recoverable=r.recoverable)
if result['exception']:
    from unicorn.arm_const import UC_ARM_REG_LR
    result['lr'] = hex(r.uc.reg_read(UC_ARM_REG_LR))
    result['reent_caller'] = r.reent_caller
    result['snprintf_caller'] = r.snprintf_caller
print(json.dumps(result, indent=2), flush=True)
unexpected = [x for x in r.recoverable if x != ('FMV audio', 0)]
if result['failure'] or result['invalid'] or result['exception'] or unexpected or r.map != 35 or r.ticks < 21 or r.ready < 21:
    raise SystemExit(1)
