"""Compare Block 5 animation and event records against the USA disc."""
from pathlib import Path
import os
port = Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF'] = str(port/'build/resort-probe/resort-probe.elf')
exec((port/'tools/test_block3_elf_tables.py').read_text().split('\ndisassembly =',1)[0])
errors=[]
def anim(name,table,n,native,initializer=None):
    if initializer:
        u.reg_write(UC_ARM_REG_SP,0x1000000);u.reg_write(UC_ARM_REG_LR,0xF00000)
        u.emu_start(symbols[initializer],0xF00000,count=1000000)
    original=asset(name)[address(name,table)-0x800C9578:]
    buf=bytes(u.mem_read(symbols[native],n*16))
    for j in range(n):
        a,b=buf[j*16:(j+1)*16],original[j*16:(j+1)*16]
        ok=int.from_bytes(a[:4],'little') == callbacks.get(int.from_bytes(b[:4],'little'),-1) and a[4:8]==b[4:8] and a[12:]==b[12:]
        if b[5]: ok=ok and int.from_bytes(a[8:12],'little')==symbols['Player_VariableAnimDurationGet'] and int.from_bytes(b[8:12],'little')==0x800706e4
        else: ok=ok and a[8:12]==b[8:12]
        if not ok: errors.append((name,table,j,a.hex(),b.hex()))
    print(name,table,'differences',sum(x[0]==name and x[1]==table for x in errors),flush=True)
for name,n in [('map5_s02',39),('map5_s03',31),('map6_s00',43),('map6_s01',13)]:
    tab='HARRY_M'+name[3:].replace('_','').upper()+'_ANIM_INFOS'
    if n: anim(name,tab,n,name+'_'+tab)
for name,table,n,init in [('map5_s02','KAUFMANN_ANIM_INFOS',46,'KaufmannAnimInfos_Init'),('map5_s03','KAUFMANN_ANIM_INFOS',46,'KaufmannAnimInfos_Init'),('map6_s01','DAHLIA_ANIM_INFOS',52,'DahliaAnimInfos_Init'),('map6_s01','CYBIL_ANIM_INFOS',64,None),('map6_s00','GROANER_ANIM_INFOS',48,'GroanerAnimInfos_Init'),('map6_s00','ROMPER_ANIM_INFOS',44,'RomperAnimInfos_Init')]:
    anim(name,table,n,({'map5_s02':'KAUFMANN_M5S02_ANIM_INFOS','map6_s01:DAHLIA_ANIM_INFOS':'DAHLIA_M6S01_ANIM_INFOS','map6_s01:CYBIL_ANIM_INFOS':'CYBIL_M6S01_ANIM_INFOS','map6_s00:GROANER_ANIM_INFOS':'GROANER_M6S00_ANIM_INFOS'}.get(name+':'+table, {'map5_s02':'KAUFMANN_M5S02_ANIM_INFOS'}.get(name, table))), 'ResortAnimInfos_Init' if name in ('map5_s02','map6_s00','map6_s01') and table != 'ROMPER_ANIM_INFOS' else init)
anim('map5_s02','STALKER_ANIM_INFOS',96,'STALKER_M5S02_ANIM_INFOS','StalkerM5S02AnimInfos_Init')
for name,n in [('map5_s02',21),('map5_s03',46),('map6_s00',24),('map6_s01',17)]:
    original=asset(name)[address(name,'MAP_EVENTS')-0x800C9578:][:n*12]
    native=bytes(u.mem_read(symbols[name+'_MAP_EVENTS'],n*12))
    for i in range(n):
        if native[i*12:(i+1)*12]!=original[i*12:(i+1)*12]:errors.append((name,'MAP_EVENTS',i,native[i*12:(i+1)*12].hex(),original[i*12:(i+1)*12].hex()))
    print(name,'events differences',sum(x[0]==name and x[1]=='MAP_EVENTS' for x in errors),flush=True)
print('errors:',errors,flush=True)
if errors: raise SystemExit(1)
# Native AI dispatches and their retail target correspondence.
name='map6_s00'
def dispatch(original_symbol,native_symbol,original_targets,native_targets):
 start=address(name,original_symbol)-0x800C9578
 original=struct.unpack('<'+'I'*len(original_targets),asset(name)[start:start+4*len(original_targets)])
 native=struct.unpack('<'+'I'*len(native_targets),bytes(u.mem_read(symbols[name+'_'+native_symbol],4*len(native_targets))))
 assert original==tuple(0 if t is None else address(name,t) for t in original_targets),(name,original_symbol,'retail')
 assert native==tuple(0 if t is None else symbols[name+'_'+t] for t in native_targets),(name,native_symbol,'native')
