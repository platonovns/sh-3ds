"""Short ARM checks of the lighthouse CLUT read/modify/upload and bounds."""
import os, shlex, struct, subprocess, sys
from pathlib import Path

port = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(port.parent.parent/'.toolchain/python-deps'))
os.environ.setdefault('SH_GAME_ELF', str(port/'silenthill_game.elf'))
fixture = port/'tools/test_game_gpu_arm.py'
ns = {'__file__': str(fixture), '__name__': 'lighthouse_gpu_fixture'}
exec(compile(fixture.read_text().split('results={}')[0], str(fixture), 'exec'), ns)
Machine, symbols, elf = ns['Machine'], ns['symbols'], ns['elf_path']
prefix = str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags = shlex.split((port/'build-game/flags').read_text().splitlines()[0])
obj, probe = port/'build/lighthouse_clut_probe.o', port/'build/lighthouse_clut_probe.elf'
subprocess.run([prefix+'gcc', *flags, '-c', str(port/'tests/lighthouse_clut_probe.c'), '-o', str(obj)], check=True)
subprocess.run([prefix+'gcc', '-nostdlib', '-Wl,-Ttext=0xE00000,--gc-sections,--just-symbols='+str(elf),
                '-Wl,--undefined=lighthouse_clut_probe_setup', str(obj), '-o', str(probe)], check=True)
nm = subprocess.check_output([prefix+'nm', '-an', str(elf)], text=True)
rows = [line.split() for line in nm.splitlines() if len(line.split()) == 3]
canonical = next(int(x[0],16) for x in rows if x[2] == 'canonical')
active = next(int(x[0],16) for x in rows if x[2] == 'active' and int(x[0],16) == canonical+4)
probe_nm = subprocess.check_output([prefix+'nm', '-n', str(probe)], text=True)
symbols['lighthouse_clut_probe_setup'] = next(int(x[0],16) for line in probe_nm.splitlines()
    if len(x := line.split()) == 3 and x[2] == 'lighthouse_clut_probe_setup')
raw = probe.read_bytes(); off = struct.unpack_from('<I', raw, 28)[0]
size, count = struct.unpack_from('<HH', raw, 42)

def machine():
    m = Machine()
    for i in range(count):
        typ, pos, addr, _, length, _, _, _ = struct.unpack_from('<8I', raw, off+i*size)
        if typ == 1 and length: m.uc.mem_write(addr, raw[pos:pos+length])
    m.uc.mem_write(active, struct.pack('<I', symbols['fs_result']))
    m.uc.mem_write(canonical, struct.pack('<I', symbols['vram']))
    m.word('game3ds_canonical', symbols['vram'])
    m.hook('game3ds_gpu_dirty_rect', lambda *_: m.ret())
    m.hook('Lm_TransparentPrimSet', lambda *_: m.ret())
    return m

m = machine(); m.call('lighthouse_clut_probe_setup')
vram = symbols['vram']; start = vram + (480*1024+320)*2
rows = [[((y*16+x)*113)&0x7fff for x in range(16)] for y in range(16)]
for y,row in enumerate(rows): m.uc.mem_write(start+y*2048, struct.pack('<16H', *row))
for enable in (1, 0):
    m.call('WorldGfx_CharaModelTransparentSet', 34, enable) # Chara_Alessa
    for y,row in enumerate(rows):
        expected = [v | 0x8000 if enable else v for v in row]
        assert list(struct.unpack('<16H', m.uc.mem_read(start+y*2048, 32))) == expected

# A stack buffer is still rejected unless its exact producer extent is registered.
for registered in (0, 510):
    m = machine(); rect, stack = 0x1001d000, 0x1001d100
    m.uc.mem_write(rect, struct.pack('<4h', 320, 480, 16, 16))
    if registered: m.call('stage4_fs_game_image_span', stack, registered)
    m.call('LoadImage', rect, stack, expected_failure=409)
    assert m.failure == (409, 512), m.failure

# Scene-local effect must request the existing native framebuffer capture.
m = machine(); seen = []
def captured(*_):
    seen.append(True); m.uc.emu_stop()
m.hook('Game3ds_FramebufferCapture', captured)
try: m.call('map6_s02_func_800D2364')
except AssertionError: pass # deliberate stop at the framebuffer boundary
assert seen
print('Lighthouse ARM CLUT roundtrip, 512-byte bounds guard and feedback capture PASS')
