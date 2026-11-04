"""Short ARM component checks for carousel progression and Cybil branches."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
out = port / 'build/map6-s04-checks'
out.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port/'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]', 1)[0]
source = source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/map6-s04-checks'")
source = source.replace("*(str(p) for p in objects),'-o',str(probe)",
                        "*(str(p) for p in objects), str(port/'build-game/memcard.o'), '-Wl,--allow-multiple-definition','-o',str(probe)")
exec(compile(source, str(port/'tools/test_block3_components.py'), 'exec'))

# The larval and Alessa tables are shared only where retail bytes match.
assert asset('map6_s04')[0xe81cc-0xc9578:0xe81cc-0xc9578+38*16] == asset('map1_s00')[0xda6c8-0xc9578:0xda6c8-0xc9578+38*16]
assert asset('map6_s04')[0xea9d8-0xc9578:0xea9d8-0xc9578+22*16] == asset('map3_s02')[0xd1b6c-0xc9578:0xd1b6c-0xc9578+22*16]
obj, fixture = out/'map6_s04_probe.o', out/'map6_s04_probe.elf'
p = subprocess.run([prefix+'gcc', *shlex.split(flags), '-c', str(port/'tests/map6_s04_probe.c'), '-o', str(obj)], capture_output=True, text=True)
if p.returncode: raise RuntimeError(p.stderr)
names = ('map6_s04_probe_entry', 'map6_s04_probe_events', 'map6_s04_probe_liquid', 'map6_s04_probe_save', 'map6_s04_probe_outcome')
subprocess.run([prefix+'gcc', '-nostdlib', '-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),
                *('-Wl,--undefined='+n for n in names), str(obj), str(port/'build-game/memcard.o'),
                '-Wl,--allow-multiple-definition', '-o', str(fixture)], check=True)
raw2 = fixture.read_bytes()
off2 = struct.unpack_from('<I', raw2, 28)[0]
size2, count2 = struct.unpack_from('<HH', raw2, 42)
for line in subprocess.check_output([prefix+'nm', '-n', str(fixture)], text=True).splitlines():
    p = line.split()
    if len(p) == 3 and p[2].startswith('map6_s04_probe_'): game.symbols[p[2]] = int(p[0], 16)
r = Chapter()
for i in range(count2):
    typ, pos, addr, _, length, _, _, _ = struct.unpack_from('<8I', raw2, off2+i*size2)
    if typ == 1 and length: r.uc.mem_write(addr, raw2[pos:pos+length])
r.reset('map6_s03', 36)
assert r.call('map6_s04_probe_entry') == 0
r.reset('map6_s04', 37)
assert r.call('alchemilla_probe_header') == 0
executable = {int(p[0], 16) for line in subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True).splitlines()
              if len(p := line.split()) == 3 and p[1] in ('T', 't', 'W', 'w')}
count = r.row()[0]
callbacks = struct.unpack('<'+'I'*count, r.uc.mem_read(game.symbols['alchemilla_probe_callbacks'], count*4))
assert all(not p or p in executable for p in callbacks)
assert r.call('map6_s04_probe_events') == 0
r.bridge('Game_TurnFlashlightOn', lambda *_: r.ret())
for near in (0, 1): assert r.call('map6_s04_probe_liquid', near) == 0, near
for name in ('map6_s04_func_800E7944', 'map6_s04_sharedFunc_800D2EF4_0_s00',
             'WorldGfx_PlayerPrevHeldItem', 'map6_s04_Player_ControlUnfreeze',
             'map6_s04_sharedFunc_800D88C0_0_s00', 'vcReturnPreAutoCamWork',
             'func_8008D448', 'Game_FlashlightAttributesFix', 'Chara_ModelCharaIdClear',
             'Sd_SfxStop', 'Model_AnimFlagsSet', 'SD_Call'):
    if name in game.symbols: r.bridge(name, lambda *_: r.ret())
for rescued in (0, 1): assert r.call('map6_s04_probe_outcome', rescued) == 0, rescued
for rescued in (0, 1): assert r.call('map6_s04_probe_save', rescued) == 0, rescued
print('MAP6_S04 ARM entry, event chain, Cybil branch triggers, Unknown Liquid and save roundtrips PASS')
