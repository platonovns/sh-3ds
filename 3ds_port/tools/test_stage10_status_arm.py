"""Original Status glyph producer rasters directly at 320x240, without final scaling."""
import hashlib,json,os,shlex,struct,subprocess
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'status_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
p=ns['port'];symbols=ns['symbols'];prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
obj=p/'build/stage10_status_probe.o';elf=obj.with_suffix('.elf')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_status_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2]=='stage10_status_text':symbols[s[2]]=int(s[0],16)
m=ns['Machine']()
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
cases=[]
for high_res in (0,1):
    m.draws.clear();m.call('stage10_status_text',high_res,0)
    assert len(m.draws)==7,m.draws
    for d in m.draws:
        v=d['vertices'];xs=v[0::9];ys=v[1::9]
        assert max(xs)-min(xs)==12 and max(ys)-min(ys)==(15 if high_res else 12),(xs,ys)
        assert all(abs(y*2-round(y*2))<1e-6 for y in ys)
    cases.append(dict(original_high_res_flag=high_res,glyph_lcd_pixels=[12,15 if high_res else 12]))
m.draws.clear();m.call('stage10_status_text',0,1)
assert len(m.draws)==21
tops=sorted(min(m.draws[i]['vertices'][1::9]) for i in (0,7,14))
assert tops[1]-tops[0]==12 and tops[2]-tops[1]==12,tops
w=symbols['g_PsxRam']+0x100;m.call('game3ds_gpu_extent',w,w+4)
assert struct.unpack('<2I',m.uc.mem_read(w,8))==(320,240)
report=dict(status='PASS',glyphs=7,cases=cases,native_surface=[320,240],
    final_rescale=False,elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_accepted=False)
(p/'reports/stage10-status-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
