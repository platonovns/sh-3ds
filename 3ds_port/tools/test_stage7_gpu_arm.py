#!/usr/bin/env python3
"""ARM display routing, PSX line samples, transfer bounds and overlap copies."""
import json,os,shlex,struct,subprocess
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py');ns={'__file__':str(fixture),'__name__':'stage7_gpu_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
Machine=ns['Machine'];symbols=ns['symbols'];p=ns['port'];elf=ns['elf_path']
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-');flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage7_gpu_probe.o';probe=p/'build/stage7_gpu_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage7_gpu_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(elf),str(obj),'-o',str(probe)],check=True)
raw=probe.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
nm=subprocess.check_output([prefix+'nm','-n',str(probe)],text=True)
symbols['stage7_route_probe']=next(int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3 and s[2]=='stage7_route_probe')
m=Machine();ram=symbols['g_PsxRam'];packet=ram+0x100;rect=ram+0x400;out=ram+0x1000
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
routes=[]
for state,h,want in [(11,224,(400,240,0)),(11,448,(320,448,0)),(7,448,(320,448,0)),(19,224,(320,240,2)),(14,448,(320,240,1))]:
    result=m.call('stage7_route_probe',state,h);got=(result&1023,(result>>10)&1023,result>>20)
    assert got==want,(state,got,want);routes.append({'state':state,'native_surface':got,'physical_display':(320 if got[2] else 400,240)})
# Decimal counts use the actual ARM formatter, before any glyph rasterization.
m=Machine();digits=[]
def record_digits(ptr,*_):
    raw=bytes(m.uc.mem_read(ptr,32));digits.append(raw.split(b'\0')[0].decode('ascii'));m.ret()
m.hook('Gfx_StringDraw',record_digits)
values=[0,1,9,10,15,99,100,165,9999,-15]
for value in values:m.call('Gfx_StringDrawInt',3,value&0xffffffff)
assert digits==[str(v) for v in values],digits
# Independent line fixture starts with zero screen offset, as raw GP0 decoding.
m=Machine();ram=symbols['g_PsxRam'];packet=ram+0x100
lines=[]
for gouraud in (0,1):
    for label,start,end,n in [('horizontal',(2,3),(7,3),1),('vertical',(2,3),(2,7),1),('diagonal',(2,3),(6,7),5),('reversed',(6,7),(2,3),5)]:
        code=0x50 if gouraud else 0x40;xy=lambda pt:(pt[0]&65535)|((pt[1]&65535)<<16)
        words=[(code<<24)|0x102030,xy(start)]+([0x405060] if gouraud else [])+[xy(end)]
        m.uc.mem_write(packet,struct.pack('<IHH'+'I'*len(words),symbols['prim_terminator'],len(words),0,*words));m.draws=[];m.call('DrawPrim',packet)
        assert len(m.draws)==n,(label,m.draws)
        assert all(d['count']==6 and not d['textured'] for d in m.draws)
        lines.append({'case':label,'gouraud':bool(gouraud),'rectangles':n})
# Original save UI scroll thumbs have two layers; both must use native OT tags.
save_ui=[]
for slot,count,selected in [(0,1,0),(1,5,4),(0,11,7),(1,165,164)]:
    m=Machine();arena=symbols['g_PsxRam']+0x1a2600;ot=symbols['g_OrderingTable2']
    m.word('g_ActiveBufferIdx',0);m.word('GsOUT_PACKET_P',arena)
    m.call('GsInitGraph2',320,224,0,0,0);m.call('GsClearOt',0,0,ot)
    m.call('SaveScreen_NavigationDraw',slot,count,selected,0)
    m.call('GsDrawOt',ot)
    assert len(m.draws)>=4 and m.get_word('GsOUT_PACKET_P')-arena<32768
    save_ui.append({'slot':slot,'save_count':count,'selected':selected,'draws':len(m.draws)})
# Actual canonical VRAM transfers; no rendered frame is claimed by this fixture.
m=Machine();ram=symbols['g_PsxRam'];rect=ram+0x400;out=ram+0x1000;vram=symbols['vram'];m.word('game3ds_canonical',vram)
samples=[i+1 for i in range(12)]
for y in range(3):m.uc.mem_write(vram+((30+y)*1024+20)*2,struct.pack('<4H',*samples[y*4:y*4+4]))
m.uc.mem_write(rect,struct.pack('<4h',20,30,4,3));m.call('StoreImage',rect,out)
assert list(struct.unpack('<12H',m.uc.mem_read(out,24)))==samples
m.call('MoveImage',rect,21,31)
for y in range(3):assert list(struct.unpack('<4H',m.uc.mem_read(vram+((31+y)*1024+21)*2,8)))==samples[y*4:y*4+4]
m.uc.mem_write(rect,struct.pack('<4h',1023,511,2,2));m.call('StoreImage',rect,out,expected_failure=443)
report={'status':'PASS','execution':'linked ARM, SDK submission recorder; GPU readback pixels require Azahar probe','routes':routes,'decimal_counts':digits,'lines':lines,'original_save_ui':save_ui,'StoreImage_words':12,'overlapping_MoveImage':True,'invalid_transfer_rejected':True}
(p/'reports/stage7-gpu-extensions-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
