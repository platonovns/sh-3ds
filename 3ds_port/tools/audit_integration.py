"""Small production ELF structural audit; does not substitute for gameplay."""
import os, re, struct, subprocess
from pathlib import Path

port = Path(__file__).resolve().parents[1]
elf = port / 'silenthill_game.elf'
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
nm = subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True)
symbols = {}
callable_addresses = set()
for line in nm.splitlines():
    p = line.split()
    if len(p) == 3:
        try: addr = int(p[0], 16)
        except ValueError: continue
        symbols[p[2]] = addr
        if p[1] in 'TtWw': callable_addresses.add(addr)
undefined = subprocess.check_output([prefix+'nm', '-u', str(elf)], text=True)
assert all(re.match(r'^\s*w\s+', line) for line in undefined.splitlines()), undefined
data = elf.read_bytes()
offset = struct.unpack_from('<I', data, 28)[0]
size, count = struct.unpack_from('<HH', data, 42)
segments = []
for i in range(count):
    kind, pos, addr, _, fsize, memsize, _, _ = struct.unpack_from('<8I', data, offset+i*size)
    if kind == 1: segments.append((addr, addr+memsize, data[pos:pos+fsize]))
def word(addr):
    for start, end, raw in segments:
        if start <= addr and addr+4 <= end:
            off = addr-start
            return struct.unpack('<I', (raw[off:off+4]+b'\0'*4)[:4])[0]
    raise ValueError(hex(addr))

source = (port/'source/game_map.c').read_text()
rows = re.findall(r'case MapIdx_(MAP\d_S\d\d):.*?g_pMapOverlayHeader=&(\w+);break;', source)
assert len(rows) == 32 and len({x[0] for x in rows}) == 32, rows
fields = [4,12,16,60,64,68,72,96,100,104,108,112,116,120,128,132,140,144,152,156]
fields += list(range(0xa4,0x184,4)) + list(range(0x194,0x248,4))
for name, header in rows:
    assert header in symbols, (name, header)
    base = symbols[header]
    for off in fields:
        ptr = word(base+off)
        assert ptr == 0 or ptr in callable_addresses, (name, hex(off), hex(ptr))
    events, funcs = word(base+0x24), word(base+0x20)
    for index in range(257):
        assert index < 256, (name, 'unterminated events')
        event = events + index*12
        if word(event+4) & 15 == 15: break
        state = word(event+8)
        if state & 31 == 10:
            ptr = word(funcs + ((state >> 5) & 255)*4)
            assert ptr in callable_addresses, (name, 'event', index, hex(ptr))
for name in ('open_main','game_fmv_play','game_fmv_platform_begin','fmv_entry','fmv_stream_init',
             'game3ds_gpu_sync','Game3ds_BeginUpdate'):
    assert name in symbols, name
disassembly = subprocess.check_output([prefix+'objdump','-d',str(elf)], text=True)
start = disassembly.index('<open_main>:')
body = disassembly[start:disassembly.index('\n\n',start)]
assert '<game_fmv_play>' in body, 'open_main does not call native FMV'
assert not any(x in nm for x in ('s11_frame','s11f_', 'stage11b_')), 'Stage 11B diagnostics found'
print('PASS: 32 map registrations and header function pointers; native FMV call; no strong undefined symbols or Stage 11B sampling symbols')
