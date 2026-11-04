"""Real native pad facade: C-stick camera only, no Harry movement, original locks.
Analog camera response and ownership; actual locomotion is tested separately.
"""
import hashlib,json,math,os,shlex,struct,subprocess
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'modern_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
p=ns['port'];symbols=ns['symbols'];prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0]);obj=p/'build/stage10_modern_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_modern_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage10_'):symbols[s[2]]=int(s[0],16)
cases=[]
for blocked in range(5):
    m=ns['Machine']()
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
    m.hook('Game3ds_Observe',lambda *_:m.ret())
    m.hook('game3ds_read_pad',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,1<<24),m.ret()))
    def camera(ptr,*_):m.uc.mem_write(ptr,struct.pack('<4h',0,1024,0,0));m.ret()
    m.hook('vwGetViewAngle',camera)
    m.call('stage10_modern_setup',blocked);m.call('Game3ds_PadPoll');m.call('stage10_analog',156,0);v=m.call('stage10_modern_result')
    assert (v&65535)==123 and (v>>16)==0,(blocked,hex(v))
    camera_result=m.call('stage10_camera_result')
    assert not (camera_result&(1<<31)),'Camera translation must remain original'
    assert bool(camera_result&65535)==(blocked==0),(blocked,hex(camera_result))
    cases.append(dict(blocked=blocked,heading=v&65535,psx_buttons=v>>16,camera_right=camera_result&65535))
report=dict(status='PASS',scope=__doc__,cases=cases,elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_accepted=False)
for keys,expected,vertical in [(1<<24,1,False),(1<<25,-1,False),(1<<26,-1,True),(1<<27,1,True)]:
    m=ns['Machine']()
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
    m.hook('Game3ds_Observe',lambda *_:m.ret())
    m.hook('game3ds_read_pad',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,keys),m.ret()))
    m.call('stage10_modern_setup',0);m.call('Game3ds_PadPoll');m.call('stage10_analog',156 if keys==(1<<24) else (-156 if keys==(1<<25) else 0),156 if keys==(1<<26) else (-156 if keys==(1<<27) else 0))
    v=m.call('stage10_modern_result');assert v==123,(keys,v)
    component=m.call('stage10_camera_pitch' if vertical else 'stage10_camera_result')&65535
    component=component-65536 if component&32768 else component
    assert component*expected>0,(keys,component,expected)
    cases.append(dict(keys=keys,axis='pitch' if vertical else 'yaw',matrix_forward_component=component,harry_yaw=123))
response=[]
for rate in (30,60):
    for magnitude in (0,23,60,156):
        m=ns['Machine']()
        for i in range(count):
            typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
            if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
        clock=[0]
        m.hook('game3ds_q12_clock',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,clock[0]),m.ret()))
        m.call('stage10_modern_setup',0);m.call('stage10_analog',magnitude,0)
        values=[]
        for frame in range(rate*2):
            clock[0]=round(frame*4096/rate)
            value=m.call('stage10_camera_result')&65535;assert value<32768
            values.append(value)
        assert values==sorted(values) and max(values)<=1401,(rate,magnitude,values)
        if magnitude<=23:assert not any(values)
        else:assert 0<values[0]<values[-1]
        angles=[math.degrees(math.asin(v/4096)) for v in values]
        assert all(angles[i]-angles[i-1]<150/rate+.2 for i in range(1,len(angles)))
        m.call('stage10_analog',0,0);released=[]
        for frame in range(rate*2,rate*4):
            clock[0]=round(frame*4096/rate);released.append(m.call('stage10_camera_result')&65535)
        assert released==sorted(released,reverse=True) and released[-1]==0
        response.append(dict(rate=rate,analog=magnitude,first_samples=values[:6],settled=values[-1],released=released[-1]))
for magnitude in (60,156):
    pair=[r['settled'] for r in response if r['analog']==magnitude];assert abs(pair[0]-pair[1])<4
assert response[2]['settled']<response[3]['settled']/2
report['analog_response']=response
(p/'reports/stage10-modern-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
