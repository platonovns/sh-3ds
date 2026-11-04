#!/usr/bin/env python3
"""Execute linked Stage 2 ARM code with real read-only host image IO hooks.

Only stdio transport/log output/errno are bridged; disc geometry, CUE parsing,
identity, CRC32, on-disc FS decode and PsxFile logic execute in ARM.
No 3DS services are emulated. This is NOT hardware acceptance.
"""
from pathlib import Path
import io
import json
import os
import struct
import subprocess
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_CPU_ARM_1176)

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
elf = (PORT / 'silenthill_3ds.elf').read_bytes()
nm = subprocess.check_output([str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-nm'), '-n',
                              str(PORT / 'silenthill_3ds.elf')], text=True)
symbols = {s[2]: int(s[0], 16) for line in nm.splitlines() if len(s := line.split()) == 3 and s[0] != 'w'}
phoff = struct.unpack_from('<I', elf, 28)[0]
phsize, phcount = struct.unpack_from('<HH', elf, 42)


def execute(kind):
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.ctl_set_cpu_model(UC_CPU_ARM_1176)
    uc.reg_write(UC_ARM_REG_C1_C0_2, 0xf00000)
    uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    uc.mem_map(0x100000, 0x800000)
    uc.mem_map(0x10000000, 0x20000)
    uc.mem_map(0x20000000, 0x10000)
    # newlib's ferror macro reads FILE flags directly; synthetic transport FILEs
    # have zero flags. No filesystem implementation or image logic is bypassed.
    uc.mem_map(0x21000000, 0x10000)
    uc.mem_map(0x30000000, 0x1000)
    for n in range(phcount):
        typ, off, addr, _, filesz, _, _, _ = struct.unpack_from('<8I', elf, phoff + n * phsize)
        if typ == 1:
            uc.mem_write(addr, elf[off:off + filesz])
    handles = {}
    opened = []
    hooks = []
    regs = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
    def cstr(addr):
        return bytes(uc.mem_read(addr, 1024)).split(b'\0')[0].decode('ascii')
    def ret(n):
        uc.reg_write(UC_ARM_REG_R0, n & 0xffffffff)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def signed(n):
        return n if n < 0x80000000 else n - 0x100000000
    def bridge(name, fn):
        if name in symbols:
            def callback(uc, addr, size, arg):
                fn(*(uc.reg_read(r) for r in regs))
            hooks.append(uc.hook_add(UC_HOOK_CODE, callback, begin=symbols[name], end=symbols[name]))
    def fopen(path, mode, _a, _b):
        path, mode = cstr(path), cstr(mode)
        if path == '/image.bin' and kind == 'missing':
            uc.mem_write(0x20008000, struct.pack('<I', 2)); ret(0); return
        if path == '/image.bin':
            f = (ROOT / 'sh1_data/sh1.bin').open('rb')
        elif path == '/image.cue':
            f = io.BytesIO((ROOT / 'sh1_data/sh1.cue').read_bytes())
        elif path == '/log.txt':
            f = io.BytesIO()
        else:
            raise AssertionError(path)
        handle = 0x21000000 + len(opened) * 0x1000
        opened.append(f); handles[handle] = f
        ret(handle)
    def fread(dst, size, count, handle):
        f = handles[handle]; pos = f.tell(); b = bytearray(f.read(size * count))
        fault = (207 if kind == 'bad_read' else 25) * 2352 + 31
        if kind in ('unsupported', 'bad_read') and pos <= fault < pos + len(b):
            b[fault - pos] ^= 1
        uc.mem_write(dst, bytes(b)); ret(len(b) // size if size else 0)
    def fgets(dst, count, handle, _):
        b = handles[handle].readline(count - 1)
        if b: uc.mem_write(dst, b + b'\0')
        ret(dst if b else 0)
    def seek(handle, off, whence, _):
        handles[handle].seek(signed(off), whence); ret(0)
    def close(handle, *_):
        handles.pop(handle).close(); ret(0)
    bridge('fopen', fopen); bridge('fread', fread); bridge('fgets', fgets)
    bridge('fseek', seek); bridge('ftell', lambda handle, *_: ret(handles[handle].tell()))
    bridge('fclose', close); bridge('ferror', lambda *_: ret(0))
    def free_null(ptr,*_):
        assert ptr==0,'Diagnostic disc path must not allocate a resource cache'
        ret(0)
    bridge('free',free_null) # Standard C free(NULL), new optional cache cleanup.
    bridge('__errno', lambda *_: ret(0x20008000))
    for name in ('fprintf', 'fflush', 'fputs', 'printf', 'puts', 'fwrite'):
        bridge(name, lambda *_: ret(0))
    uc.mem_write(0x20001000, b'/image.bin\0')
    uc.mem_write(0x20002000, b'/image.cue\0')
    uc.mem_write(0x20003000, b'/log.txt\0')
    uc.reg_write(UC_ARM_REG_SP, 0x1001fff0)
    # Fifth AAPCS argument: clock callback = NULL (timings measured on host/3DS).
    uc.mem_write(0x1001fff0, struct.pack('<I', 0))
    for reg, val in zip(regs, (0x20000000, 0x20001000, 0x20002000, 0x20003000)):
        uc.reg_write(reg, val)
    uc.reg_write(UC_ARM_REG_LR, 0x30000000)
    invalid_access = []
    def invalid(uc, access, addr, size, value, arg):
        pc = uc.reg_read(UC_ARM_REG_PC)
        nearest = max(((v, k) for k, v in symbols.items() if v <= pc), default=(0, '?'))
        invalid_access.append(f'Unmapped {addr:#x} at PC={pc:#x} {nearest}, LR={uc.reg_read(UC_ARM_REG_LR):#x}')
        return False
    uc.hook_add(UC_HOOK_MEM_INVALID, invalid)
    try:
        try:
            uc.emu_start(symbols['disc_gate_run'], 0x30000000, timeout=55_000_000, count=150_000_000)
        except Exception as e:
            raise AssertionError(invalid_access) from e
        assert uc.reg_read(UC_ARM_REG_PC) == 0x30000000, hex(uc.reg_read(UC_ARM_REG_PC))
        names = ('open_status identity_status log_status found cue_parsed tracks mode sector_bytes sectors image_bytes '
                 'raw_pass raw_total data_pass data_total fs_pass fs_total msf_pass msf_total first_failure expected actual '
                 'test_count identity_us random_us sequential_us sequential_sectors').split()
        result = dict(zip(names, struct.unpack('<3i23I', uc.mem_read(0x20000000, 104))))
        if kind == 'supported':
            assert result['open_status'] == result['identity_status'] == result['first_failure'] == 0, result
            assert (result['raw_pass'], result['data_pass'], result['fs_pass'], result['msf_pass']) == (3, 3, 6, 15), result
        elif kind == 'bad_read':
            assert result['identity_status'] == 0 and result['first_failure'] == 8, result
            assert result['expected'] == 0xa8966201 and result['actual'] != result['expected'], result
            assert result['fs_pass'] == 5 and result['fs_total'] == 6, result
        elif kind == 'missing':
            assert result['open_status'] == -1 and not result['found'] and not result['test_count'], result
        else:
            assert result['open_status'] == 0 and result['identity_status'] == -6 and not result['test_count'], result
        assert not handles, 'Leaked FILE handles'
        return result
    finally:
        for f in opened:
            f.close()


print(json.dumps({'execution': 'linked ARM1176 code; host stdio transport; not console hardware',
                  'supported': execute('supported'), 'missing': execute('missing'),
                  'unsupported': execute('unsupported'), 'injected_resource_failure': execute('bad_read')}, indent=2))
