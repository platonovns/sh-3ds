"""Original flashlight occlusion, native seed layout, intensity ramp and flare packets.

Only the SDK readback pixel and camera-mode boundary are fixtures; the original
occlusion query, smoothing, halo/ray producers and OT validation execute on ARM.
PICA school rendering is qualified separately.
"""
import hashlib,json,os,shlex,struct,subprocess
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'lens_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
p=ns['port'];symbols=ns['symbols'];prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0]);obj=p/'build/stage10_lens_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_lens_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage10_lens_'):symbols[s[2]]=int(s[0],16)
cases=[]
for buffer in (0,1):
    m=ns['Machine']()
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
    move,tile,poly,fade_offset,flag_offset=[m.call('stage10_lens_layout',i) for i in range(5)]
    assert (move,tile)==(28,20)
    for on_screen in (0,1):
        m.call('stage10_lens_setup',buffer);base=m.get_word('GsOUT_PACKET_P')
        assert m.call('stage10_lens_seed',on_screen)==move+tile
        packet=bytes(m.uc.mem_read(base,move+tile))
        assert struct.unpack_from('<H',packet,4)[0]==5
        assert struct.unpack_from('<I',packet,12)[0]==0x80000000
        assert struct.unpack_from('<I',packet,move-4)[0]==(8<<16|8),'Move width overlaps native TILE tag'
        if on_screen:
            assert struct.unpack_from('<H',packet,move+4)[0]==3
            assert packet[move+11]==0x60
    m.call('stage10_lens_setup',buffer)
    pixel=[0xffff];reads=[];mode=[1]
    def readback(rect,dst,*_):
        reads.append(struct.unpack('<4h',m.uc.mem_read(rect,8)))
        m.uc.mem_write(dst,struct.pack('<I',pixel[0]));m.uc.reg_write(UC_ARM_REG_R0,0);m.ret()
    m.hook('StoreImage2',readback)
    m.hook('vcRetCamMvSmoothF',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,mode[0]),m.ret()))
    assert m.call('func_8008D850')==1
    assert reads[-1]==(792 if buffer==0 else 784,112,2,1)
    for value in (0,0x7ffe,0x8000):
        pixel[0]=value;assert m.call('func_8008D850')==0
    pixel[0]=0xffff
    used=m.call('stage10_lens_draw');intensity=struct.unpack('<h',m.uc.mem_read(symbols['D_800C4818']+fade_offset,2))[0]
    assert used==22*poly and intensity==2048,(used,poly,intensity)
    assert m.uc.mem_read(symbols['D_800C4818']+flag_offset,1)==b'\0'
    pixel[0]=0;assert m.call('stage10_lens_draw')==22*poly
    assert struct.unpack('<h',m.uc.mem_read(symbols['D_800C4818']+fade_offset,2))[0]==1024
    mode[0]=0;assert m.call('stage10_lens_draw')==3*poly
    assert m.uc.mem_read(symbols['D_800C4818']+fade_offset,2)==b'\0\0'
    cases.append(dict(buffer=buffer,seed_bytes=move+tile,readback_rect=reads[-1],flare_primitives=22,chase_primitives=3,ramp=[2048,1024,0]))
report=dict(status='PASS',scope=__doc__,cases=cases,elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_accepted=False)
(p/'reports/stage10-lens-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
