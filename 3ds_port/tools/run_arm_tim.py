#!/usr/bin/env python3
"""Linked ARM1176 TIM/VRAM and PICA upload byte checks, with host IO/SDK hooks.
GPU allocation/flush are test doubles; this cannot establish hardware rendering.
"""
from pathlib import Path
import io
import json
import os
import struct
import subprocess
import zlib
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_CPU_ARM_1176,
    UC_ARM_REG_S0, UC_ARM_REG_S1, UC_ARM_REG_S2, UC_ARM_REG_S3, UC_ARM_REG_S4, UC_ARM_REG_S5)
from test_orientation import render, sample

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
ELF_PATH = Path(os.environ.get('SH_GAME_ELF', str(PORT / 'silenthill_3ds.elf')))
ELF = ELF_PATH.read_bytes()
NM = subprocess.check_output([str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-nm'), '-n',
                              str(ELF_PATH)], text=True)
SYMBOLS = {s[2]: int(s[0], 16) for line in NM.splitlines() if len(s := line.split()) == 3 and s[0] != 'w'}
PHOFF = struct.unpack_from('<I', ELF, 28)[0]
PHSIZE, PHCOUNT = struct.unpack_from('<HH', ELF, 42)
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)


class Runner:
    def __init__(self, kind='supported'):
        self.kind = kind
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        uc.ctl_set_cpu_model(UC_CPU_ARM_1176)
        uc.reg_write(UC_ARM_REG_C1_C0_2, 0xf00000)
        uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        for addr, size in ((0x100000, 0xF00000), (0x10000000, 0x20000), (0x20000000, 0x10000),
                           (0x21000000, 0x10000), (0x22000000, 0x200000), (0x30000000, 0x1000)):
            uc.mem_map(addr, size)
        for n in range(PHCOUNT):
            typ, off, addr, _, size, _, _, _ = struct.unpack_from('<8I', ELF, PHOFF + n * PHSIZE)
            if typ == 1: uc.mem_write(addr, ELF[off:off + size])
        self.handles = {}; self.hooks = []; self.next_handle = 0
        self.allocations = {}; self.next_alloc = 0x20009000; self.deleted = 0; self.flushes = 0
        self.next_texture_data = 0x22000000; self.texture_snapshots = []
        self.bridge('fopen', self.fopen); self.bridge('fread', self.fread); self.bridge('fgets', self.fgets)
        self.bridge('fseek', lambda h, o, w, _: (self.handles[h].seek(o if o < 0x80000000 else o - 0x100000000, w), self.ret(0)))
        self.bridge('ftell', lambda h, *_: self.ret(self.handles[h].tell()))
        self.bridge('fclose', lambda h, *_: (self.handles.pop(h).close(), self.ret(0)))
        self.bridge('__errno', lambda *_: self.ret(0x20008000))
        self.bridge('calloc', self.calloc); self.bridge('free', self.free)
        self.bridge('C3D_TexInitWithParams', self.tex_init)
        self.bridge('C3D_TexDelete', self.tex_delete)
        self.bridge('C3D_TexFlush', self.tex_flush)
        self.bridge('C3D_TexBind', lambda *_: self.ret())
        # mallinfo returns a struct through hidden r0, not a scalar.
        self.bridge('mallinfo', lambda ptr, *_: (uc.mem_write(ptr, bytes(40)), self.ret(ptr)))
        self.bridge('linearSpaceFree', lambda *_: self.ret(16 * 1024 * 1024))
        # SDK time is not part of the TIM/VRAM oracle; return a 64-bit zero.
        self.bridge('svcGetSystemTick', lambda *_: (uc.reg_write(UC_ARM_REG_R1, 0), self.ret(0)))
        if kind == 'resource_missing':
            self.bridge('ShDisc_Resolve', lambda *_: self.ret(-1))
        self.invalid = []
        def invalid(uc, access, addr, size, value, arg):
            self.invalid.append([hex(addr), hex(uc.reg_read(UC_ARM_REG_PC))]); return False
        uc.hook_add(UC_HOOK_MEM_INVALID, invalid)
        uc.mem_write(0x20001000, b'/image.bin\0'); uc.mem_write(0x20002000, b'/image.cue\0')

    def ret(self, n=0):
        self.uc.reg_write(UC_ARM_REG_R0, n & 0xffffffff)
        self.uc.reg_write(UC_ARM_REG_PC, self.uc.reg_read(UC_ARM_REG_LR))

    def bridge(self, name, fn):
        assert name in SYMBOLS, name
        self.hooks.append(self.uc.hook_add(UC_HOOK_CODE,
            lambda uc, addr, size, arg: fn(*(uc.reg_read(r) for r in REGS)), begin=SYMBOLS[name], end=SYMBOLS[name]))

    def call(self, name, *args):
        uc = self.uc
        uc.reg_write(UC_ARM_REG_SP, 0x1001ffc0)
        for r, a in zip(REGS, args): uc.reg_write(r, a)
        if len(args) > 4: uc.mem_write(0x1001ffc0, struct.pack('<' + 'I' * (len(args)-4), *args[4:]))
        uc.reg_write(UC_ARM_REG_LR, 0x30000000)
        uc.emu_start(SYMBOLS[name], 0x30000000, timeout=55_000_000, count=200_000_000)
        assert not self.invalid, self.invalid
        assert uc.reg_read(UC_ARM_REG_PC) == 0x30000000, (name, hex(uc.reg_read(UC_ARM_REG_PC)))
        return uc.reg_read(UC_ARM_REG_R0)

    def fopen(self, path, mode, *_):
        path = bytes(self.uc.mem_read(path, 1024)).split(b'\0')[0].decode()
        if self.kind == 'missing' and path == '/image.bin':
            self.uc.mem_write(0x20008000, struct.pack('<I', 2)); self.ret(0); return
        f = (ROOT / 'sh1_data' / ('sh1.bin' if path == '/image.bin' else 'sh1.cue')).open('rb')
        h = 0x21000000 + self.next_handle * 0x1000; self.next_handle += 1
        self.handles[h] = f; self.ret(h)

    def fread(self, dst, size, count, h):
        f = self.handles[h]; pos = f.tell()
        if self.kind == 'short_resource' and pos == 64 * 2352: self.ret(0); return
        b = bytearray(f.read(size * count))
        fault = 25 * 2352 + 31 if self.kind == 'unsupported' else 64 * 2352 + 24 + 544
        if self.kind in ('unsupported', 'crc') and pos <= fault < pos + len(b): b[fault-pos] ^= 1
        if b: self.uc.mem_write(dst, bytes(b))
        self.ret(len(b) // size if size else 0)

    def fgets(self, dst, count, h, _):
        b = self.handles[h].readline(count - 1)
        if b: self.uc.mem_write(dst, b + b'\0')
        self.ret(dst if b else 0)

    def calloc(self, count, size, *_):
        if self.kind == 'calloc_fail': self.ret(0); return
        p = self.next_alloc; self.next_alloc += 0x100
        assert size * count <= 0x100
        self.allocations[p] = size * count; self.uc.mem_write(p, bytes(size * count)); self.ret(p)

    def free(self, p, *_):
        if p: del self.allocations[p]
        self.ret()

    def tex_init(self, tex, cube, dimensions, params):
        if self.kind == 'pica_fail': self.ret(0); return
        width, height = dimensions & 65535, dimensions >> 16
        assert 8 <= width <= 1024 and 8 <= height <= 1024
        data = self.next_texture_data
        self.next_texture_data += (width * height * 4 + 4095) & ~4095
        self.texture = (tex, data, width, height)
        self.uc.mem_write(tex, struct.pack('<6I', data, (width * height * 4) << 4,
                                          (width << 16) | height, 0, 0, 0))
        self.ret(1)

    def tex_delete(self, tex, *_):
        self.deleted += 1; self.ret()

    def tex_flush(self, tex, *_):
        _, data, width, height = self.texture
        self.texture_snapshots.append((tex, width, height, bytes(self.uc.mem_read(data,width*height*4))))
        self.flushes += 1; self.ret()

    def capture_draws(self):
        self.draws = []
        def capture(ptr, count, tex, blend):
            self.draws.append((tex,blend,[struct.unpack('<9f',self.uc.mem_read(ptr+i*36,36)) for i in range(count)]))
            self.ret(1)
        self.bridge('render3ds_draw_triangles',capture)

    def floats(self, *values):
        for reg,value in zip((UC_ARM_REG_S0,UC_ARM_REG_S1,UC_ARM_REG_S2,UC_ARM_REG_S3,UC_ARM_REG_S4,UC_ARM_REG_S5),values):
            self.uc.reg_write(reg,struct.unpack('<I',struct.pack('<f',value))[0])

    def region(self, tex, width, height, sx=0, sy=0, sw=None, sh=None, flips=0):
        self.floats(0,0,width,height)
        return self.call('render3ds_draw_texture_region',tex,sx,sy,sw or width,sh or height,flips,0)

    def gate(self):
        self.call('tim_gate_run', SYMBOLS['tim_diag'], SYMBOLS['stage3_vram'], 0x20001000, 0x20002000)
        assert not self.handles
        return list(struct.unpack('<78I', self.uc.mem_read(SYMBOLS['tim_diag'], 312)))


def sample_draw(tiled,pw,ph,vertices,width,height):
    """UV at screen-space pixel centers via triangle barycentric interpolation."""
    x0 = min(v[0] for v in vertices); y0 = min(v[1] for v in vertices)
    dx = (max(v[0] for v in vertices)-x0)/width
    dy = (max(v[1] for v in vertices)-y0)/height
    out = bytearray()
    for y in range(height):
        for x in range(width):
            px,py = x0+(x+0.5)*dx,y0+(y+0.5)*dy
            for i in range(0,len(vertices),3):
                a,b,c = vertices[i:i+3]
                det = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                wa = ((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/det
                wb = ((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/det
                wc = 1-wa-wb
                if min(wa,wb,wc) >= -1e-6:
                    out += sample(tiled,pw,ph,wa*a[3]+wb*b[3]+wc*c[3],wa*a[4]+wb*b[4]+wc*c[4])
                    break
            else: raise AssertionError('pixel outside both triangles')
    return bytes(out)

def main():
    r = Runner()
    r.call('tim_selftest_run', SYMBOLS['stage3_vram'], 0x20000000)
    synthetic = list(struct.unpack('<5I', r.uc.mem_read(0x20000000, 20)))
    assert synthetic[0] == synthetic[1] and synthetic[2:] == [0,0,0], synthetic
    words = r.gate()
    pc = json.loads((PORT / 'reports/tim-pc-tests.json').read_text())
    assert words == pc['gate_words'] and synthetic[0] == pc['synthetic_passed']
    ref = json.loads((PORT / 'reports/tim-reference.json').read_text())
    pica = []
    r.capture_draws()
    # Actual linked renderer's row callback, decode, swizzle and padding execute.
    # Only C3D allocation/flush and allocator telemetry are bridged.
    for i, meta in enumerate(ref['resources']):
        r.uc.mem_write(SYMBOLS['renderer'] + 4, b'\1')  # Render3dsStats.ready
        r.uc.mem_write(0x20000000, struct.pack('<I', i))
        width, height = meta['logical']
        tex = r.call('render3ds_texture_create_rows', width, height, SYMBOLS['tim_read_row'],
                     0x20000000, 0x20000010, 0x20000014)
        assert tex
        _, data, pw, ph = r.texture
        assert list(struct.unpack('<2I', r.uc.mem_read(0x20000010, 8))) == [pw, ph]
        tiled = bytes(r.uc.mem_read(data, pw * ph * 4))
        rgba = bytearray(); padding = 0
        for y in range(ph):
            ty = y
            for x in range(pw):
                morton = sum(((x >> b) & 1) << (2*b) | ((ty >> b) & 1) << (2*b+1) for b in range(3))
                off = (((ty // 8) * (pw // 8) + x // 8) * 64 + morton) * 4
                pixel = tiled[off:off+4][::-1]
                if x < width and y < height: rgba += pixel
                else: assert pixel == bytes(4); padding += 1
        assert zlib.crc32(rgba) == meta['decoded_crc']
        assert r.region(tex,width,height) == 1
        sampled = sample_draw(tiled,pw,ph,r.draws[-1][2],width,height)
        assert zlib.crc32(sampled) == meta['decoded_crc'], 'PICA sampling/UV orientation mismatch'
        if i == 1:
            for strip in range(4):
                assert r.region(tex,256,16,strip*256,0,256,16) == 1
                cropped = sample_draw(tiled,pw,ph,r.draws[-1][2],256,16)
                expected = b''.join(rgba[(y*width+strip*256)*4:(y*width+(strip+1)*256)*4] for y in range(16))
                assert cropped == expected
        pica.append(dict(name=meta['name'], physical=[pw,ph], logical=[width,height],
                         decoded_crc=zlib.crc32(rgba), tiled_crc=zlib.crc32(tiled), zero_padding_pixels=padding,
                         normal_descriptor_bytes=r.allocations[tex], linear_texture_bytes=pw*ph*4,
                         sampled_draw_crc=zlib.crc32(sampled), native_orientation=True))
        r.call('render3ds_texture_destroy', tex)
        assert not r.allocations
    negative = {}
    for kind, expected in (('missing',300), ('unsupported',301), ('resource_missing',310), ('short_resource',312), ('crc',313)):
        n = Runner(kind); state = n.gate(); assert state[3] == expected, state
        negative[kind] = dict(first_failure=state[3], expected=state[4], actual=state[5])
    for kind in ('pica_fail', 'calloc_fail', 'callback_fail'):
        n = Runner(kind); n.uc.mem_write(SYMBOLS['renderer'] + 4, b'\1')
        # Empty metadata makes the real callback reject the decode after allocation.
        tex = n.call('render3ds_texture_create_rows', 320, 240, SYMBOLS['tim_read_row'], 0x20000000, 0x20000010, 0x20000014)
        assert not tex and not n.allocations and not n.flushes
        assert n.deleted == (1 if kind == 'callback_fail' else 0)
        assert bytes(n.uc.mem_read(0x20000010,8)) == bytes(8)
        negative[kind] = 'NULL returned, no texture/normal allocation leaked'
    print(json.dumps(dict(execution='linked ARM1176; host stdio and GPU allocation/flush bridges; not hardware acceptance',
                          synthetic_passed=synthetic[0], synthetic_total=synthetic[1],
                          pc_metadata_and_checksums_equal=True, gate_words=words, pica_upload=pica, negative=negative), indent=2))


if __name__ == '__main__': main()
