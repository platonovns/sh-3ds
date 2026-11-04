#!/usr/bin/env python3
"""Local Azahar RSP debugger: resume boot, capture a stalled death, no game writes."""
import argparse,json,socket,struct,time
from pathlib import Path

class Rsp:
    def __init__(self,port):
        deadline=time.monotonic()+30
        while True:
            try:self.socket=socket.create_connection(('127.0.0.1',port),timeout=2);break
            except (ConnectionRefusedError,TimeoutError):
                if time.monotonic()>=deadline:raise
                time.sleep(0.25)
        self.socket.settimeout(10)
    def packet(self):
        while True:
            b=self.socket.recv(1)
            if not b:raise ConnectionError('Azahar debugger disconnected')
            if b==b'$':break
        data=bytearray()
        while (b:=self.socket.recv(1))!=b'#':
            if not b:raise ConnectionError('Azahar debugger disconnected')
            data.extend(b)
        checksum=self.socket.recv(2)
        assert int(checksum,16)==sum(data)%256,(data,checksum)
        self.socket.sendall(b'+')
        return data.decode('ascii')
    def send(self,command):
        data=command.encode('ascii')
        self.socket.sendall(b'$'+data+b'#'+f'{sum(data)%256:02x}'.encode())
    def command(self,command):
        self.send(command);return self.packet()
    def memory(self,address,length):
        out=bytearray()
        for offset in range(0,length,512):
            response=self.command(f'm{address+offset:x},{min(512,length-offset):x}')
            if response.startswith('E'):raise RuntimeError(response)
            out.extend(bytes.fromhex(response))
        return bytes(out)

def symbols(elf):
    b=elf.read_bytes();off=struct.unpack_from('<I',b,32)[0];size,count=struct.unpack_from('<HH',b,46)
    headers=[struct.unpack_from('<10I',b,off+i*size) for i in range(count)]
    out={}
    for h in headers:
        if h[1]!=2:continue
        strings=headers[h[6]];names=b[strings[4]:strings[4]+strings[5]]
        for pos in range(h[4],h[4]+h[5],h[9]):
            name,value,length,info,other,index=struct.unpack_from('<IIIBBH',b,pos)
            text=names[name:].split(b'\0',1)[0].decode()
            if text and index:out[text]=(value,length)
    return out

p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=24689)
p.add_argument('--timeout',type=int,default=1800);p.add_argument('--capture-now',action='store_true');a=p.parse_args()
port=Path(__file__).resolve().parents[1];repo=port.parent
info=json.loads((port/'build/azahar/last-run.json').read_text(encoding='utf-8-sig'))
assert info.get('gdb_stub') or a.capture_now,'Launch with -GdbStub or enable it live for --capture-now'
run=Path(info['launched']).parent;names=symbols(port/'silenthill_game.elf')
r=Rsp(a.port);initial=r.command('?')
if not a.capture_now:r.send('c')
print(json.dumps({'debugger':'CONNECTED_RESUMED','initial_stop':initial,'run':str(run)}),flush=True)
started=time.monotonic();previous=None;last_fresh=started;status={}
while time.monotonic()-started<a.timeout:
    time.sleep(1)
    try:
        text=(repo/'sh1_data/stage4_status.txt').read_text()
        s=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
        if s.get('build')!=info['build_identity'] or s.get('report_complete')!='1':continue
        status=s;frame=s.get('map_frames')
        if frame!=previous:previous=frame;last_fresh=time.monotonic()
        if a.capture_now or (int(s.get('player_health','1'))<=0 and s.get('anim_state')=='8' and time.monotonic()-last_fresh>8):break
    except (OSError,ValueError):continue
else:raise TimeoutError('No stalled death observed')
if a.capture_now:
    stop=initial
else:
    r.socket.sendall(b'\x03');stop=r.packet()
raw=r.command('g')
registers=list(struct.unpack('<16I',bytes.fromhex(raw[:128])))
report={'status':'STALLED_DEATH_DEBUG_CAPTURE','stop':stop,'registers_raw':raw,
        'registers':{f'r{i}' if i<13 else ('sp','lr','pc')[i-13]:hex(x) for i,x in enumerate(registers)},
        'runtime':status,'build':info['build_identity'],'sha256':info['build_sha256']}
for label,address in (('pc',registers[15]),('lr',registers[14])):
    candidates=[(value,name) for name,(value,length) in names.items() if value<=address and value>0]
    if candidates:
        base,name=max(candidates);report[label+'_nearest']={'symbol':name,'offset':hex(address-base)}
try:
    stack=r.memory(registers[13],4096-(registers[13]&4095));(run/'stage6-hang-stack.bin').write_bytes(stack)
    report['stack_words']=[hex(x) for x in struct.unpack('<'+'I'*(len(stack)//4),stack)]
except Exception as error:report['stack_error']=repr(error)
report['regions']={}
for label,address,length in [('syswork',*names['g_SysWork']),
                            ('particle_vectors',names['g_PsxRam'][0]+0xE0C4C,128)]:
    try:
        data=r.memory(address,length);filename='stage6-hang-'+label+'.bin'
        (run/filename).write_bytes(data);report['regions'][label]={'address':address,'bytes':length,'file':filename}
    except Exception as error:report['regions'][label]={'error':repr(error)}
(run/'stage6-gdb-hang.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('runtime','stack_words','registers_raw')},indent=2),flush=True)
# Leave the emulated CPU stopped with its evidence intact; do not step or write
# game registers, data, event flags, inventory or player position.
