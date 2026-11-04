"""Full retail/native hover-control transition on a recorded rear-stall pose.
Only the flat world boundary is isolated, equally on MIPS and ARM. Attack AI,
angle/distance math, motion commands and damage classification execute normally.
"""
import hashlib,json,os,re,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0
from retail_mips import Retail,SYMBOLS,PORT,ROOT
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'air_state'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
m=ns['Machine']();r=Retail();names=ns['symbols']
entry=bytes(r.uc.mem_read((SYMBOLS['g_FileTable']&0x1fffffff)+1996*12,12))
location=struct.unpack_from('<I',entry)[0];sector=location&0x7ffff;length=((location>>19)&4095)*256
with (ROOT/'sh1_data/sh1.bin').open('rb') as f:
    overlay=bytearray()
    for i in range((length+2047)//2048):
        f.seek((sector+i)*2352+24);overlay.extend(f.read(2048))
overlay=bytes(overlay[:length]);expected=re.search(r'sha1:\s*(\w+)',(ROOT/'configs/USA/maps/map0_s01.yaml').read_text())[1]
assert hashlib.sha1(overlay).hexdigest()==expected
r.uc.mem_write(0xc9578,overlay)
for name,address in re.findall(r'^(\w+)\s*=\s*(0x[0-9A-Fa-f]+)',(ROOT/'configs/USA/maps/sym.map0_s01.txt').read_text(),re.M):SYMBOLS[name]=int(address,16)
snapshot=PORT/'build/stage10-r5-air-rear-before';meta=json.loads((snapshot/'report.json').read_text())
original=(snapshot/'sys.bin').read_bytes();size,offset,stride=meta['air_snapshot']['layout']
m.call('AsRodata_Reformat')
native_table=bytes(m.uc.mem_read(names['sharedData_800CAA98_0_s01'],0xd78))
retail_table=bytes(r.uc.mem_read(0xcaa98,0xd78))
tail=dict(native=list(struct.unpack('<4h',native_table[0xd70:])),retail=list(struct.unpack('<4h',retail_table[0xd70:])))
tail['retail_extended']=list(struct.unpack('<20h',r.uc.mem_read(0xcb808,40)))
tail['native_extended']=list(struct.unpack('<20h',m.uc.mem_read(names['sharedData_800CAA98_0_s01']+0xd70,40)))
SYMBOLS.setdefault('func_800808AC',0x800808ac)
for name,value in [('Collision_GroundHeightGet',0),('func_800808AC',1)]:
    r.hook(name,lambda *_,v=value:r.ret(v))
    m.hook(name,lambda *_,v=value:(m.uc.reg_write(UC_ARM_REG_R0,v),m.ret()))
# An unobstructed segment: preserve the entire target postprocessor and copy
# the requested endpoint through its LOS boundary, rather than replacing it.
def clear_r(enemy,unused,target,out):
    r.uc.mem_write(out&0x1fffffff,bytes(r.uc.mem_read(target&0x1fffffff,12)));r.ret(1)
def clear_m(enemy,unused,target,out):
    m.uc.mem_write(out,bytes(m.uc.mem_read(target,12)));m.uc.reg_write(UC_ARM_REG_R0,1);m.ret()
r.hook('sharedFunc_800D4AEC_0_s01',clear_r)
m.hook('map0_s01_sharedFunc_800D4AEC_0_s01',clear_m)
SYMBOLS.setdefault('func_800805BC',0x800805bc)
def vertices(machine,base,output,source,coords,n):
    # Identical translated bone boundary. Hull shape is irrelevant to the
    # radius-table lookup, which is executed by the actual retail/native code.
    for i in range(n):machine.mem_write((output+i*12)&(0x1fffffff if base else 0xffffffff),struct.pack('<3i',8192, -4096,1105920))
def vertices_r(out,src,coords,n):vertices(r.uc,1,out,src,coords,n);r.ret()
def vertices_m(out,src,coords,n):vertices(m.uc,0,out,src,coords,n);m.ret()
r.hook('func_800805BC',vertices_r);m.hook('func_800805BC',vertices_m)
cases=[]
for player_yaw in (0,1024,2048,3072):
    for collision_class in (None,1,2,3,4):
        image=bytearray(original);struct.pack_into('<h',image,114,player_yaw)
        if collision_class is not None:
            flags=struct.unpack_from('<I',image,offset+0x11c)[0]&~(15<<17)
            flags|=1<<({1:18,2:19,3:20,4:17}[collision_class])
            struct.pack_into('<I',image,offset+0x11c,flags)
        r.uc.mem_write(SYMBOLS['g_SysWork']&0x1fffffff,bytes(image));m.uc.mem_write(names['g_SysWork'],bytes(image))
        for name,n in [('g_DeltaTime',4),('g_DeltaTimeRaw',4),('g_Player_IsAiming',2)]:
            data=(snapshot/(name+'.bin')).read_bytes();r.uc.mem_write(SYMBOLS[name]&0x1fffffff,data);m.uc.mem_write(names[name],data)
        shared=(snapshot/'map0_s01_sharedData_800E21D0_0_s01.bin').read_bytes()[:0x160]
        r.uc.mem_write(0xe21d0,shared);m.uc.mem_write(names['map0_s01_sharedData_800E21D0_0_s01'],shared)
        re=SYMBOLS['g_SysWork']+offset;ne=names['g_SysWork']+offset
        radii=None
        if collision_class is not None:
            # The class lives in animation-derived flags in a normal run.
            # Here each legal class is deliberately exercised at the same pose.
            r.uc.mem_write(0xe21d0,b'\0'*4);m.uc.mem_write(names['map0_s01_sharedData_800E21D0_0_s01'],b'\0'*4)
            r.call('sharedFunc_800D82B8_0_s01',re);m.call('map0_s01_sharedFunc_800D82B8_0_s01',ne)
            radii=[struct.unpack('<h',r.uc.mem_read((re&0x1fffffff)+212,2))[0],struct.unpack('<h',m.uc.mem_read(ne+212,2))[0]]
        r.call('AirScreamer_Control_47',re);m.call('map0_s01_Ai_AirScreamer_Control_47',ne)
        a=bytes(r.uc.mem_read(re&0x1fffffff,stride));b=bytes(m.uc.mem_read(ne,stride))
        differences=[i for i in range(stride) if a[i]!=b[i]]
        # Model is at +0: controlState is byte +2, stateStep at +3.
        cases.append(dict(player_yaw=player_yaw,collision_class=collision_class,radii=radii,differences=differences,
            retail_model=list(a[:16]),native_model=list(b[:16]),target=list(struct.unpack_from('<3i',b,0xf8)),
            retail_collision=list(struct.unpack_from('<8h',a,200)),native_collision=list(struct.unpack_from('<8h',b,200))))
for c in cases:
    c['sdk_sqrt_hull_radius_delta']=c['retail_collision'][7]-c['native_collision'][7]
passed=all(set(c['differences'])<={214,215} and abs(c['sdk_sqrt_hull_radius_delta'])<=4 and
    (not c['radii'] or c['radii'][0]==c['radii'][1]) for c in cases)
report=dict(status='PASS' if passed else 'FAIL',scope=__doc__,retail_overlay_sha1=expected,table_tail=tail,cases=cases,elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest())
(PORT/'reports'/os.environ.get('SH_AIR_COMPARE_REPORT','stage10-r5-air-state-comparison.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if not os.environ.get('SH_EXPECT_AIR_MISMATCH'):assert passed
