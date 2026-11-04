"""Audit selected linked ARM callback tables against original USA BIN records.

This verifies the listed player, actor and enemy animation records and selected
AI dispatch tables; it is not a complete callback audit or a gameplay test.
"""
from pathlib import Path
import hashlib, json, os, re, struct, subprocess, sys

port = Path(__file__).resolve().parents[1]
root = port.parent
sys.path.insert(0, str(root.parent / '.toolchain/python-deps'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR

elf = Path(os.environ.get('SH_BLOCK3_ELF',str(port / 'build/block3-compile-probe/block3-probe.elf')))
(elf.parent/'tables.json').unlink(missing_ok=True)
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
symbols = {p[2]: int(p[0], 16) for line in subprocess.check_output([prefix+'nm','-n',str(elf)], text=True).splitlines()
           if len(p := line.split()) == 3}
data = elf.read_bytes()
offset = struct.unpack_from('<I', data, 28)[0]
size, count = struct.unpack_from('<HH', data, 42)
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
u.mem_map(0x10000, 0x1000000)
for i in range(count):
    kind, pos, addr, _, fsize, _, _, _ = struct.unpack_from('<8I', data, offset + i * size)
    if kind == 1 and fsize:
        u.mem_write(addr, data[pos:pos+fsize])

ft = (root / 'src/main/filetable.c.USA.inc').read_text()
disc = Path(os.environ.get('SH_DISC', str(root.parent/'silent-hill-decomp/sh1_data/sh1.bin')))
def asset(name):
    m = re.search(r'\{\s*(0x[0-9a-fA-F]+),\s*(\d+).*// VIN/' + name.upper() + r'.BIN', ft)
    lba, length = int(m[1],16), int(m[2])*256
    result = bytearray()
    with disc.open('rb') as f:
        while len(result) < length:
            f.seek(lba*2352+24)
            result.extend(f.read(2048))
            lba += 1
    return result[:length]
def address(name, symbol):
    text = (root/'configs/USA/maps'/('sym.'+name+'.txt')).read_text()
    return int(re.search(r'^'+symbol+r'\s*=\s*(0x\w+)', text, re.M)[1],16)

callbacks = {0: 0, 0x80044CA4: symbols['Anim_BlendLinear'],
             0x800449F0: symbols['Anim_PlaybackOnce'], 0x80044B38: symbols['Anim_PlaybackLoop']}
checks = []
disassembly = subprocess.check_output([prefix+'objdump','-dr','--disassemble=map4_s04_Lisa_Update',str(elf)],text=True)
assert 'R_ARM_ABS32\tLISA_ANIM_INFOS' in disassembly and '\tbx\t' in disassembly, 'Lisa native table dispatch linkage'
checks.append(dict(map='map4_s04',table='Lisa_Update -> LISA_ANIM_INFOS',status='PASS'))
for i,n in enumerate((31,35,31,13,25),1):
    name = f'map4_s{i:02d}'
    table = f'HARRY_M4S{i:02d}_ANIM_INFOS'
    original = asset(name)[address(name,table)-0x800C9578:]
    native = bytes(u.mem_read(symbols[name+'_'+table], n*16))
    for j in range(n):
        a, b = native[j*16:(j+1)*16], original[j*16:(j+1)*16]
        assert int.from_bytes(a[:4],'little') == callbacks[int.from_bytes(b[:4],'little')], (name,j,'playback')
        if b[5]:
            assert a[4:8] == b[4:8] and a[12:] == b[12:], (name,j,'scalar')
            assert int.from_bytes(b[8:12],'little') == 0x800706E4, (name,j,'original variable callback')
            assert int.from_bytes(a[8:12],'little') == symbols['Player_VariableAnimDurationGet'], (name,j,'native variable callback')
        else:
            assert a[4:] == b[4:], (name,j,'scalar',a.hex(),b.hex())
    checks.append(dict(map=name,table=table,entries=n,status='PASS'))

name, table, n = 'map4_s01', 'CYBIL_ANIM_INFOS', 64
original = asset(name)[address(name,table)-0x800C9578:]
native = bytes(u.mem_read(symbols[table], n*16))
for j in range(n):
    a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
    assert a[4:] == b[4:] and int.from_bytes(a[:4],'little') == callbacks[int.from_bytes(b[:4],'little')], (name,table,j)
checks.append(dict(map=name,table=table,entries=n,status='PASS'))

name = 'map4_s02'
original = asset(name)[address(name, 'sharedData_800CAA98_0_s01')-0x800C9578:]
native = bytes(u.mem_read(symbols[name+'_AIR_SCREAMER_ANIM_INFOS'],56*16))
variable = {address(name, 'sharedFunc_800D7714_0_s01'): symbols[name+'_sharedFunc_800D7714_0_s01'],
            address(name, 'sharedFunc_800D77D0_0_s01'): symbols[name+'_sharedFunc_800D77D0_0_s01']}
for j in range(56):
    a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
    assert int.from_bytes(a[:4],'little')==callbacks[int.from_bytes(b[:4],'little')], (name,'air playback',j)
    assert a[4:8]==b[4:8] and a[12:]==b[12:], (name,'air scalar',j,a.hex(),b.hex())
    if b[5]:
        assert int.from_bytes(a[8:12],'little')==variable[int.from_bytes(b[8:12],'little')], (name,'air variable',j)
    else:
        assert a[8:12]==b[8:12], (name,'air duration',j)
checks.append(dict(map=name,table='AIR_SCREAMER_ANIM_INFOS',entries=56,status='PASS'))

u.reg_write(UC_ARM_REG_SP, 0x1000000)
for mapname,table,n,init in [('map4_s04','LISA_ANIM_INFOS',36,'LisaAnimInfos_Init'),
                              ('map4_s03','TWINFEELER_ANIM_INFOS',48,'TwinfeelerAnimInfos_Init'),
                              ('map4_s05','FLOATSTINGER_ANIM_INFOS',26,'FloatstingerAnimInfos_Init')]:
    u.reg_write(UC_ARM_REG_LR,0xF00000)
    u.emu_start(symbols[init],0xF00000,count=1000000)
    original=asset(mapname)[address(mapname,table)-0x800C9578:]
    native=bytes(u.mem_read(symbols[table],n*16))
    for j in range(n):
        a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
        assert a[4:]==b[4:] and int.from_bytes(a[:4],'little')==callbacks[int.from_bytes(b[:4],'little')], (mapname,table,j)
    checks.append(dict(map=mapname,table=table,entries=n,status='PASS'))
differences=[]
for table,n,init in [('GROANER_ANIM_INFOS',48,'GroanerAnimInfos_Init'),
                     ('ROMPER_ANIM_INFOS',44,'RomperAnimInfos_Init')]:
    u.reg_write(UC_ARM_REG_LR,0xF00000)
    u.emu_start(symbols[init],0xF00000,count=1000000)
    if table == 'GROANER_ANIM_INFOS':
        u.reg_write(UC_ARM_REG_LR,0xF00000)
        u.emu_start(symbols['GroanerM4S02AnimInfos_Init'],0xF00000,count=1000000)
    original=asset(name)[address(name,table)-0x800C9578:]
    native=bytes(u.mem_read(symbols['GROANER_M4S02_ANIM_INFOS' if table == 'GROANER_ANIM_INFOS' else table],n*16))
    for j in range(n):
        a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
        if a[4:]!=b[4:] or int.from_bytes(a[:4],'little')!=callbacks[int.from_bytes(b[:4],'little')]:
            differences.append((name,table,j,a.hex(),b.hex()))
    checks.append(dict(map=name,table=table,entries=n,status='PASS'))
assert not differences,differences

def dispatch(mapname, original_symbol, native_symbol, original_targets, native_targets):
    blob=asset(mapname);start=address(mapname,original_symbol)-0x800C9578
    original=struct.unpack('<'+'I'*len(original_targets),blob[start:start+4*len(original_targets)])
    native=struct.unpack('<'+'I'*len(native_targets),bytes(u.mem_read(symbols[mapname+'_'+native_symbol],4*len(native_targets))))
    expected_orig=tuple(0 if target is None else address(mapname,target) for target in original_targets)
    expected_native=tuple(0 if target is None else symbols[mapname+'_'+target] for target in native_targets)
    assert original==expected_orig,(mapname,original_symbol,'retail',original,expected_orig)
    assert native==expected_native,(mapname,native_symbol,'native',native,expected_native)
    checks.append(dict(map=mapname,table=native_symbol,entries=len(native_targets),status='PASS'))

air_original=[{3:'AirScreamer_ControlStandIdle',16:'AirScreamer_ControlRecoil',17:'AirScreamer_ControlStun',33:'AirScreamer_ControlGlide'}.get(i,f'AirScreamer_Control_{i}') for i in range(52)]
dispatch(name,'g_AirScreamer_ControlFuncs','g_Ai_AirScreamer_ControlFuncs',air_original,
         [f'Ai_AirScreamer_Control_{i}' for i in range(52)])
groaner_orig=[None,'Groaner_ControlWalkForward','Groaner_ControlRunForward','Groaner_ControlJumpAttack',
              'Groaner_Control4','Groaner_ControlStandRecoil','Groaner_ControlStun','Groaner_ControlStun',
              'Groaner_ControlStun','Groaner_ControlDeath']
groaner_native=[None,'sharedFunc_800E39D8_2_s00','sharedFunc_800E3E94_2_s00','sharedFunc_800E4830_2_s00',
                'sharedFunc_800E4E84_2_s00','sharedFunc_800E554C_2_s00','sharedFunc_800E55B0_2_s00',
                'sharedFunc_800E55B0_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E5930_2_s00']
dispatch(name,'sharedData_800EEE14_2_s00','sharedData_800EEE14_2_s00',groaner_orig,groaner_native)
romper=[None,'Romper_Control_1','Romper_ControlWalkForward','Romper_Control_3','Romper_Control_4',
        'Romper_ControlJump','Romper_Control_6','Romper_Control_7','Romper_Control_8','Romper_Control_9',
        'Romper_Control_10','Romper_ControlGrabAttack']
dispatch(name,'g_Romper_ControlFuncs','g_Romper_ControlFuncs',romper,romper)

original=asset('map4_s05')[0x800D7A04-0x800C9578:][:28]
expected=(0,0,0x800D1BF8,0x800D2B90,0x800D341C,0x800D3424,0x800D3564)
assert struct.unpack('<7I',original)==expected
native=struct.unpack('<7I',bytes(u.mem_read(symbols['map4_s05_D_800D7A04'],28)))
targets=(None,None,'func_800D1BF8','func_800D2B90','Floatstinger_NoOpDispatch','func_800D3424','func_800D3564')
assert native==tuple(0 if target is None else symbols['map4_s05_'+target] if target != 'Floatstinger_NoOpDispatch' else symbols[target] for target in targets),native
checks.append(dict(map='map4_s05',table='D_800D7A04',entries=7,status='PASS'))
out=dict(status='PASS',scope=__doc__,elf_sha256=hashlib.sha256(data).hexdigest(),checks=checks)
(elf.parent/'tables.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
