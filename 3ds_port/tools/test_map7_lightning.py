"""Exercise ARM particle-script pointer conversion without retail assets."""
from pathlib import Path
import os
import struct
import subprocess
import sys

port = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(port.parent.parent / '.toolchain/python-deps'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

elf = port / 'silenthill_game.elf'
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
symbols = {}
for line in subprocess.check_output([prefix + 'nm', '-n', str(elf)], text=True).splitlines():
    fields = line.split()
    if len(fields) == 3:
        symbols[fields[2]] = int(fields[0], 16)

raw = elf.read_bytes()
phoff = struct.unpack_from('<I', raw, 28)[0]
phsize, phcount = struct.unpack_from('<HH', raw, 42)
uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
uc.mem_map(0x100000, 0x1000000)
for i in range(phcount):
    typ, offset, address, _, size, _, _, _ = struct.unpack_from('<8I', raw, phoff + i * phsize)
    if typ == 1 and size:
        uc.mem_write(address, raw[offset:offset + size])

ram = symbols['g_PsxRam']
script, sprite = ram + 0xec680, ram + 0xec2fc
particle, stop = 0xf00000, 0xf10000
uc.mem_write(script, struct.pack('<III', 0, 0x800ec2fc, 0))
uc.mem_write(script + 8 * 12, struct.pack('<III', 0, 0x800ec680, 1))
uc.mem_write(symbols['g_DeltaTime'], struct.pack('<I', 136))
for initial in (script, script + 8 * 12, 0x800ec680):
    uc.mem_write(particle, struct.pack('<II', initial, 100) + bytes(72))
    uc.reg_write(UC_ARM_REG_R0, particle)
    uc.reg_write(UC_ARM_REG_SP, 0xff0000)
    uc.reg_write(UC_ARM_REG_LR, stop)
    uc.emu_start(symbols['map7_s03_func_800D88E8'], stop, count=1000)
    result = uc.reg_read(UC_ARM_REG_R0)
    assert result == sprite, (hex(initial), hex(result), hex(sprite))
print('MAP7_S03 ARM particle-script pointers and loop PASS')

# The retail results screen reinitializes a save and restores these fields.
save = 0xe00000
uc.mem_write(save, bytes(636))
uc.mem_write(symbols['g_SavegamePtr'], struct.pack('<I', save))
for name, value in (('D_800C48B0', 2), ('D_800C48B1', 5),
                    ('D_800C48B2', 0), ('D_800C48B3', 7),
                    ('D_800C48B5', 0), ('D_800C48B6', 0), ('D_800C48B7', 0)):
    uc.mem_write(symbols[name], bytes([value]))
uc.reg_write(UC_ARM_REG_SP, 0xff0000)
uc.reg_write(UC_ARM_REG_LR, stop)
uc.emu_start(symbols['func_800904F4'], stop, count=10000)
assert bytes(uc.mem_read(save + 0xa8, 1)) == b'\x07'
assert bytes(uc.mem_read(save + 0x24a, 2)) == b'\x02\x05'
assert uc.mem_read(save + 0x25c, 1)[0] & 1
assert uc.mem_read(save + 0x27a, 1)[0] & 64
print('ARM results restore clear-game fields and Next Fear state PASS')

# Exercise each ordinary ending's original clear-game transition.
for ending in range(1, 5):
    uc.mem_write(save, bytes(636))
    uc.mem_write(symbols['g_SysWork'] + 0xc, struct.pack('<I', 2))
    uc.mem_write(symbols['map7_s03_D_800F481C'], bytes([ending]))
    uc.reg_write(UC_ARM_REG_SP, 0xff0000)
    uc.reg_write(UC_ARM_REG_LR, stop)
    uc.emu_start(symbols['map7_s03_func_800E9C28'], stop, count=10000)
    assert uc.mem_read(save + 0x24a, 2) == bytes([1, 1 << (ending - 1)])
    assert uc.mem_read(save + 0x25c, 1)[0] & 1
    assert uc.mem_read(save + 0xa8, 1)[0] == 24
    assert struct.unpack('<I', uc.mem_read(symbols['g_SysWork'] + 8, 4))[0] == 2
print('ARM four clear-game ending flags and results transition PASS')

branch_names = ('map7_s03_func_800E3F30', 'map7_s03_func_800E4714',
                'map7_s03_func_800E514C', 'map7_s03_func_800E70F0')
branch_calls = []
def intercept_branch(machine, address, size, user):
    for name in branch_names + ('map7_s03_Map_CutsceneObjectsUpdate',):
        if address == symbols[name]:
            if name in branch_names:
                branch_calls.append(name)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
            return

uc.hook_add(UC_HOOK_CODE, intercept_branch)
for kaufmann in (0, 1):
    for cybil in (0, 1):
        uc.mem_write(save, bytes(636))
        for flag, enabled in ((391, kaufmann), (449, cybil)):
            if enabled:
                uc.mem_write(save + 0x168 + 4 * (flag >> 5), struct.pack('<I', 1 << (flag & 31)))
        for step, expected in ((1, branch_names[0 if cybil else 1]),
                               (3, branch_names[2 if kaufmann else 3])):
            branch_calls.clear()
            uc.mem_write(symbols['map7_s03_D_800F4805'], bytes([step]))
            uc.reg_write(UC_ARM_REG_SP, 0xff0000)
            uc.reg_write(UC_ARM_REG_LR, stop)
            uc.emu_start(symbols['map7_s03_func_800E3390'], stop, count=10000)
            assert branch_calls == [expected], (kaufmann, cybil, step, branch_calls)
print('ARM final scene 391/449 combinations PASS')

# Check that a completed fade and empty file queue enter the retail credits state.
def intercept(machine, address, size, user):
    if address == symbols['Fs_QueueGetLength']:
        machine.reg_write(UC_ARM_REG_R0, 0)
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

uc.mem_write(symbols['g_Screen_FadeStatus'], struct.pack('<I', 5))
uc.hook_add(UC_HOOK_CODE, intercept)
uc.reg_write(UC_ARM_REG_SP, 0xff0000)
uc.reg_write(UC_ARM_REG_LR, stop)
uc.emu_start(symbols['func_801E2FC0'], stop, count=10000)
state = struct.unpack('<I', uc.mem_read(symbols['g_GameWork'] + 0x594, 4))[0]
assert state == 21 and uc.reg_read(UC_ARM_REG_R0) == 1, state
print('ARM ending-to-credits state transition PASS')

# The 3DS main loop must dispatch state 21 to the actual credits handler.
table = symbols['g_GameStateUpdateFuncs']
entries = struct.unpack('<22I', uc.mem_read(table, 22 * 4))
assert symbols.get('GameState_Unk15_Update') and entries[21] == symbols['GameState_Unk15_Update'], 'state 21 has no credits handler'
assert entries[17] == 0 and entries[18] == 0
audio_calls = []
def intercept_credits(machine, address, size, user):
    if address == symbols['SD_Call']:
        audio_calls.append(machine.reg_read(UC_ARM_REG_R0))
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

uc.hook_add(UC_HOOK_CODE, intercept_credits)
uc.mem_write(symbols['g_GameWork'] + 0x598, bytes(12))
uc.reg_write(UC_ARM_REG_SP, 0xff0000)
uc.reg_write(UC_ARM_REG_LR, stop)
uc.emu_start(entries[21], stop, count=10000)
steps = struct.unpack('<III', uc.mem_read(symbols['g_GameWork'] + 0x598, 12))
assert steps[:2] == (0, 1) and audio_calls == [18, 16], (steps, audio_calls)
print('ARM main-loop dispatch to credits initialization PASS')

# Credits restore the previous in-game state after framebuffer restoration.
restore_names = ('Screen_RectInterlacedClear', 'LoadImage', 'DrawSync', 'VSync')
restore_calls = []
def intercept_restore(machine, address, size, user):
    for name in restore_names:
        if address == symbols[name]:
            restore_calls.append(name)
            machine.reg_write(UC_ARM_REG_R0, 0)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
            return

uc.hook_add(UC_HOOK_CODE, intercept_restore)
uc.mem_write(symbols['g_GameWork'] + 0x590, struct.pack('<IIIII', 11, 21, 2, 10, 0))
uc.reg_write(UC_ARM_REG_SP, 0xff0000)
uc.reg_write(UC_ARM_REG_LR, stop)
uc.emu_start(symbols['func_801E3304'], stop, count=10000)
state = struct.unpack('<I', uc.mem_read(symbols['g_GameWork'] + 0x594, 4))[0]
assert state == 11 and restore_calls == ['Screen_RectInterlacedClear', 'LoadImage', 'LoadImage', 'DrawSync', 'VSync'], (state, restore_calls)
print('ARM credits restore previous in-game state PASS')
