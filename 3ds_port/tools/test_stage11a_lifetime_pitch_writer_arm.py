"""Synthetic MIDI CC reproduction in preserved ARM images, never hardware causality.

Runs the original SD_Init and control_change(0, 1, 0) against each linked ELF.
This demonstrates one register-write path for unkeyed voices. It does not claim
that this exact controller event occurred in the user's school recording.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent


def trial(elf):
    sys.path.insert(0, str(ROOT.parent / '.toolchain/python-deps'))
    os.environ['SH_GAME_ELF'] = str(elf)
    fixture = PORT / 'tools/test_stage9_audio_arm.py'
    source = fixture.read_text().split('for command in (160,162,163,170):')[0]
    ns = {'__file__': str(fixture), '__name__': 'pitch_writer_fixture'}
    exec(compile(source, str(fixture), 'exec'), ns)
    r, game = ns['r'], ns['game']
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR

    scratch, pcm = 0x24800000, 0x24801000
    writes, keys = [], []
    addresses = sorted((addr, name) for name, addr in game.symbols.items())

    def register_write(*_):
        attr = r.uc.reg_read(UC_ARM_REG_R0)
        voice, mask = struct.unpack('<2I', r.uc.mem_read(attr, 8))
        if mask & 16:
            pitch = struct.unpack('<H', r.uc.mem_read(attr + 20, 2))[0]
            lr = r.uc.reg_read(UC_ARM_REG_LR)
            _, caller = max((addr, name) for addr, name in addresses if addr <= lr)
            writes.append(dict(voice_mask=voice, mask=mask, pitch=pitch, caller=caller))

    def key_write(*_):
        if r.uc.reg_read(UC_ARM_REG_R0) == 1:
            keys.append(r.uc.reg_read(UC_ARM_REG_R1))

    def pitches():
        values = []
        for i in range(24):
            r.uc.mem_write(scratch, struct.pack('<I', 1 << i) + bytes(76))
            r.call('SpuGetVoiceAttr', scratch)
            values.append(struct.unpack('<H', r.uc.mem_read(scratch + 20, 2))[0])
        return values

    def observer():
        if 'stage11a_lifetime_spu' not in game.symbols:
            return None
        r.uc.mem_write(scratch, bytes(1024))
        r.call('stage11a_lifetime_spu', scratch, scratch + 64)
        return list(struct.unpack('<16I', r.uc.mem_read(scratch, 64)))

    r.uc.hook_add(UC_HOOK_CODE, register_write,
                  begin=game.symbols['SpuSetVoiceAttr'], end=game.symbols['SpuSetVoiceAttr'])
    r.uc.hook_add(UC_HOOK_CODE, key_write,
                  begin=game.symbols['SpuSetKey'], end=game.symbols['SpuSetKey'])
    r.uc.hook_add(UC_HOOK_CODE, lambda *_: keys.append('WithAttr'),
                  begin=game.symbols['SpuSetKeyOnWithAttr'], end=game.symbols['SpuSetKeyOnWithAttr'])
    before, observed_before = pitches(), observer()
    r.call('control_change', 0, 1, 0)
    after, observed_after = pitches(), observer()
    r.call('game_spu_render', pcm, 512)
    samples = struct.unpack('<1024h', r.uc.mem_read(pcm, 2048))
    assert before == [0] * 24 and after == [4096] * 24
    assert not keys and writes and all(w['pitch'] == 4096 for w in writes)
    assert not any(samples) and not r.failure and not r.invalid
    if observed_after:
        assert observed_before[4:9] == [0, 0, 0, 24, 0]
        assert observed_after[4:9] == [0, 24, 0, 0, 24]
    r.call('game_audio_cd_close')
    for handle in r.handles.values():
        handle.close()
    return dict(elf=str(elf.relative_to(ROOT)), elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                before_pitch=before, after_pitch=after, keyons=keys, pitch_writes=writes,
                pcm_nonzero=sum(v != 0 for v in samples), observer_before=observed_before,
                observer_after=observed_after)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path)
    args = parser.parse_args()
    if args.elf:
        print(json.dumps(trial(args.elf)))
    else:
        cases = []
        for elf in (PORT / 'build/hardware-stage10-r6-cpu-audit/silenthill_game.elf',
                    PORT / 'build/stage11a-lifetime/silenthill_stage11a_lifetime.elf'):
            raw = subprocess.check_output([sys.executable, str(Path(__file__).resolve()), '--elf', str(elf)], text=True)
            cases.append(json.loads(raw))
        result = dict(status='PASS', scope='SYNTHETIC_LINKED_ARM_NOT_HARDWARE_TRIGGER',
                      injected_call='control_change(0,1,0) after original SD_Init', cases=cases,
                      hardware_write_origin_confirmed=False,
                      finding='MIDI CC1=0 can set all 24 unkeyed voices to pitch 4096 in frozen R6 and lifetime; no KeyOn or nonzero PCM is required.')
        dest = PORT / 'reports/stage11a-lifetime-hardware-20261028/pitch-writer-arm.json'
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
