#!/usr/bin/env python3
"""Execute actual ARM lower-screen HUD with no map and boundary health values."""
import os,shlex,struct,subprocess
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_C1_C0_2,UC_ARM_REG_FPEXC,UC_CPU_ARM_1176
p=Path(__file__).resolve().parents[1]; exe=p/'silenthill_game.elf'; b=p/'build/lower-hud-probe';obj=b.with_suffix('.o');probe=b.with_suffix('.elf')
tool=Path(os.environ['DEVKITARM'])/'bin';flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
subprocess.run([str(tool/'arm-none-eabi-gcc'),*flags,'-c',str(p/'tests/lower_hud_probe.c'),'-o',str(obj)],check=True)
subprocess.run([str(tool/'arm-none-eabi-gcc'),'-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(exe),str(obj),'-o',str(probe)],check=True)
def syms(path):
    out=subprocess.check_output([str(tool/'arm-none-eabi-nm'),'-n',str(path)],text=True)
    return {t[2]:int(t[0],16) for line in out.splitlines() if len(t:=line.split())==3 and t[0]!='w'}
s=syms(exe);s.update(syms(probe));u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
u.ctl_set_cpu_model(UC_CPU_ARM_1176);u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
for a,n in [(0x100000,0xf00000),(0x10000000,0x20000),(0x20000000,0x200000),(0x30000000,0x1000)]:u.mem_map(a,n)
def load(path):
    data=path.read_bytes();off=struct.unpack_from('<I',data,28)[0];sz,num=struct.unpack_from('<HH',data,42)
    for i in range(num):
        typ,pos,addr,_,n,_,_,_=struct.unpack_from('<8I',data,off+i*sz)
        if typ==1 and n:u.mem_write(addr,data[pos:pos+n])
load(exe);load(probe)
def ret(n=0):u.reg_write(UC_ARM_REG_R0,n&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def hook(name,fn):return u.hook_add(UC_HOOK_CODE,lambda *_:fn(),begin=s[name],end=s[name])
owner_hook=hook('Game3ds_CanPause',lambda:ret(1))
def fmt():
    dst=u.reg_read(UC_ARM_REG_R0);cap=u.reg_read(UC_ARM_REG_R1);a=u.reg_read(UC_ARM_REG_R3);sp=u.reg_read(UC_ARM_REG_SP)
    b=struct.unpack('<I',u.mem_read(sp,4))[0];txt=f'{a}/{b}'.encode();u.mem_write(dst,txt[:cap-1]+b'\0');ret(len(txt))
hook('snprintf',fmt)
def call(hp,gun,a,b):
    sp=0x1001ffc0;u.mem_write(sp,struct.pack('<I',0x20000000));u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x30000000)
    for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(hp,gun,a,b)):u.reg_write(reg,value)
    u.emu_start(s['lower_hud_probe'],0x30000000,count=200000000,timeout=30000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x30000000
    return struct.unpack('<6I',u.mem_read(0x20000000,24))
for hp,field in [(0,1),(40959,1),(40960,2),(204799,2),(204800,3)]:
    r=call(hp,0,0,0);assert r[0]==1 and r[field]==64 and r[4:]==(0,0),r
r=call(204800,1,12,37);assert r[0]==1 and r[3]==64 and r[4]>0 and r[5]==0,r
r2=call(204800,1,0,0);assert r2[4]!=r[4],(r,r2)
print('PASS: ARM no-map HUD, health boundaries, firearm current/reserve and melee')
# Load real original TIMs into emulated RAM at the asset boundary; all decoding,
# map selection, flags and Harry transforms execute in the linked ARM code.
u.mem_map(0x22000000,0x1000000);next_alloc=[0x22000000]
def alloc(n,clear=False):
    p=next_alloc[0];next_alloc[0]+=(n+15)&~15
    assert next_alloc[0]<0x23000000
    if clear:u.mem_write(p,bytes(n))
    return p
def malloc_hook():ret(alloc(u.reg_read(UC_ARM_REG_R0)))
def calloc_hook():ret(alloc(u.reg_read(UC_ARM_REG_R0)*u.reg_read(UC_ARM_REG_R1),True))
for name in ('malloc','__wrap_malloc'):
    if name in s:hook(name,malloc_hook)
for name in ('calloc','__wrap_calloc'):
    if name in s:hook(name,calloc_hook)
for name in ('free','__wrap_free'):
    if name in s:hook(name,lambda:ret())
if 'Fs_QueueGetLength' in s:hook('Fs_QueueGetLength',lambda:ret(0))
def memcpy_hook():
    dst=u.reg_read(UC_ARM_REG_R0);src=u.reg_read(UC_ARM_REG_R1);n=u.reg_read(UC_ARM_REG_R2)
    if n:u.mem_write(dst,bytes(u.mem_read(src,n)))
    ret(dst)
def memset_hook():
    dst=u.reg_read(UC_ARM_REG_R0);v=u.reg_read(UC_ARM_REG_R1)&255;n=u.reg_read(UC_ARM_REG_R2)
    if n:u.mem_write(dst,bytes([v])*n)
    ret(dst)
if 'memcpy' in s:hook('memcpy',memcpy_hook)
if 'memset' in s:hook('memset',memset_hook)
disc=p.parent.parent/'silent-hill-decomp/sh1_data/sh1.bin';resources={}
def disc_read(f,lba,off,n):
    b=bytearray()
    while n:
        part=min(n,2048-off%2048);f.seek((lba+off//2048)*2352+24+off%2048)
        chunk=f.read(part);assert len(chunk)==part;b+=chunk;off+=part;n-=part
    return bytes(b)
def asset():
    fileid=u.reg_read(UC_ARM_REG_R0);out=u.reg_read(UC_ARM_REG_R1);sz=u.reg_read(UC_ARM_REG_R2)
    with disc.open('rb') as f:
        word=struct.unpack('<I',disc_read(f,24,47388+12*fileid,4))[0]
        lba,size=word&0x7ffff,((word>>19)&0xfff)*256;raw=disc_read(f,lba,0,size)
    resources[fileid]=raw
    ptr=alloc(size);u.mem_write(ptr,raw);u.mem_write(out,struct.pack('<I',ptr));u.mem_write(sz,struct.pack('<I',size));ret()
hook('stage4_fs_presentation_read',asset)
def invoke(name,*args):
    sp=0x1001ffc0;u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x30000000)
    for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
    u.emu_start(s[name],0x30000000,count=200000000,timeout=30000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x30000000,(name,hex(u.reg_read(UC_ARM_REG_PC)))
    return u.reg_read(UC_ARM_REG_R0)
invoke('lower_map_setup',1);frame=invoke('lower_map_pixels')
for _ in range(61):invoke('Game3ds_LowerDraw',frame)
a=bytes(u.mem_read(frame,320*240*2));assert sum(v!=0 for v in a)>10000
raw=resources[1896];image=8+struct.unpack_from('<I',raw,8)[0]+12
for y in range(12,230,17):
    for x in range(5,300,23):
        if 166<=x<=192 and 108<=y<=135:continue
        packed=struct.unpack_from('<H',raw,image+2*((2*y)*160+x//2))[0]
        index=(packed>>(8*(x%2)))&255;word=struct.unpack_from('<H',raw,20+2*index)[0]
        r,g,b=word&31,(word>>5)&31,(word>>10)&31
        expected=(r<<11)|(((g<<1)|(g>>4))<<5)|b
        actual=struct.unpack_from('<H',a,2*(x*240+239-y))[0]
        assert actual==expected,(x,y,actual,expected)
assert invoke('lower_original_marker_probe')>0,'original interactive marker did not emit primitives'
invoke('lower_map_move',4*4096,0,1024);invoke('Game3ds_LowerDraw',frame)
b=bytes(u.mem_read(frame,320*240*2));assert a!=b,'Harry marker did not move/turn'
invoke('lower_map_mark');invoke('Game3ds_LowerDraw',frame)
marked=bytes(u.mem_read(frame,320*240*2));assert marked!=b,'original event flag did not update marking'
invoke('lower_map_area',2,0);invoke('Game3ds_LowerDraw',frame)
c=bytes(u.mem_read(frame,320*240*2));assert sum(v!=0 for v in c)<500,'map shown when not owned'
invoke('lower_map_area',2,1)
for _ in range(61):invoke('Game3ds_LowerDraw',frame)
d=bytes(u.mem_read(frame,320*240*2));assert sum(v!=0 for v in d)>10000 and d!=a,'area map not changed'
invoke('lower_map_area',6,1)
for _ in range(61):invoke('Game3ds_LowerDraw',frame)
floor1=bytes(u.mem_read(frame,320*240*2));assert sum(v!=0 for v in floor1)>10000
invoke('lower_map_area',7,1)
for _ in range(61):invoke('Game3ds_LowerDraw',frame)
floor2=bytes(u.mem_read(frame,320*240*2));assert sum(v!=0 for v in floor2)>10000 and floor2!=floor1,'floor map not changed'
print('PASS: ARM original TIM map owned/not owned, live position, event marking, area and floor change')
# Markers, health and ammo receive the same presentation factor.
invoke('lower_map_setup',1)
invoke('lower_test_firearm')
u.mem_write(s['game_text_style'],struct.pack('<I',0))
for _ in range(3):invoke('Game3ds_LowerDraw',frame)
for brightness in range(2,11):
    u.mem_write(s['game_lower_brightness'],struct.pack('<I',brightness))
    invoke('Game3ds_LowerDraw',frame)
    pixels=struct.unpack('<76800H',u.mem_read(frame,320*240*2))
    assert (31*brightness//10)<<11 in pixels,brightness
    assert pixels[269*240+239-4]==((63*brightness//10)<<5),(brightness,'health')
    white=((31*brightness//10)<<11)|((63*brightness//10)<<5)|(31*brightness//10)
    assert pixels[282*240+239-3]==white,(brightness,'ammo')
u.mem_write(s['game_lower_brightness'],struct.pack('<I',10))
print('PASS: ARM map cursor, health and ammo brightness 20-100%')
invoke('lower_map_setup',0);invoke('Game3ds_LowerDraw',frame)
before=bytes(u.mem_read(frame,320*240*2))
u.mem_write(0x20010000,b'FPS 30.0\0')
invoke('Game3ds_LowerCounter',frame,0x20010000)
after=bytes(u.mem_read(frame,320*240*2))
assert before!=after
assert struct.unpack_from('<H',after,2*(4*240+239-4))[0]==0xffff
assert after[2*(250*240):]==before[2*(250*240):], 'counter crossed to HUD side'
invoke('Game3ds_LowerDraw',frame);u.mem_write(0x20010000,b'\0')
invoke('Game3ds_LowerCounter',frame,0x20010000)
assert bytes(u.mem_read(frame,320*240*2))==before,'disabled counter changed framebuffer'
print('PASS: ARM counter appears at lower-screen top left and off leaves frame unchanged')
u.hook_del(owner_hook)
assert invoke('lower_owner_probe',11,0,0)==1
for state,sys,cut in [(14,0,0),(15,0,0),(19,0,0),(20,0,0),(9,0,0),(16,0,0),(11,3,0),(11,2,0),(11,0,1)]:
    assert invoke('lower_owner_probe',state,sys,cut)==0,(state,sys,cut)
print('PASS: ARM gameplay vs map/status/loading/movie/save/cutscene ownership gate')
display_hook=hook('game3ds_gpu_display',lambda:ret(0))
assert invoke('lower_pause_probe',11,0,0,0)==1
for state,sys,cut,border in [(11,0,1,0),(11,0,0,1),(11,10,0,0),(11,7,0,0),(12,0,0,0),(11,4,0,0),(15,0,0,0)]:
    assert invoke('lower_pause_probe',state,sys,cut,border)==0,(state,sys,cut,border)
u.hook_del(display_hook)
print('PASS: ARM START reaches cutscenes, map events and original menus; gameplay opens pause')
hook('Gfx_MapMsg_Draw',lambda:ret(0))
assert invoke('lower_select_probe',0)==11,'SELECT without map left gameplay'
assert invoke('lower_select_probe',1)==15,'SELECT with map did not enter original map state'
print('PASS: ARM original SELECT state dispatch with and without map')