air=[{3:'AirScreamer_ControlStandIdle',16:'AirScreamer_ControlRecoil',17:'AirScreamer_ControlStun',33:'AirScreamer_ControlGlide'}.get(i,f'AirScreamer_Control_{i}') for i in range(52)]
dispatch('g_AirScreamer_ControlFuncs','g_Ai_AirScreamer_ControlFuncs',air,[f'Ai_AirScreamer_Control_{i}' for i in range(52)])
groaner=[None,'Groaner_ControlWalkForward','Groaner_ControlRunForward','Groaner_ControlJumpAttack','Groaner_Control4','Groaner_ControlStandRecoil','Groaner_ControlStun','Groaner_ControlStun','Groaner_ControlStun','Groaner_ControlDeath']
groaner_native=[None,'sharedFunc_800E39D8_2_s00','sharedFunc_800E3E94_2_s00','sharedFunc_800E4830_2_s00','sharedFunc_800E4E84_2_s00','sharedFunc_800E554C_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E55B0_2_s00','sharedFunc_800E5930_2_s00']
dispatch('sharedData_800EEE14_2_s00','sharedData_800EEE14_2_s00',groaner,groaner_native)
romper=[None,'Romper_Control_1','Romper_ControlWalkForward','Romper_Control_3','Romper_Control_4','Romper_ControlJump','Romper_Control_6','Romper_Control_7','Romper_Control_8','Romper_Control_9','Romper_Control_10','Romper_ControlGrabAttack']
dispatch('g_Romper_ControlFuncs','g_Romper_ControlFuncs',romper,romper)
print('AI dispatch tables PASS',flush=True)
original=asset(name)[address(name,'sharedData_800CAA98_0_s01')-0x800C9578:]
native=bytes(u.mem_read(symbols[name+'_AIR_SCREAMER_ANIM_INFOS'],56*16))
variable={address(name,'sharedFunc_800D7714_0_s01'):symbols[name+'_sharedFunc_800D7714_0_s01'],address(name,'sharedFunc_800D77D0_0_s01'):symbols[name+'_sharedFunc_800D77D0_0_s01']}
for j in range(56):
 a,b=native[j*16:(j+1)*16],original[j*16:(j+1)*16]
 assert int.from_bytes(a[:4],'little')==callbacks[int.from_bytes(b[:4],'little')],('air playback',j)
 assert a[4:8]==b[4:8] and a[12:]==b[12:],('air scalar',j)
 if b[5]:assert int.from_bytes(a[8:12],'little')==variable[int.from_bytes(b[8:12],'little')],('air duration',j)
 else:assert a[8:12]==b[8:12],('air duration',j)
print('Air Screamer animation callbacks PASS',flush=True)
# Every new event-table pointer: compare retail target identity and native address.
for name in ('map5_s02','map5_s03','map6_s00','map6_s01'):
 header=(root/'src/maps'/name/(name+'_header.c')).read_text()
 body=re.search(r'void \(\*g_MapEventFuncs\[\]\)\(\)\s*=\s*\{(.*?)\};',header,re.S)[1]
 targets=[t.strip().split()[0] for t in body.split(',') if t.strip()]
 orig=struct.unpack('<'+'I'*len(targets),asset(name)[address(name,'g_MapEventFuncs')-0x800C9578:][:len(targets)*4])
 native=struct.unpack('<'+'I'*len(targets),bytes(u.mem_read(symbols[name+'_g_MapEventFuncs'],len(targets)*4)))
 for i,target in enumerate(targets):
  if target=='NULL':expected=0;expect_native=0
  else:
   match=re.fullmatch(r'func_([0-9A-Fa-f]{8})',target)
   expected=int(match[1],16) if match else address(name,target)
   expect_native=symbols[name+'_'+target]
  assert orig[i]==expected and native[i]==expect_native,(name,i,target,hex(orig[i]),hex(expected),hex(native[i]),hex(expect_native))
 print(name,'retail and native event function targets PASS',flush=True)
