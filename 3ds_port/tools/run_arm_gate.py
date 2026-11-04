#!/usr/bin/env python3
"""Execute the actual linked ARM gate in Unicorn; no 3DS services/game assets.

Optional host test dependency: unicorn==2.1.3. Only printf is intercepted to
avoid initializing newlib/3DS IO. Every memory, ABI, game and GTE test executes
the code from silenthill_3ds.elf. This is not console hardware acceptance.
"""
from pathlib import Path
import json
import os
import struct
import subprocess
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR,
                               UC_ARM_REG_PC, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC,
                               UC_CPU_ARM_1176)

port = Path(__file__).resolve().parent.parent
elf = port / 'silenthill_3ds.elf'
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
nm = subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True)
symbols = {line.split()[2]: int(line.split()[0], 16) for line in nm.splitlines()
           if len(line.split()) == 3 and line.split()[0] != 'w'}
data = elf.read_bytes()
phoff = struct.unpack_from('<I', data, 28)[0]
phsize, phcount = struct.unpack_from('<HH', data, 42)

def execute(fault=False):
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.ctl_set_cpu_model(UC_CPU_ARM_1176)
    uc.reg_write(UC_ARM_REG_C1_C0_2, 0xf00000)
    uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    uc.mem_map(0x100000, 0x800000)
    uc.mem_map(0x10000000, 0x10000)
    uc.mem_map(0x20000000, 0x1000)
    uc.mem_map(0x30000000, 0x1000)
    for n in range(phcount):
        typ, off, addr, _, filesz, _, _, _ = struct.unpack_from('<8I', data, phoff+n*phsize)
        if typ == 1:
            uc.mem_write(addr, data[off:off+filesz])
    uc.reg_write(UC_ARM_REG_SP, 0x1000fff0)
    uc.reg_write(UC_ARM_REG_R0, 0x20000000)
    uc.reg_write(UC_ARM_REG_LR, 0x30000000)
    unaligned = []
    def access(uc, kind, addr, size, value, arg):
        if size > 1 and addr % size:
            unaligned.append({'pc': hex(uc.reg_read(UC_ARM_REG_PC)), 'addr': hex(addr), 'size': size})
            uc.emu_stop()
    uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, access)
    def bypass_printf(uc, addr, size, arg):
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, bypass_printf, begin=symbols['printf'], end=symbols['printf'])
    if fault:
        def wrong_clip(uc, addr, size, arg):
            uc.reg_write(UC_ARM_REG_R0, 123)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE, wrong_clip, begin=symbols['NormalClip'], end=symbols['NormalClip'])
    uc.emu_start(symbols['engine_gate_run'], 0x30000000, timeout=20_000_000, count=40_000_000)
    assert not unaligned, unaligned
    assert uc.reg_read(UC_ARM_REG_PC) == 0x30000000, 'Gate did not return'
    names = ('memory_ok scratch_ok abi_ok core_ok ram_bytes scratch_bytes pointer_bytes bool_bytes '
             'gte_passed gte_total failed_test actual expected '
             'normal_before normal_after linear_before linear_after').split()
    result = dict(zip(names, struct.unpack('<11I2i4I', uc.mem_read(0x20000000, 68))))
    assert all(result[k] == 1 for k in names[:4]), result
    if fault:
        assert (result['failed_test'], result['actual'], result['expected']) == (9, 123, 256), result
        assert result['gte_passed'] == result['gte_total'] - 1, result
    else:
        assert result['failed_test'] == 0 and result['gte_passed'] == result['gte_total'] == 23, result
    return result

print(json.dumps({'execution': 'linked ARM code in Unicorn, not hardware',
                  'normal': execute(), 'injected_failure': execute(True),
                  'unaligned_multi_byte_accesses': 0}, indent=2))
