"""Native header and event dispatch checks for Block 5."""
from pathlib import Path
import os
port=Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF']=str(port/'build/resort-probe/resort-probe.elf')
source=(port/'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]',1)[0]
source=source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/resort-probe'")
exec(source)
r=Chapter()
callable_addresses=set()
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    p=line.split()
    if len(p)==3 and p[1] in ('T','t','W','w'):callable_addresses.add(int(p[0],16))
for name,index in [('map5_s02',31),('map5_s03',32),('map6_s00',33),('map6_s01',34)]:
    r.reset(name,index);assert r.call('alchemilla_probe_header')==0
    info=r.row(53);callbacks=struct.unpack('<'+'I'*info[0],r.uc.mem_read(game.symbols['alchemilla_probe_callbacks'],4*info[0]))
    assert all(p==0 or p in callable_addresses for p in callbacks),(name,'events')
    hdr=struct.unpack('<I',r.uc.mem_read(game.symbols['g_pMapOverlayHeader'],4))[0]
    fields=[4,12,16,60,64,68,72,96,100,104,108,112,116,120,128,132,140,144,152,156]
    fields.extend(range(0xa4,0x184,4));fields.extend(range(0x194,0x248,4))
    for off in fields:
        ptr=struct.unpack('<I',r.uc.mem_read(hdr+off,4))[0]
        assert ptr==0 or ptr in callable_addresses,(name,hex(off),hex(ptr))
    print(name, 'header and event callbacks',info[0],flush=True)
