"""ARM checks of the integrated lighthouse overlay; not a hardware playthrough."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
out = port / 'build/map6-s02-checks'
out.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port / 'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]', 1)[0]
source = source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/map6-s02-checks'")
source = source.replace("*(str(p) for p in objects),'-o',str(probe)",
                        "*(str(p) for p in objects), str(port/'build-game/memcard.o'), '-Wl,--allow-multiple-definition','-o',str(probe)")
exec(compile(source, str(port / 'tools/test_block3_components.py'), 'exec'))

for name in ('VIN/MAP6_S02.BIN', 'VIN/STF_ROLL.BIN', 'TIM/FONT24.TIM',
             'TIM/LHEFFECT.TIM', 'TIM/ENBAN.TIM', 'ANIM/UFO5.DMS',
             *('TIM/UFO%d.TIM' % i for i in range(1, 8))):
    match = re.search(r'\{\s*(0x[0-9a-fA-F]+),\s*(\d+).*// ' + re.escape(name) + r'\s*$', ft, re.M)
    assert match, name
    lba, length = int(match[1], 16), int(match[2]) * 256
    with (root.parent/'silent-hill-decomp/sh1_data/sh1.bin').open('rb') as disc:
        disc.seek(lba * 2352 + 24)
        assert len(disc.read(min(length, 2048))) == min(length, 2048), name

obj = out / 'map6_s02_probe.o'
fixture = out / 'map6_s02_probe.elf'
p = subprocess.run([prefix+'gcc', *shlex.split(flags), '-c', str(port/'tests/map6_s02_probe.c'), '-o', str(obj)], capture_output=True, text=True)
if p.returncode:
    raise RuntimeError(p.stderr)
names = ('map6_s02_probe_save', 'map6_s02_probe_edges', 'map6_s02_probe_entrance',
         'map6_s02_probe_lighthouse_complete')
subprocess.run([prefix+'gcc', '-nostdlib', '-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),
                *('-Wl,--undefined='+n for n in names), str(obj), str(port/'build-game/memcard.o'),
                '-Wl,--allow-multiple-definition', '-o', str(fixture)], check=True)
raw2 = fixture.read_bytes()
off2 = struct.unpack_from('<I', raw2, 28)[0]
size2, count2 = struct.unpack_from('<HH', raw2, 42)
for line in subprocess.check_output([prefix+'nm', '-n', str(fixture)], text=True).splitlines():
    parts = line.split()
    if len(parts) == 3 and parts[2].startswith('map6_s02_probe_'):
        game.symbols[parts[2]] = int(parts[0], 16)
r = Chapter()
for i in range(count2):
    typ, pos, addr, _, length, _, _, _ = struct.unpack_from('<8I', raw2, off2+i*size2)
    if typ == 1 and length:
        r.uc.mem_write(addr, raw2[pos:pos+length])
r.reset('map6_s00', 33)
assert r.call('map6_s02_probe_entrance') == 0
r.reset('map6_s02', 35)
assert r.call('alchemilla_probe_header') == 0
executable = set()
for line in subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True).splitlines():
    parts = line.split()
    if len(parts) == 3 and parts[1] in ('T', 't', 'W', 'w'):
        executable.add(int(parts[0], 16))
count = r.row()[0]
callbacks = struct.unpack('<'+'I'*count, r.uc.mem_read(game.symbols['alchemilla_probe_callbacks'], count*4))
assert all(not address or address in executable for address in callbacks), callbacks
assert r.call('map6_s02_probe_edges') == 0
r.bridge('vcReturnPreAutoCamWork', lambda *_: r.ret())
assert r.call('map6_s02_probe_lighthouse_complete') == 0
for phase in range(4):
    assert r.call('map6_s02_probe_save', phase) == 0, phase
r.call('func_801E386C')
credit_step = struct.unpack('<i', r.uc.mem_read(game.symbols['D_801E5E7C'], 4))[0]
assert credit_step == (0x20d0 - 264) // 400, credit_step
print('MAP6_S02 ARM entrance, event closure, lighthouse flags, exit, four save/checksum roundtrips and UFO credits initialization PASS')
