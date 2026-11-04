#!/usr/bin/env python3
"""Execute default USA control setup; inspect actual supported-state table."""
import contextlib,io,json,os,shlex,struct,subprocess
with contextlib.redirect_stdout(io.StringIO()):
    import test_game_gpu_arm as gpu
p=gpu.port;prefix=str(__import__('pathlib').Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/menu_mapping_probe.o';elf=p/'build/menu_mapping_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/menu_mapping_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(gpu.elf_path),str(obj),'-o',str(elf)],check=True)
probe=elf.read_bytes();m=gpu.Machine();off=struct.unpack_from('<I',probe,28)[0];size,count=struct.unpack_from('<HH',probe,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',probe,off+i*size)
    if typ==1 and length:m.uc.mem_write(addr,probe[pos:pos+length])
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
gpu.symbols['test_menu_mapping']=next(int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3 and s[2]=='test_menu_mapping')
bits=m.call('test_menu_mapping');assert bits==7,bits
table=struct.unpack('<15I',m.uc.mem_read(gpu.symbols['g_SysStateFuncs'],60))
assert table[2]==gpu.symbols['SysState_StatusMenu_Update'] and table[3]==gpu.symbols['SysState_MapScreen_Update']
print(json.dumps({'execution':'actual linked ARM default USA control setup and state table',
    'triangle':'StatusMenu, state 2, original preset 2',
    'select':'MapScreen, state 3, original preset 2',
    'status_callback_bound':True,'passed':True},indent=2))
