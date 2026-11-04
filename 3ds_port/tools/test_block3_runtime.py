"""Short original-disc map initialization/update diagnostics, not a playthrough.

Each case starts from a nearby save-like fixture. SDK, GPU and audio boundaries
are those of run_arm_game; no hardware, visuals, or full chapter acceptance.
"""
from pathlib import Path
import hashlib, json, os, struct, sys

port = Path(__file__).resolve().parents[1]
root = port.parent
elf = Path(os.environ.get('SH_BLOCK3_ELF', str(port / 'build/block3-compile-probe/block3-probe.elf')))
os.environ['SH_GAME_ELF'] = str(elf)
os.environ['SH_STAGE9_REGRESSION'] = '1'
sys.path.insert(0, str(root.parent / '.toolchain/python-deps'))
import run_arm_game as game
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0

# The unmodified runner reads only sh1.bin/cue through this root; it does not
# write a memory card. The disc remains in the user's original data directory.
game.runtime.ROOT = root.parent / 'silent-hill-decomp'

class Entry(game.GameRunner):
    def __init__(self, wanted, pose_map, point, flags, require_control=False, walk=False):
        super().__init__()
        self.wanted, self.pose_map, self.point, self.flags = wanted, pose_map, point, flags
        self.require_control = require_control
        self.walk = walk
        self.walk_start = self.walk_end = None
        self.seeded = self.placed = False
        self.map = self.room = None
        self.ticks = self.ready = 0
        self.boss_updates = 0
        self.bad_dynamic_callbacks = []
        self.lisa_scene_updates = 0
        self.uc.hook_add(UC_HOOK_CODE, self.seed, begin=game.symbols['GameBoot_MapLoad'], end=game.symbols['GameBoot_MapLoad'])
        self.uc.hook_add(UC_HOOK_CODE, self.place, begin=game.symbols['Chara_PositionSet'], end=game.symbols['Chara_PositionSet'])
        self.uc.hook_add(UC_HOOK_CODE, self.tick, begin=game.symbols['GameState_InGame_Update'], end=game.symbols['GameState_InGame_Update'])
        boss = {25:'map4_s03_Twinfeeler_Update',27:'map4_s05_Floatstinger_Update'}.get(wanted)
        if boss:
            self.uc.hook_add(UC_HOOK_CODE, self.boss_tick, begin=game.symbols[boss], end=game.symbols[boss])
        if wanted == 26:
            lisa=game.symbols['map4_s04_func_800D1910']
            self.uc.hook_add(UC_HOOK_CODE,self.lisa_tick,begin=lisa,end=lisa)
        self.bridge('game3ds_map_observe', self.map_observe)

    def seed(self, uc, *_):
        if self.seeded:
            return
        self.seeded = True
        save = struct.unpack('<I', uc.mem_read(game.symbols['g_SavegamePtr'], 4))[0]
        uc.mem_write(save + 0xa4, bytes([self.wanted]))
        for flag in (132,134,146,164,165,166,176,179,181,182,195,196,197,198,210,211,224,237,238,294,295,296,297) + self.flags:
            p = save + 0x168 + (flag // 32) * 4
            word = struct.unpack('<I', uc.mem_read(p, 4))[0] | (1 << (flag % 32))
            uc.mem_write(p, struct.pack('<I', word))
        uc.reg_write(UC_ARM_REG_R0, self.wanted)

    def place(self, uc, *_):
        if not self.placed:
            self.placed = True
            point = game.symbols[self.pose_map + '_MAP_POINTS'] + self.point * 12
            if self.require_control:
                # Original MAP4_S05 post-boss callback writes the current
                # arena position into point 14 immediately before transition.
                # This nearby fixture substitutes a plausible arena position;
                # the retail table's static point 14 is only a zero placeholder.
                uc.mem_write(point,struct.pack('<i',-118*4096))
                uc.mem_write(point+8,struct.pack('<i',108*4096))
            uc.reg_write(UC_ARM_REG_R0, point)

    def map_observe(self, mapidx, room, *_):
        self.map, self.room = mapidx, room
        self.ret()

    def boss_tick(self, uc, *_):
        self.boss_updates += 1
        if self.wanted == 25 and self.boss_updates > 1:
            # Twinfeeler_Init clears retail overlay data before the update
            # loop writes any native callbacks into these two work arrays.
            for symbol, count, stride, offset, allowed in [
                ('map4_s03_D_800DF580',16,0xd8,0xc8,('map4_s03_func_800D19F0',)),
                ('map4_s03_D_800E0930',3,0x1c,0x18,('Map4S03_Callback3114','Map4S03_Callback326C'))]:
                valid = {0, *(game.symbols[name] for name in allowed)}
                base = game.symbols[symbol]
                for i in range(count):
                    ptr = int.from_bytes(uc.mem_read(base+i*stride+offset,4),'little')
                    if ptr not in valid:
                        self.bad_dynamic_callbacks.append((symbol,i,hex(ptr)))

    def lisa_tick(self, uc, *_):
        self.lisa_scene_updates += 1

    def tick(self, uc, *_):
        if self.map != self.wanted:
            return
        self.ticks += 1
        disabled = uc.mem_read(game.symbols['g_Player_DisableControl'], 1)[0]
        state = int.from_bytes(uc.mem_read(game.symbols['g_SysWork'] + 8, 4), 'little')
        self.ready = self.ready + 1 if not disabled and state == 0 else 0
        if self.walk and self.ready >= 21:
            pos = struct.unpack('<3i',uc.mem_read(game.symbols['g_SysWork']+0x4c+0x18,12))
            if self.walk_start is None:self.walk_start = pos
            self.walk_end = pos
        if (self.ready >= (60 if self.walk else 21) if self.require_control else self.ticks >= 21):
            self.stopped = True
            uc.emu_stop()

    def read_pad(self,*args):
        if self.walk and self.ready >= 21:
            self.ret(1 << 6)  # Physical 3DS D-pad up, through original input path.
        else:
            super().read_pad(*args)

    def vblank(self, *_):
        self.frames += 1
        self.title_age = self.title_age + 1 if self.state == 7 else 0
        self.ret()

cases = [
    ('antique', 23, 'map2_s02', 8, ()),
    ('otherworld', 24, 'map4_s01', 9, (306, 337, 338, 308)),
    ('mall', 25, 'map4_s02', 31, (306, 337, 338, 308, 319)),
    ('twinfeeler', 25, 'map4_s03', 1, (306, 337, 338, 308, 319, 320, 321, 323, 324)),
    ('lisa', 26, 'map4_s02', 18, (306, 337, 338, 308)),
    ('lisa_story', 26, 'map4_s01', 14, (306, 337)),
    ('floatstinger', 27, 'map4_s04', 9, (306, 337, 338, 308, 339, 340)),
    ('floatstinger_arena', 27, 'map4_s05', 13, (306, 337, 338, 308, 339, 340, 346, 347, 348, 349)),
    ('returned_city', 12, 'map4_s05', 14, (306, 337, 338, 308, 319, 330, 331, 332, 339, 340, 348, 350, 352)),
    ('returned_walk', 12, 'map4_s05', 14, (306, 337, 338, 308, 319, 330, 331, 332, 339, 340, 348, 350, 352)),
]
if len(sys.argv) > 1:
    cases = [case for case in cases if case[0] in sys.argv[1:]]
    if not cases:
        raise SystemExit('Unknown fixture')
results = []
for label, wanted, pose, point, flags in cases:
    r = Entry(wanted, pose, point, flags, require_control=(label in ('returned_city','returned_walk')),
              walk=(label == 'returned_walk'))
    result = game.run(r, seconds=180)
    result.update(label=label, map=wanted, pose_source=pose, pose_index=point,
                  observed_map=r.map, room=r.room, update_calls=r.ticks, control_ticks=r.ready,
                  boss_update_calls=r.boss_updates, lisa_scene_calls=r.lisa_scene_updates,
                  bad_dynamic_callbacks=r.bad_dynamic_callbacks, walk_start=r.walk_start, walk_end=r.walk_end)
    results.append(result)
    print(json.dumps(result, indent=2), flush=True)
    if result['failure'] or result['invalid'] or result['exception'] or r.bad_dynamic_callbacks or r.ticks < 21:
        break
passed = len(results) == len(cases) and all(not x['failure'] and not x['invalid'] and not x['exception'] and not x['bad_dynamic_callbacks'] and x['update_calls'] >= 21 for x in results)
passed = passed and all(x['control_ticks'] >= 21 for x in results if x['label'] == 'returned_city')
passed = passed and all(x['control_ticks'] >= 60 and x['walk_start'] and x['walk_end'] and
                        (x['walk_start'][0],x['walk_start'][2]) != (x['walk_end'][0],x['walk_end'][2])
                        for x in results if x['label'] == 'returned_walk')
passed = passed and all(x['boss_update_calls'] > 0 for x in results if x['label'] in ('twinfeeler','floatstinger_arena'))
passed = passed and all(x['lisa_scene_calls'] > 0 for x in results if x['label'] == 'lisa_story')
record = dict(status='PASS' if passed else 'FAIL', scope=__doc__, elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(), results=results)
suffix = '-'.join(sys.argv[1:]) if len(sys.argv) > 1 else 'all'
(port / 'build/block3-compile-probe' / ('runtime-' + suffix + '.json')).write_text(json.dumps(record, indent=2) + '\n')
if not passed:
    raise SystemExit(1)
