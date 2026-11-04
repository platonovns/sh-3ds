"""Retail MIPS/native Air Screamer score and target geometry on a flat fixture.
Distance is an exact collinear input; world collision and the later target
postprocessor are isolated equally. This does not claim full state-47 acceptance.
"""
import hashlib,json,os,re,shlex,struct,subprocess
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0
from unicorn import UC_HOOK_CODE
from retail_mips import Retail,SYMBOLS,PORT,ROOT
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'air_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-');p=PORT
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0]);obj=p/'build/stage10_air_reference_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_air_reference_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage10_air_'):ns['symbols'][s[2]]=int(s[0],16)
m=ns['Machine']()
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
r=Retail()
# Original assets live in SILENT./HILL. archives, indexed by the executable's
# table, rather than ISO directories. Read the retail MAP0_S01 entry directly.
entry=bytes(r.uc.mem_read((SYMBOLS['g_FileTable']&0x1fffffff)+1996*12,12))
location=struct.unpack_from('<I',entry)[0];sector=location&0x7ffff;length=((location>>19)&4095)*256
with (ROOT/'sh1_data/sh1.bin').open('rb') as f:
    overlay=bytearray()
    for i in range((length+2047)//2048):
        f.seek((sector+i)*2352+24);overlay.extend(f.read(2048))
overlay=bytes(overlay[:length])
expected=re.search(r'sha1:\s*(\w+)',(ROOT/'configs/USA/maps/map0_s01.yaml').read_text())[1]
assert hashlib.sha1(overlay).hexdigest()==expected
r.uc.mem_write(0xc9578,overlay)
trace=[]
def pc_trace(u,address,size,unused):
    trace.append((hex(address),bytes(u.mem_read(address&0x1fffffff,4)).hex()))
    if len(trace)>16:trace.pop(0)
r.uc.hook_add(UC_HOOK_CODE,pc_trace)
for name,address in re.findall(r'^(\w+)\s*=\s*(0x[0-9A-Fa-f]+)',(ROOT/'configs/USA/maps/sym.map0_s01.txt').read_text(),re.M):SYMBOLS[name]=int(address,16)
for name,value in [('Collision_GroundHeightGet',0),('sharedFunc_800D4E84_0_s01',0)]:
    r.hook(name,lambda *_,v=value:r.ret(v))
    native='map0_s01_'+name if name.startswith('sharedFunc_') else name
    m.hook(native,lambda *_,v=value:(m.uc.reg_write(UC_ARM_REG_R0,v&0xffffffff),m.ret()))
layout=struct.unpack('<2I',m.uc.mem_read(ns['symbols']['stage10_air_layout'],8));cases=[]
distance=[0]
r.hook('Math_Distance2dGet',lambda *_:r.ret(distance[0]))
m.hook('Math_Distance2dGet',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,distance[0]),m.ret()))
for d in (2048,4096,8192,16384,28672):
    distance[0]=d
    for yaw in (0,512,1024,1536,2048,3072):
        for enemy_yaw in (0,1024,2048):
            enemy=m.call('stage10_air_setup',yaw,d,enemy_yaw)
            r.uc.mem_write(SYMBOLS['g_SysWork']&0x1fffffff,bytes(m.uc.mem_read(ns['symbols']['g_SysWork'],layout[0])))
            r.uc.mem_write(SYMBOLS['g_Player_IsAiming']&0x1fffffff,b'\0\0')
            original_enemy=SYMBOLS['g_SysWork']+layout[1]
            try:score=r.call('sharedFunc_800D3814_0_s01',original_enemy)
            except Exception:
                print(json.dumps(dict(failed_trace=trace)),flush=True);raise
            native=m.call('map0_s01_sharedFunc_800D3814_0_s01',enemy)
            assert score==native,(d,yaw,enemy_yaw,score,native)
            r.call('sharedFunc_800D53AC_0_s01',original_enemy);m.call('map0_s01_sharedFunc_800D53AC_0_s01',enemy)
            target=bytes(r.uc.mem_read((original_enemy&0x1fffffff)+0xf8,12))
            actual=bytes(m.uc.mem_read(enemy+0xf8,12));assert actual==target,(d,yaw,enemy_yaw,target.hex(),actual.hex())
            cases.append(dict(distance=d,player_yaw=yaw,enemy_yaw=enemy_yaw,score=score,
                score_meets_2m=score>=8192,target=list(struct.unpack('<3i',target))))
report=dict(status='PASS',scope=__doc__,cases=cases,retail_overlay_sha1=expected,
    elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_accepted=False)
(p/'reports/stage10-air-retail-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='PASS',cases=len(cases),front_back=[c for c in cases if c['distance']==8192 and c['enemy_yaw']==0]),indent=2))
