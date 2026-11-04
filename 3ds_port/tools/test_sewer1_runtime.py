"""Short real-disc seeded map updates; not a continuous route or hardware test."""
from pathlib import Path
import os, sys, struct, json, hashlib

port = Path(__file__).resolve().parents[1]
elf = Path(os.environ.get('SH_SEWER1_ELF', str(port / 'build/sewer1-compile-probe/sewer1-probe.elf')))
os.environ['SH_BLOCK3_ELF'] = str(elf)
# Reuse the existing runner and its SDK boundaries, without executing its cases.
exec((port / 'tools/test_block3_runtime.py').read_text().split('\ncases = [', 1)[0])

class SewerEntry(Entry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hanged_updates = 0
        self.creeper_updates = 0
        for symbol, attr in [('map5_s00_HangedScratcher_Update', 'hanged_updates'), ('map5_s00_Creeper_Update', 'creeper_updates')]:
            def observe(uc, address, size, userdata, attr=attr):
                setattr(self, attr, getattr(self, attr) + 1)
            self.uc.hook_add(UC_HOOK_CODE, observe, begin=game.symbols[symbol], end=game.symbols[symbol])
    def place(self, uc, *_):
        if not self.placed:
            self.placed = True
            point = game.symbols[self.pose_map + '_MAP_POINTS'] + self.point * 12
            uc.reg_write(UC_ARM_REG_R0, point)

cases = [
    ('waterworks', 10, 'map2_s02', 33, (350, 352, 193)),
    ('sewer_entry', 29, 'map2_s00', 66, (350, 352, 193)),
    ('early', 29, 'map5_s00', 6, (350, 352, 193, 355)),
    ('mid_key', 29, 'map5_s00', 9, (350, 352, 193, 355, 353, 1371)),
    ('hanged', 29, 'map5_s00', 30, (350, 352, 193, 355, 353, 1371, 354)),
    ('creeper', 29, 'map5_s00', 11, (350, 352, 193, 355, 353, 1371, 354)),
    ('exit', 29, 'map5_s00', 14, (350, 352, 193, 355, 353, 1371, 354, 1391)),
    ('resort', 30, 'map5_s00', 31, (350, 352, 193, 355, 353, 1371, 354, 1391, 358)),
]
if len(sys.argv) > 1:
    cases = [c for c in cases if c[0] in sys.argv[1:]]
    if not cases: raise SystemExit('Unknown fixture')
results = []
for label, wanted, pose, point, flags in cases:
    r = SewerEntry(wanted, pose, point, flags, require_control=(label == 'resort'), walk=(label == 'resort'))
    result = game.run(r, seconds=180)
    result.update(label=label, map=wanted, pose_source=pose, pose_index=point,
                  observed_map=r.map, room=r.room, update_calls=r.ticks, control_ticks=r.ready,
                  walk_start=r.walk_start, walk_end=r.walk_end, hanged_updates=r.hanged_updates, creeper_updates=r.creeper_updates)
    results.append(result)
    print(json.dumps(result, indent=2), flush=True)
    if result['failure'] or result['invalid'] or result['exception'] or r.ticks < 21: break
passed = len(results) == len(cases) and all(not x['failure'] and not x['invalid'] and not x['exception'] and x['update_calls'] >= 21 for x in results)
passed = passed and all(x['control_ticks'] >= 60 and x['walk_start'] and x['walk_end'] and (x['walk_start'][0], x['walk_start'][2]) != (x['walk_end'][0], x['walk_end'][2]) for x in results if x['label'] == 'resort')
passed = passed and all(x['hanged_updates'] > 0 for x in results if x['label'] == 'hanged')
passed = passed and all(x['creeper_updates'] > 0 for x in results if x['label'] == 'creeper')
record = dict(status='PASS' if passed else 'FAIL', scope=__doc__, elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(), results=results)
(elf.parent / ('runtime-' + ('-'.join(sys.argv[1:]) if len(sys.argv) > 1 else 'all') + '.json')).write_text(json.dumps(record, indent=2) + '\n')
if not passed: raise SystemExit(1)
