"""Offline MAP5 callbacks, items and save checksum fixtures."""
from pathlib import Path
import os
port = Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF'] = os.environ.get('SH_SEWER1_ELF', str(port / 'build/sewer1-compile-probe/sewer1-probe.elf'))
source = (port / 'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]',1)[0]
source = source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/sewer1-compile-probe'")
exec(source)

src=port/'tests/sewer1_probe.c'; obj=out/'sewer1_probe.o'; fixture=out/'sewer1-component.elf'
p=subprocess.run([prefix+'gcc',*shlex.split(flags),'-c',str(src),'-o',str(obj)],capture_output=True,text=True)
if p.returncode: raise RuntimeError(p.stderr)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),
                '-Wl,--undefined=sewer1_probe_save','-Wl,--undefined=sewer1_probe_hanged','-Wl,--undefined=sewer1_probe_creeper','-Wl,--undefined=sewer1_probe_flag_set','-Wl,--undefined=sewer1_probe_invalid_use','-Wl,--undefined=sewer1_probe_anim_reload','-Wl,--undefined=sewer1_probe_attack',str(obj),'-o',str(fixture)],check=True)
raw2=fixture.read_bytes();off2=struct.unpack_from('<I',raw2,28)[0];size2,count2=struct.unpack_from('<HH',raw2,42)
for line in subprocess.check_output([prefix+'nm','-n',str(fixture)],text=True).splitlines():
    p=line.split()
    if len(p)==3 and p[2].startswith('sewer1_'): game.symbols[p[2]]=int(p[0],16)
r=Chapter(); checks=[]
for i in range(count2):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw2,off2+i*size2)
    if typ==1 and length:r.uc.mem_write(addr,raw2[pos:pos+length])
callable_addresses=set()
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    p=line.split()
    if len(p)==3 and p[1] in ('T','t','W','w'): callable_addresses.add(int(p[0],16))
for name,index in [('map5_s00',29),('map5_s01',30)]:
    r.reset(name,index); assert r.call('alchemilla_probe_header')==0
    info=r.row(53); callbacks=struct.unpack('<'+'I'*info[0],r.uc.mem_read(game.symbols['alchemilla_probe_callbacks'],4*info[0]))
    assert all(p==0 or p in callable_addresses for p in callbacks)
    hdr=struct.unpack('<I',r.uc.mem_read(game.symbols['g_pMapOverlayHeader'],4))[0]
    fields=[4,12,16,60,64,68,72,96,100,104,108,112,116,120,128,132,140,144,152,156]
    fields.extend(range(0xa4,0x184,4)); fields.extend(range(0x194,0x248,4))
    for offset in fields:
        ptr=struct.unpack('<I',r.uc.mem_read(hdr+offset,4))[0]
        assert ptr==0 or ptr in callable_addresses,(name,hex(offset),hex(ptr))
    checks.append(dict(case='header_and_event_callbacks',map=name,events=info[0],status='PASS'))
for name in ('ScreenFade_Start','Screen_BackgroundImgDraw'):
    if name in game.symbols:r.bridge(name,lambda *_:r.ret())
for name in ('ScreenFade_IsFinished','Fs_QueueChunksLoad'):
    if name in game.symbols:r.bridge(name,lambda *_:r.ret(1))
for index,item,unlock in [(32,77,1371),(37,87,1391)]:
    r.reset('map5_s00',29)
    r.call('sewer1_probe_flag_set',355)  # The entry animation must already have completed.
    assert r.call('alchemilla_probe_use',index)==0,(index,r.row())
    assert r.call('alchemilla_probe_count',item)==1
    r.call('GameState_MapEvent_Update')
    assert r.call('alchemilla_probe_count',item)==0,(index,'consume')
    assert r.call('alchemilla_probe_flag',unlock)==1,(index,'unlock')
    checks.append(dict(case='inventory_use_and_consume',event=index,item=item,status='PASS'))
    r.reset('map5_s00',29)
    assert r.call('sewer1_probe_invalid_use',index,0)==0,(index,'wrong_location')
    checks.append(dict(case='wrong_location',event=index,status='PASS'))
r.reset('map5_s00',29)
r.call('alchemilla_probe_pickup',23,2); r.call('alchemilla_probe_pickup',23,3)
assert r.call('alchemilla_probe_flag',353)==1 and r.call('alchemilla_probe_count',77)==1
checks.append(dict(case='sewer_key_pickup',status='PASS'))
r.reset('map5_s00',29)
r.call('alchemilla_probe_pickup',23,2); r.call('alchemilla_probe_pickup',23,0xffffffff)
assert r.call('alchemilla_probe_flag',353)==0 and r.call('alchemilla_probe_count',77)==0
checks.append(dict(case='sewer_key_declined',status='PASS'))
r.reset('map5_s00',29)
r.call('alchemilla_probe_event',24,10)
assert r.call('alchemilla_probe_flag',354)==1 and r.call('alchemilla_probe_count',87)==1
checks.append(dict(case='sewer_exit_key_pickup',status='PASS'))
for event, flag in [(13,356),(17,357),(21,358),(19,359)]:
    r.reset('map5_s00',29)
    r.call('alchemilla_probe_event',event,6)
    assert r.call('alchemilla_probe_flag',flag)==1,(event,flag)
    checks.append(dict(case='ladder_completion',event=event,flag=flag,status='PASS'))
for phase in range(6):
    r.reset('map5_s00',29)
    assert r.call('sewer1_probe_save',phase)==0,phase
    checks.append(dict(case='save_checksum_roundtrip',phase=phase,status='PASS'))
for lethal in (0,1):
    r.reset('map5_s00',29)
    r.call('HangedScratcherAnimInfos_Init')
    r.call('sewer1_probe_hanged',lethal)
    row=struct.unpack('<4I',r.uc.mem_read(game.symbols['sewer1_enemy_out'],16))
    assert row[0]==350*4096 and row[1]==(0 if lethal else 250*4096) and row[3]==0,row
    checks.append(dict(case='hanged_damage',lethal=lethal,result=row,status='PASS'))
r.reset('map5_s00',29)
assert r.call('sewer1_probe_anim_reload')==0
checks.append(dict(case='enemy_animation_reload',status='PASS'))
r.reset('map5_s00',29)
r.call('sewer1_probe_creeper')
row=struct.unpack('<4I',r.uc.mem_read(game.symbols['sewer1_enemy_out'],16))
assert row==(20*4096,0,0,0),row
checks.append(dict(case='creeper_damage_and_death',result=row,status='PASS'))
for is_creeper in (0,1):
    r.reset('map5_s00',29); calls=[]
    r.bridge('func_8008A0E4',lambda *args: (calls.append('attack'),r.ret(0)))
    r.bridge('Collision_CharaCollisionSet',lambda *args: (calls.append('collision'),r.ret()))
    r.bridge('Los_NpcToPlayerHitCheck',lambda *args:r.ret(0))
    r.bridge('Sfx_WithFlagsPlay',lambda *args: (calls.append('sound'),r.ret()))
    r.call('sewer1_probe_attack',is_creeper)
    if is_creeper and struct.unpack('<i',r.uc.mem_read(game.symbols['sewer1_enemy_out'],4))[0] != 0:
        calls.append('collision')
    assert all(name in calls for name in ('attack','collision','sound')),(is_creeper,calls)
    checks.append(dict(case='enemy_attack_and_collision_dispatch',enemy='creeper' if is_creeper else 'hanged',calls=calls,status='PASS'))
assert not r.failure and not r.invalid,(r.failure,r.invalid)
record=dict(status='PASS',scope=__doc__,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),checks=checks)
(out/'sewer1-components.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
