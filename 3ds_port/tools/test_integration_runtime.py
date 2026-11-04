"""Short seeded CPU map entries against the integrated ELF and original disc."""
from pathlib import Path
import json, os, sys
port = Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF'] = str(port/'silenthill_game.elf')
exec((port/'tools/test_block3_runtime.py').read_text().split('\ncases = [', 1)[0])
cases = {
    'school': (3,'map1_s00',0,()),
    'post-school': (11,'map2_s00',106,()),
    'hospital': (15,'map2_s02',19,()),
    'sewer': (29,'map2_s00',66,(350,352,193)),
    'resort': (30,'map5_s00',31,(350,352,193,355,353,1371,354,1391,358)),
    'kaufmann': (31,'map5_s01',8,(350,352,193,355,358,378)),
    'boat': (34,'map6_s00',4,(350,352,193,355,358,402,403,423)),
    'boat-scene': (34,'map6_s00',6,(350,352,193,355,358,402,403,423)),
    'boat-end': (34,'map6_s00',4,(350,352,193,355,358,402,403,423,424,1024)),
}
label = sys.argv[1]
if label == 'map0':
    r = game.GameRunner()
    result = game.run(r, seconds=180)
    print(json.dumps(result, indent=2), flush=True)
    assert not result['failure'] and not result['invalid'] and not result['exception'] and result['first_map_state_frame'] is not None
    raise SystemExit(0)
r = Entry(*cases[label])
result = game.run(r, seconds=180)
if result['exception']:
    from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR
    sp = r.uc.reg_read(UC_ARM_REG_SP)
    result['lr'] = hex(r.uc.reg_read(UC_ARM_REG_LR))
    result['stack_words'] = [hex(x) for x in struct.unpack('<32I', r.uc.mem_read(sp, 128))]
result.update(label=label, observed_map=r.map, updates=r.ticks, control_ticks=r.ready,
              bad_dynamic_callbacks=r.bad_dynamic_callbacks)
print(json.dumps(result, indent=2), flush=True)
assert not result['failure'] and not result['invalid'] and not result['exception'] and not r.bad_dynamic_callbacks and r.ticks >= 21
