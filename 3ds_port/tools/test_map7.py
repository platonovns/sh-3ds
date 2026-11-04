"""Focused ARM checks for resident Nowhere overlays and save compatibility."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
out = port / 'build/map7-checks'
out.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port/'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]', 1)[0]
source = source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/map7-checks'")
source = source.replace("*(str(p) for p in objects),'-o',str(probe)",
                        "*(str(p) for p in objects), str(port/'build-game/memcard.o'), '-Wl,--allow-multiple-definition','-o',str(probe)")
exec(compile(source, str(port/'tools/test_block3_components.py'), 'exec'))

tables = {
    'map7_s00': [(0xd2ca8,36)],
    'map7_s01': [(0xdfc78,18),(0xdfd98,36),(0xdffd8,4)],
    'map7_s02': [(0xe5b3c,96),(0xe7708,36),(0xe7948,4),(0xe7988,30),
                 (0xe7b68,52),(0xe7ea8,18),(0xe7fc8,46),(0xe82a8,4)],
}
for name, entries in tables.items():
    data = asset(name)
    for address, count in entries:
        for i in range(count):
            callback = struct.unpack_from('<I', data, address-0xc9578+i*16)[0]
            assert callback in (0, 0x800449f0, 0x80044b38, 0x80044ca4), (name, hex(address), i)

obj, fixture = out/'map7_probe.o', out/'map7_probe.elf'
p = subprocess.run([prefix+'gcc', *shlex.split(flags), '-c', str(port/'tests/map7_probe.c'), '-o', str(obj)], capture_output=True, text=True)
if p.returncode: raise RuntimeError(p.stderr)
names = ('map7_probe_edges', 'map7_probe_key', 'map7_probe_save', 'map7_probe_entry_complete')
subprocess.run([prefix+'gcc', '-nostdlib', '-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),
                *('-Wl,--undefined='+n for n in names), str(obj), str(port/'build-game/memcard.o'),
                '-Wl,--allow-multiple-definition', '-o', str(fixture)], check=True)
raw2 = fixture.read_bytes()
off2 = struct.unpack_from('<I', raw2, 28)[0]
size2, count2 = struct.unpack_from('<HH', raw2, 42)
for line in subprocess.check_output([prefix+'nm', '-n', str(fixture)], text=True).splitlines():
    p = line.split()
    if len(p) == 3 and p[2].startswith('map7_probe_'): game.symbols[p[2]] = int(p[0], 16)
r = Chapter()
for i in range(count2):
    typ, pos, addr, _, length, _, _, _ = struct.unpack_from('<8I', raw2, off2+i*size2)
    if typ == 1 and length: r.uc.mem_write(addr, raw2[pos:pos+length])
executable = {int(p[0], 16) for line in subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True).splitlines()
              if len(p := line.split()) == 3 and p[1] in ('T', 't', 'W', 'w')}
for name, index, target, flag, param in [('map6_s04',37,39,451,8),('map7_s00',39,40,472,6),
                                         ('map7_s01',40,41,532,71),('map7_s02',41,42,0,91)]:
    r.reset(name, index)
    assert r.call('alchemilla_probe_header') == 0, name
    count = r.row()[0]
    callbacks = struct.unpack('<'+'I'*count, r.uc.mem_read(game.symbols['alchemilla_probe_callbacks'], count*4))
    assert all(not p or p in executable for p in callbacks), name
    assert r.call('map7_probe_edges', target, flag, param) == 0, name
    if name == 'map7_s00':
        for symbol in ('map7_s00_Player_ControlUnfreeze','vcReturnPreAutoCamWork',
                       'func_8008D448','Game_FlashlightAttributesFix','Chara_ModelCharaIdClear',
                       'SD_Call','func_8003D01C','map7_s00_sharedFunc_800D2EF4_0_s00'):
            if symbol in game.symbols: r.bridge(symbol, lambda *_: r.ret())
        assert r.call('map7_probe_entry_complete') == 0
    if name == 'map7_s01': assert r.call('map7_probe_key',80,527,9) == 0
    if name == 'map7_s02':
        for rescued in (0, 1): assert r.call('map7_probe_save', rescued) == 0
print('MAP7 ARM bindings, event callbacks, overlay edges, Phaleg gate and save roundtrips PASS')
