#!/usr/bin/env python3
"""Original ARM save UI/state machine + same host C SD-card image backend.
Fresh ARM instances model restart. This is a component test, not the Cafe route.
"""
import ctypes as ct,json,os,shlex,struct,subprocess,tempfile
from pathlib import Path
import run_arm_game as game
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage7_save_probe.o';elf=p/'build/stage7_save_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage7_save_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
data=elf.read_bytes();off=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
for line in nm.splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage7_save_'):game.symbols[s[2]]=int(s[0],16)
with tempfile.TemporaryDirectory(prefix='sh-save-') as directory:
    root=Path(directory);lib=root/'card.so';card=root/'memcard.mcr'
    subprocess.run(['cc','-shared','-fPIC','-O1','-g','-I'+str(p/'include'),str(p/'source/game_card_image.c'),'-o',str(lib)],check=True)
    core=ct.CDLL(str(lib))
    class SaveRunner(game.GameRunner):
        def __init__(self):
            super().__init__()
            for i in range(count):
                typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',data,off+i*size)
                if typ==1 and length:self.uc.mem_write(addr,data[pos:pos+length])
            self.call('PsxMemory_Init')
            self.bridge('game_card_mount',lambda *_:self.ret(core.game_card_mount(str(card).encode())))
            self.bridge('game_card_ready',lambda *_:self.ret(core.game_card_ready()))
            self.bridge('game_card_find',lambda name,*_:self.ret(core.game_card_find(self.string(name))))
            self.bridge('game_card_create',lambda name,n,*_:self.ret(core.game_card_create(self.string(name),n)))
            self.bridge('game_card_entry',self.entry)
            self.bridge('game_card_read',self.read)
            self.bridge('game_card_write',self.write)
            self.bridge('game_card_erase',lambda name,*_:self.ret(core.game_card_erase(self.string(name))))
            self.bridge('game_card_format',lambda *_:self.ret(core.game_card_format()))
        def string(self,ptr):return bytes(self.uc.mem_read(ptr,64)).split(b'\0')[0]
        def entry(self,block,name,size,*_):
            buf=ct.create_string_buffer(21);n=ct.c_uint();ok=core.game_card_entry(block,buf,ct.byref(n))
            if ok:
                if name:self.uc.mem_write(name,buf.raw)
                if size:self.uc.mem_write(size,struct.pack('<I',n.value))
            self.ret(ok)
        def read(self,block,offset,dest,n):
            buf=ct.create_string_buffer(n);ok=core.game_card_read(block,offset,buf,n)
            if ok:self.uc.mem_write(dest,buf.raw)
            self.ret(ok)
        def write(self,block,offset,src,n):self.ret(core.game_card_write(block,offset,ct.create_string_buffer(bytes(self.uc.mem_read(src,n))),n))
    first=SaveRunner();created=first.call('stage7_save_create');assert created==0,(created,first.failure)
    raw=card.read_bytes();assert len(raw)==131072
    core.game_card_unmount()
    second=SaveRunner();loaded=second.call('stage7_save_load');assert loaded==0,(loaded,second.failure)
    core.game_card_unmount()
    report={'status':'PASS','execution':'original ARM SaveScreen_SaveGame and MemCard state machines; host transport uses production C card-image module','new_ARM_instance_loads_persisted_save':True,'card_bytes':len(raw),'game_serialization':'original SH checksums, metadata, options and save record','visual_or_hardware_acceptance':False}
    (p/'reports/stage7-save-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
