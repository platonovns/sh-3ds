"""Selected MAP5 ARM callable tables against the original USA BIN."""
from pathlib import Path
import os
port = Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF'] = os.environ.get('SH_SEWER1_ELF', str(port / 'build/sewer1-compile-probe/sewer1-probe.elf'))
exec((port / 'tools/test_block3_elf_tables.py').read_text().split('\ndisassembly =', 1)[0])

for name, table, n in [('map5_s00','HARRY_M5S00_ANIM_INFOS',31), ('map5_s01','HARRY_M5S01_ANIM_INFOS',35)]:
    original = asset(name)[address(name,table)-0x800C9578:]
    native = bytes(u.mem_read(symbols[name+'_'+table], n*16))
    for j in range(n):
        a,b = native[j*16:(j+1)*16],original[j*16:(j+1)*16]
        assert int.from_bytes(a[:4], 'little') == callbacks[int.from_bytes(b[:4], 'little')], (name,j,'playback')
        assert a[4:8] == b[4:8] and a[12:] == b[12:], (name,j,'record')
        if b[5]:
            assert int.from_bytes(b[8:12],'little') == 0x800706E4
            assert int.from_bytes(a[8:12],'little') == symbols['Player_VariableAnimDurationGet'], (name,j,'duration')
        else:
            assert a[8:12] == b[8:12], (name,j,'duration')
    checks.append(dict(map=name, table=table, entries=n, status='PASS'))

u.reg_write(UC_ARM_REG_SP, 0x1000000)
for table,n,init in [('HANGED_SCRATCHER_ANIM_INFOS',54,'HangedScratcherAnimInfos_Init'), ('CREEPER_ANIM_INFOS',36,'CreeperAnimInfos_Init')]:
    u.reg_write(UC_ARM_REG_LR, 0xF00000)
    u.emu_start(symbols[init], 0xF00000, count=1000000)
    original=asset('map5_s00')[address('map5_s00',table)-0x800C9578:]
    native=bytes(u.mem_read(symbols[table],n*16))
    for j in range(n):
        a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
        assert a[4:]==b[4:] and int.from_bytes(a[:4],'little')==callbacks[int.from_bytes(b[:4],'little')], (table,j)
    checks.append(dict(map='map5_s00', table=table, entries=n, status='PASS'))
differences=[]
for table,n,init in [('GROANER_ANIM_INFOS',48,'GroanerAnimInfos_Init'),('ROMPER_ANIM_INFOS',44,'RomperAnimInfos_Init')]:
    u.reg_write(UC_ARM_REG_LR,0xF00000)
    u.emu_start(symbols[init],0xF00000,count=1000000)
    if table=='GROANER_ANIM_INFOS':
        u.reg_write(UC_ARM_REG_LR,0xF00000)
        u.emu_start(symbols['GroanerM5S01AnimInfos_Init'],0xF00000,count=1000000)
    original=asset('map5_s01')[address('map5_s01',table)-0x800C9578:]
    native=bytes(u.mem_read(symbols['GROANER_M5S01_ANIM_INFOS' if table=='GROANER_ANIM_INFOS' else table],n*16))
    for j in range(n):
        a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
        if a[4:]!=b[4:] or int.from_bytes(a[:4],'little')!=callbacks[int.from_bytes(b[:4],'little')]:
            print('MISMATCH',table,j,a.hex(),b.hex(),flush=True)
            differences.append((table,j,a.hex(),b.hex()))
    checks.append(dict(map='map5_s01',table=table,entries=n,status='PASS'))
assert not differences,differences
name='map5_s01'
original=asset(name)[address(name,'sharedData_800CAA98_0_s01')-0x800C9578:]
native=bytes(u.mem_read(symbols[name+'_AIR_SCREAMER_ANIM_INFOS'],56*16))
variable={address(name,'sharedFunc_800D7714_0_s01'):symbols[name+'_sharedFunc_800D7714_0_s01'],
          address(name,'sharedFunc_800D77D0_0_s01'):symbols[name+'_sharedFunc_800D77D0_0_s01']}
