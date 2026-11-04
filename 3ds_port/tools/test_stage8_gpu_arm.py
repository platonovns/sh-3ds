"""Frame ownership, full clear extents and inverse feedback mapping on ARM."""
import json,os,shlex,struct,subprocess
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'stage8_gpu_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
Machine=ns['Machine'];symbols=ns['symbols'];p=ns['port'];prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage8_gpu_probe.o';elf=p/'build/stage8_gpu_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage8_gpu_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2]=='stage8_route':symbols[s[2]]=int(s[0],16)
m=Machine()
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
routes=[]
for state,next,h,want in [(11,19,224,(400,240,0)),(19,14,448,(320,448,2)),(14,11,448,(320,240,1)),(11,11,224,(400,240,0))]*5:
    m.draws=[];value=m.call('stage8_route',state,next,h)
    got=(value&1023,(value>>10)&1023,value>>20);assert got==want,(got,want)
    v=m.draws[-1]['vertices'];xs=v[0::9];ys=v[1::9]
    assert min(xs)==0 and max(xs)==want[0] and min(ys)==0 and max(ys)==want[1],(xs,ys)
    routes.append(dict(update=state,next=next,surface=got))
# A completed native 400x240 image resolves all of its sides, not the centre
# 320-column crop. GPU sampling is tested separately in the PICA probe.
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_R0
resolves=[]
def resolve(x,y,w,h):
    ow,oh,out,stride=struct.unpack('<4I',m.uc.mem_read(m.uc.reg_read(UC_ARM_REG_SP),16))
    resolves.append((x,y,w,h,ow,oh))
    for row in range(oh):m.uc.mem_write(out+row*stride*2,struct.pack('<'+'H'*ow,*[i%32 for i in range(ow)]))
    m.uc.reg_write(UC_ARM_REG_R0,1);m.ret()
m.hook('game3ds_gpu_resolve',resolve)
m.word('game3ds_canonical',symbols['vram']);m.call('game3ds_gpu_frame_complete')
m.call('Game3ds_FramebufferCapture');m.call('Game3ds_FramebufferCapture')
assert resolves==[(0,0,400,240,320,224)],resolves
report=dict(status='PASS',execution='linked ARM with SDK recorder, no hardware claim',
    repeated_routes=len(routes),latched_world_to_status=routes[0],status_loading_hidden=routes[1],
    complete_native_feedback_source=resolves,one_resolve_per_completed_surface=True,full_view_clear=True)
(p/'reports/stage8-gpu-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
