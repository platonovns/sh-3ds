"""ARM checks of the second sewer in the real game ELF; not a playthrough."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
out = port / 'build/map6-s03-checks'
out.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port / 'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]', 1)[0]
source = source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/map6-s03-checks'")
source = source.replace("*(str(p) for p in objects),'-o',str(probe)",
                        "*(str(p) for p in objects), str(port/'build-game/memcard.o'), '-Wl,--allow-multiple-definition','-o',str(probe)")
exec(compile(source, str(port / 'tools/test_block3_components.py'), 'exec'))

# The native animation tables are reused only after comparing the retail data.
assert asset('map6_s03')[0xd95f4-0xc9578:0xd9bf4-0xc9578] == asset('map5_s02')[0xd7274-0xc9578:0xd7874-0xc9578]
assert asset('map6_s03')[0xdb1c0-0xc9578:0xdb1c0-0xc9578+54*16] == asset('map5_s00')[0xd91a0-0xc9578:0xd91a0-0xc9578+54*16]
movie = re.search(r'\{\s*(0x[0-9a-fA-F]+),\s*172.*// XA/M9_01730\s*$', ft, re.M)
assert movie
with (root.parent/'silent-hill-decomp/sh1_data/sh1.bin').open('rb') as disc:
    disc.seek(int(movie[1], 16)*2352)
    assert len(disc.read(2352)) == 2352

obj = out/'map6_s03_probe.o'
fixture = out/'map6_s03_probe.elf'
p = subprocess.run([prefix+'gcc', *shlex.split(flags), '-c', str(port/'tests/map6_s03_probe.c'), '-o', str(obj)], capture_output=True, text=True)
if p.returncode:
    raise RuntimeError(p.stderr)
names = ('map6_s03_probe_entrance', 'map6_s03_probe_unlock_entrance', 'map6_s03_probe_edges', 'map6_s03_probe_save',
         'map6_s03_probe_enemy', 'map6_s03_probe_mumbler', 'map6_s03_probe_anim_reload', 'map6_s03_probe_map_granted')
subprocess.run([prefix+'gcc', '-nostdlib', '-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),
                *('-Wl,--undefined='+n for n in names), str(obj), str(port/'build-game/memcard.o'),
                '-Wl,--allow-multiple-definition', '-o', str(fixture)], check=True)
raw2 = fixture.read_bytes()
off2 = struct.unpack_from('<I', raw2, 28)[0]
size2, count2 = struct.unpack_from('<HH', raw2, 42)
for line in subprocess.check_output([prefix+'nm', '-n', str(fixture)], text=True).splitlines():
    p = line.split()
    if len(p) == 3 and p[2].startswith('map6_s03_probe_'):
        game.symbols[p[2]] = int(p[0], 16)
r = Chapter()
for i in range(count2):
    typ, pos, addr, _, length, _, _, _ = struct.unpack_from('<8I', raw2, off2+i*size2)
    if typ == 1 and length:
        r.uc.mem_write(addr, raw2[pos:pos+length])
r.reset('map6_s00', 33)
assert r.call('map6_s03_probe_entrance') == 0
r.bridge('Gfx_MapMsg_Draw', lambda *_: r.ret(1))
assert r.call('map6_s03_probe_unlock_entrance') == 0
r.reset('map6_s03', 36)
assert r.call('alchemilla_probe_header') == 0
executable = {int(p[0], 16) for line in subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True).splitlines()
              if len(p := line.split()) == 3 and p[1] in ('T', 't', 'W', 'w')}
count = r.row()[0]
callbacks = struct.unpack('<'+'I'*count, r.uc.mem_read(game.symbols['alchemilla_probe_callbacks'], count*4))
assert all(not p or p in executable for p in callbacks), callbacks
hdr = struct.unpack('<I', r.uc.mem_read(game.symbols['g_pMapOverlayHeader'], 4))[0]
fields = [4, 12, 16, 60, 64, 68, 72, 96, 100, 104, 108, 112, 116, 120, 128, 132, 140, 144, 152, 156]
fields.extend(range(0xa4, 0x184, 4))
fields.extend(range(0x194, 0x248, 4))
for offset in fields:
    ptr = struct.unpack('<I', r.uc.mem_read(hdr+offset, 4))[0]
    assert not ptr or ptr in executable, (hex(offset), hex(ptr))
assert r.call('map6_s03_probe_edges') == 0
assert r.call('map6_s03_probe_anim_reload') == 0
for phase in range(16):
    assert r.call('map6_s03_probe_save', phase) == 0, phase
for lethal in (0, 1):
    r.reset('map6_s03', 36)
    assert r.call('map6_s03_probe_enemy', lethal) == 0, lethal
    r.reset('map6_s03', 36)
    assert r.call('map6_s03_probe_mumbler', lethal) == 0, lethal
r.reset('map6_s03', 36)
r.call('alchemilla_probe_fmv', 3)
assert r.movies[-1] == (2063, 172) and r.call('alchemilla_probe_flag', 438) == 1
for event, flag in ((4, 431), (6, 433)):
    r.reset('map6_s03', 36)
    r.call('alchemilla_probe_event', event, 6)
    assert r.call('alchemilla_probe_flag', flag) == 1, flag
for event, item, quantity in ((0, 32, 1), (1, 192, 15), (2, 32, 1)):
    r.reset('map6_s03', 36)
    r.call('alchemilla_probe_pickup', event, 2)
    r.call('alchemilla_probe_pickup', event, 3)
    assert r.call('alchemilla_probe_count', item) == quantity, (event, item)
r.reset('map6_s03', 36)
r.bridge('Screen_BackgroundImgDraw', lambda *_: r.ret())
r.call('alchemilla_probe_pickup', 12, 4)
assert r.call('map6_s03_probe_map_granted') == 0
print('MAP6_S03 entrance, callbacks, transitions, flags, pickups, animation, combat, FMV API and 16 save roundtrips PASS')
