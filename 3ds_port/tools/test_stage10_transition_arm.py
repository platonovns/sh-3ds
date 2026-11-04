"""Consecutive original framebuffer-feedback frames across game-state changes."""
import hashlib,json,os,shlex,struct,subprocess
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
ns={'__file__':str(fixture),'__name__':'stage10_transition_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
p=ns['port'];symbols=ns['symbols'];Machine=ns['Machine']
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage10_transition_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_transition_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(ns['elf_path']),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2].startswith('stage10_'):symbols[s[2]]=int(s[0],16)
def machine():
    m=Machine()
    for i in range(count):
        typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
        if typ==1 and length:m.uc.mem_write(addr,raw[pos:pos+length])
    m.word('game3ds_canonical',symbols['vram'])
    m.hook('game3ds_gpu_resolve',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,1),m.ret()))
    return m
results=[]
for label,state in [('room_gate',20),('nightmare_death',10),('gameplay_feedback',11)]:
    m=machine();m.call('stage10_transition_init')
    frames=[]
    for i in range(5):
        m.draws.clear();m.call('stage10_transition_frame',state,1 if i==0 else 2)
        sprites=[d for d in m.draws if d['textured']]
        fades=[d for d in m.draws if not d['textured'] and d['blend']==3]
        extent=[min(min(d['vertices'][0::9]) for d in sprites),
                max(max(d['vertices'][0::9]) for d in sprites)]
        assert extent==[0,400],(label,i,extent)
        assert all(d['page']&0x10000 for d in sprites),'feedback must bypass the normal 256x256 texture cache'
        assert len(fades)==1,(label,i,'missing original subtractive TILE',m.draws)
        frames.append(extent)
    results.append(dict(case=label,state=state,feedback_extents=frames,original_subtractive_fade=True))
report=dict(status='PASS',scope=__doc__,cases=results,
    elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_acceptance=False)
spatial=[]
for label,state in [('room_gate',20),('nightmare_death',10)]:
    m=machine();m.call('stage10_transition_init');captures=[]
    # This pass deliberately exercises the original even-vblank 127 level;
    # the fixture's default SDK recorder leaves R0 unchanged on return.
    clock=[0]
    m.hook('game3ds_vblank_clock',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,clock[0]),m.ret()))
    m.hook('game3ds_feedback_capture',lambda w,h,*_:(captures.append([w,h]),m.ret()))
    levels=list(range(32))
    for frame in range(32):
        clock[0]=frame*2
        m.draws.clear();m.call('stage10_transition_frame',state,0)
        sprites=[d for d in m.draws if d['textured']]
        # Use the actual ARM producer's XY/UV edges, at every native sample.
        # Tile boundaries must stitch without shifting/resolving through 320.
        covered=[]
        for d in sprites:
            assert d['page']&0x10000
            q=[d['vertices'][i*9:i*9+9] for i in range(3)]
            a,b,c=q;left,right=a[0],b[0];top,bottom=a[1],c[1]
            for x in range(round(left),round(right)):
                source=(a[3]+((x+.5-left)/(right-left))*(b[3]-a[3]))*512
                assert int(source)==x,(label,frame,x,source)
                covered.append(x)
            for y in range(240):
                source=(1-a[4]-((y+.5-top)/(bottom-top))*(c[4]-a[4]))*256
                assert int(source)==y,(label,frame,y,source)
            modulation=round(a[5]*128)
            assert modulation==127,'exercise the original decay, without an added fade quad'
        assert sorted(covered)==list(range(400))
        levels=[(v*127)>>7 for v in levels]
    assert captures==[[400,240]]*32 and not any(levels)
    spatial.append(dict(case=label,frames=32,capture_extent=[400,240],
        native_samples_remain_at_original_positions=True,original_modulation_reaches_black=True))
report['repeated_feedback_spatial_contract']=spatial
for overlap in (0,1):
    m=machine();m.call('stage10_transition_init');m.call('stage10_transition_invalidate',overlap)
    sprites=[d for d in m.draws if d['textured']]
    assert sprites and all(bool(d['page']&0x10000)==(not overlap) for d in sprites)
report['canonical_page_write_invalidates_native_snapshot']=True
sound=[]
for pair,expected in ((1,1309),(4,1354)):
    m=machine();requests=[]
    m.hook('SD_Call',lambda command,*_:(requests.append(command),m.ret()))
    # Stop at the first unrelated resource operation after the original
    # door-open request. No gameplay resources are faked by this fixture.
    m.hook('Bgm_TrackChange',lambda *_:m.uc.emu_stop())
    m.uc.reg_write(ns['UC_ARM_REG_SP'],0x1001ffc0)
    m.uc.reg_write(ns['UC_ARM_REG_LR'],0x30000000)
    m.uc.reg_write(UC_ARM_REG_R0,pair)
    m.uc.emu_start(symbols['stage10_transition_sfx'],0x30000000,count=1000000)
    assert not m.failure,m.failure
    assert requests==[expected],(pair,requests,expected)
    sound.append(dict(pair=pair,original_open_sfx=requests[0]))
report['original_transition_sound_requests']=sound
(p/'reports/stage10-transition-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
