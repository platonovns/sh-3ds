"""Native packet arena: former hardware high-water, final valid packet, guards and wrong buffer."""
import hashlib,json,os,shlex,struct,subprocess
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'packet_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
p=ns['port'];symbols=ns['symbols'];prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0]);obj=p/'build/stage10_packet_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_packet_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2]=='stage10_packet_test':symbols[s[2]]=int(s[0],16)
cases=[]
for which in range(6):
    m=ns['Machine']()
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
    failed=which in (1,2,5)
    value=m.call('stage10_packet_test',which,expected_failure=460 if failed else None)
    if not failed:assert value==(131400 if which==3 else 262144),(which,value)
    cases.append(dict(case=which,failure=m.failure,result=None if failed else value))
report=dict(status='PASS',scope=__doc__,cases=cases,elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_accepted=False)
(p/'reports/stage10-packet-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