for j in range(56):
    a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
    assert int.from_bytes(a[:4],'little')==callbacks[int.from_bytes(b[:4],'little')],('air playback',j)
    assert a[4:8]==b[4:8] and a[12:]==b[12:],('air scalar',j)
    if b[5]: assert int.from_bytes(a[8:12],'little')==variable[int.from_bytes(b[8:12],'little')],('air duration',j)
    else: assert a[8:12]==b[8:12],('air duration',j)
checks.append(dict(map=name,table='AIR_SCREAMER_ANIM_INFOS',entries=56,status='PASS'))
def dispatch(original_symbol,native_symbol,original_targets,native_targets):
    start=address(name,original_symbol)-0x800C9578
    original=struct.unpack('<'+'I'*len(original_targets),asset(name)[start:start+4*len(original_targets)])
    native=struct.unpack('<'+'I'*len(native_targets),bytes(u.mem_read(symbols[name+'_'+native_symbol],4*len(native_targets))))
    assert original==tuple(0 if t is None else address(name,t) for t in original_targets),(name,original_symbol,'retail')
    assert native==tuple(0 if t is None else symbols[name+'_'+t] for t in native_targets),(name,native_symbol,'native')
    checks.append(dict(map=name,table=native_symbol,entries=len(native_targets),status='PASS'))
air=[{3:'AirScreamer_ControlStandIdle',16:'AirScreamer_ControlRecoil',17:'AirScreamer_ControlStun',33:'AirScreamer_ControlGlide'}.get(i,f'AirScreamer_Control_{i}') for i in range(52)]
dispatch('g_AirScreamer_ControlFuncs','g_Ai_AirScreamer_ControlFuncs',air,[f'Ai_AirScreamer_Control_{i}' for i in range(52)])
groaner=[None,'Groaner_ControlWalkForward','Groaner_ControlRunForward','Groaner_ControlJumpAttack','Groaner_Control4','Groaner_ControlStandRecoil','Groaner_ControlStun','Groaner_ControlStun','Groaner_ControlStun','Groaner_ControlDeath']
groaner_native=[None,'sharedFunc_800E39D8_2_s00','sharedFunc_800E3E94_2_s00','sharedFunc_800E4830_2_s00','sharedFunc_800E4E84_2_s00','sharedFunc_800E554C_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E5930_2_s00']
dispatch('sharedData_800EEE14_2_s00','sharedData_800EEE14_2_s00',groaner,groaner_native)
romper=[None,'Romper_Control_1','Romper_ControlWalkForward','Romper_Control_3','Romper_Control_4','Romper_ControlJump','Romper_Control_6','Romper_Control_7','Romper_Control_8','Romper_Control_9','Romper_Control_10','Romper_ControlGrabAttack']
dispatch('g_Romper_ControlFuncs','g_Romper_ControlFuncs',romper,romper)

for name, targets in [('map5_s00', ['func_800D67F4','func_800D6888','func_800D69DC','MapEvent_CommonItemTake','MapEvent_SewerKeyTake','func_800D6B00','func_800D732C','func_800D75FC','func_800D7940','func_800D7C84','func_800D7F88','MapEvent_PaperMapTake']), ('map5_s01',['MapEvent_DoorJammed','MapEvent_DoorLocked','MapEvent_CommonItemTake','func_800EBA40','MapEvent_PaperMapTake','func_800EBF70','func_800EC2D8','func_800EC42C'])]:
    native=struct.unpack('<'+'I'*len(targets),bytes(u.mem_read(symbols[name+'_g_MapEventFuncs'],4*len(targets))))
    assert native == tuple(symbols[name+'_'+t] for t in targets), (name,native)
    checks.append(dict(map=name,table='g_MapEventFuncs',entries=len(targets),status='PASS'))
for name, count in [('map2_s00',201),('map2_s02',42),('map5_s00',52),('map5_s01',44)]:
    original=asset(name)[address(name,'MAP_EVENTS')-0x800C9578:][:count*12]
    native=bytes(u.mem_read(symbols[name+'_MAP_EVENTS'],count*12))
    for i in range(count):
        a,b=native[i*12:(i+1)*12],original[i*12:(i+1)*12]
        assert a==b,(name,i,a.hex(),b.hex())
    checks.append(dict(map=name,table='MAP_EVENTS',entries=count,status='PASS'))
out=dict(status='PASS',scope=__doc__,elf_sha256=hashlib.sha256(data).hexdigest(),checks=checks)
(elf.parent/'sewer1-tables.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
