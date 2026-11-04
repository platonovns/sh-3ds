"""Targeted Block 5 save and item dispatch fixtures."""
from pathlib import Path
import os
port=Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF']=str(port/'build/resort-probe/resort-probe.elf')
source=(port/'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]',1)[0]
source=source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/resort-probe'")
exec(source)
src=port/'tests/resort_probe.c';obj=out/'resort_probe.o';fixture=out/'resort-components.elf'
p=subprocess.run([prefix+'gcc',*shlex.split(flags),'-c',str(src),'-o',str(obj)],capture_output=True,text=True)
if p.returncode:raise RuntimeError(p.stderr)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),'-Wl,--undefined=resort_probe_save','-Wl,--undefined=resort_probe_wrong_use','-Wl,--undefined=resort_probe_stalker','-Wl,--undefined=resort_probe_romper','-Wl,--undefined=resort_probe_groaner',str(obj),'-o',str(fixture)],check=True)
raw2=fixture.read_bytes();off2=struct.unpack_from('<I',raw2,28)[0];size2,count2=struct.unpack_from('<HH',raw2,42)
for line in subprocess.check_output([prefix+'nm','-n',str(fixture)],text=True).splitlines():
 p=line.split()
 if len(p)==3 and p[2].startswith('resort_'):game.symbols[p[2]]=int(p[0],16)
r=Chapter()
for i in range(count2):
 typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw2,off2+i*size2)
 if typ==1 and length:r.uc.mem_write(addr,raw2[pos:pos+length])
for phase in range(8):
 r.reset('map5_s01',30);assert r.call('resort_probe_save',phase)==0,phase
 print('save roundtrip',phase,'PASS',flush=True)
for seq,(name,index,event) in enumerate([('map5_s01',30,23),('map5_s02',31,15),('map5_s03',32,12),('map5_s03',32,20)]):
 r.reset(name,index);r.uc.mem_write(game.symbols['g_TickCount'],struct.pack('<I',1000+2*seq));status=r.call('alchemilla_probe_use',event);print(name,event,'item dispatch',status,r.row(),flush=True)
 if status:raise SystemExit(1)
 r.reset(name,index);r.uc.mem_write(game.symbols['g_TickCount'],struct.pack('<I',1001+2*seq));assert r.call('resort_probe_wrong_use',event)==0,(name,event,'wrong location')
 print(name,event,'wrong location PASS',flush=True)
for n in ('ScreenFade_Start','Screen_BackgroundImgDraw'):
 if n in game.symbols:r.bridge(n,lambda *_:r.ret())
for n in ('ScreenFade_IsFinished','Fs_QueueChunksLoad'):
 if n in game.symbols:r.bridge(n,lambda *_:r.ret(1))
r.reset('map5_s03',32);r.call('alchemilla_probe_add',115)
r.call('alchemilla_probe_event',12,8)
assert r.call('alchemilla_probe_count',115)==0 and r.call('alchemilla_probe_count',116)==1 and r.call('alchemilla_probe_flag',390)==1
print('magnet consumed; motorcycle key acquired; flag 390 PASS',flush=True)
r.reset('map5_s03',32);r.call('alchemilla_probe_add',116)
r.call('alchemilla_probe_event',20,34)
assert r.call('alchemilla_probe_flag',391)==1 and r.call('alchemilla_probe_count',116)==1
print('motorcycle ending flag 391; key retained PASS',flush=True)
r.reset('map5_s02',31);r.call('alchemilla_probe_event',5,11)
assert r.call('alchemilla_probe_flag',380)==1 and r.call('alchemilla_probe_count',112)==1 and r.call('alchemilla_probe_count',113)==1
print('Kaufmann Key and Receipt awarded PASS',flush=True)
r.reset('map5_s01',30);r.call('alchemilla_probe_add',112);r.call('alchemilla_probe_event',23,0)
assert r.call('alchemilla_probe_count',112)==0 and r.call('alchemilla_probe_flag',394)==1
print('Kaufmann Key consumed at motel door PASS',flush=True)
r.reset('map5_s02',31);r.call('alchemilla_probe_add',114);r.call('alchemilla_probe_event',15,6)
assert r.call('alchemilla_probe_count',114)==1 and r.call('alchemilla_probe_flag',377)==1
print('Safe Key retained; safe flag PASS',flush=True)

r.reset('map5_s02',31)
for lethal in (0,1):
 r.call('resort_probe_stalker',lethal);row=struct.unpack('<4I',r.uc.mem_read(game.symbols['resort_stalker_out'],16));print('Stalker damage',lethal,row,flush=True);assert row[0]==350*4096 and row[1]==(0 if lethal else 340*4096)

r.bridge('Collision_SurfaceGet',lambda p,*_: (r.uc.mem_write(p,bytes(12)),r.ret()))
r.reset('map6_s00',33);r.call('RomperAnimInfos_Init')
for lethal in (0,1):

 try:r.call('resort_probe_romper',lethal)
 except Exception as ex: print('ROMPER EXCEPTION',ex,'pc',hex(r.uc.reg_read(game.UC_ARM_REG_PC)),'lr',hex(r.uc.reg_read(game.UC_ARM_REG_LR)),flush=True);raise
 row=struct.unpack('<6I',r.uc.mem_read(game.symbols['resort_romper_out'],24));print('Romper damage/death',lethal,row,flush=True);assert row[0]>0 and row[1]==(0 if lethal else row[0]-10*4096)
for value in (472,473):
 r.reset('map5_s01',30);r.bridge('map5_s01_func_800CD20C',lambda *_,value=value:r.ret(value))
 r.call('alchemilla_probe_event',8,5)
 assert r.call('alchemilla_probe_flag',371)==(value==473),(value,'lock')
 print('Indian Runner code',value,'accepted' if value==473 else 'rejected',flush=True)

r.reset('map6_s00',33)
for lethal in (0,1):
 r.call('resort_probe_groaner',lethal);row=struct.unpack('<3I',r.uc.mem_read(game.symbols['resort_groaner_out'],12));print('Groaner damage/death',lethal,row,flush=True);assert row[0]>0 and row[1]==(0 if lethal else row[0]-10*4096)
for name,index,event,item,flag in [('map5_s02',31,11,114,376),('map5_s03',32,11,115,386)]:
 r.reset(name,index);r.call('alchemilla_probe_pickup',event,2);r.call('alchemilla_probe_pickup',event,3)
 assert r.call('alchemilla_probe_count',item)==1 and r.call('alchemilla_probe_flag',flag)==1
 print(name,'pickup',item,'PASS',flush=True)
 r.reset(name,index);r.call('alchemilla_probe_pickup',event,2);r.call('alchemilla_probe_pickup',event,0xffffffff)
 assert r.call('alchemilla_probe_count',item)==0 and r.call('alchemilla_probe_flag',flag)==0
 print(name,'declined pickup',item,'PASS',flush=True)
