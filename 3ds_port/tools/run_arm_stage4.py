#!/usr/bin/env python3
"""Execute the linked original game queue and image facade on ARM1176.
Only host stdio/SDK infrastructure is bridged by the shared test runner.
"""
import json
import struct
from run_arm_tim import Runner, SYMBOLS, PORT
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0

def execute(kind):
    runner = Runner(kind if kind in ('supported', 'missing', 'unsupported', 'short_resource', 'crc') else 'supported')
    if kind == 'bad_id':
        runner.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, arg: uc.reg_write(UC_ARM_REG_R0, 2074),
                          begin=SYMBOLS['Fs_QueueStartReadTim'], end=SYMBOLS['Fs_QueueStartReadTim'])
    if kind == 'unsupported_anm':
        runner.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, arg: uc.mem_write(uc.reg_read(UC_ARM_REG_R0) + 5, b'\x02'),
                          begin=SYMBOLS['Fs_QueueUpdatePostLoad'], end=SYMBOLS['Fs_QueueUpdatePostLoad'])
    if kind == 'bad_vram':
        runner.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, arg: uc.mem_write(uc.reg_read(UC_ARM_REG_R0), struct.pack('<h', 1024)),
                          begin=SYMBOLS['LoadImage'], end=SYMBOLS['LoadImage'])
    if kind == 'queue_timeout':
        runner.bridge('CdReadSync', lambda *_: runner.ret(1))
    calls = []
    for name in ('Fs_QueueInitialize', 'Fs_QueueStartReadTim', 'Fs_QueueUpdateRead',
                 'Fs_QueuePostLoadTim', 'OpenTIM', 'ReadTIM', 'LoadImage'):
        runner.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, arg, name=name: calls.append(name),
                           begin=SYMBOLS[name], end=SYMBOLS[name])
    runner.call('stage4_fs_run', SYMBOLS['stage4_diag'], SYMBOLS['stage3_vram'], 0x20001000, 0x20002000)
    values = struct.unpack('<10I', runner.uc.mem_read(SYMBOLS['stage4_diag'], 40))
    result = dict(zip(('checkpoint', 'first_failure', 'file_id', 'detail', 'reads', 'uploads',
                       'completed', 'ticks', 'vram_crc', 'operation_pointer'), values))
    assert not runner.handles and not runner.invalid
    result['original_function_calls'] = {n: calls.count(n) for n in set(calls)}
    if kind == 'supported':
        assert result['checkpoint'] == 5 and result['first_failure'] == 0, result
        assert result['completed'] == 2 and result['reads'] == 2 and result['uploads'] == 4
        assert calls.count('Fs_QueuePostLoadTim') == 2 and calls.count('LoadImage') == 4
        pc = json.loads((PORT / 'reports/stage4-fs-pc.json').read_text())['positive']
        assert result['vram_crc'] == pc['vram_crc'] and result['ticks'] == pc['ticks']
    else:
        assert result['first_failure'] == {'missing': 411, 'unsupported': 412,
                                           'short_resource': 404, 'crc': 415, 'bad_id': 416,
                                           'unsupported_anm': 418, 'bad_vram': 410, 'queue_timeout': 414}[kind], result
    return result

print(json.dumps({'execution': 'linked ARM1176, original FS queue; not hardware acceptance',
                  'cases': {k: execute(k) for k in ('supported', 'missing', 'unsupported', 'short_resource', 'crc',
                                                   'bad_id', 'unsupported_anm', 'bad_vram', 'queue_timeout')}}, indent=2))
