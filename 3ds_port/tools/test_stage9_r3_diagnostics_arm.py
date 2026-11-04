"""Real ARM audio boundaries, counter fault discrimination and lifecycle hook."""
import struct,hashlib,json,re,os,shlex,subprocess
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_SP
fixture=Path(__file__).with_name('test_stage9_audio_arm.py')
src=fixture.read_text().split('out=0x24800000')[0]
src=src.replace('r.call(ctor)',"\nfor name in ('game_xa_lock','game_xa_unlock'):r.bridge(name,lambda *_:r.ret(0))\nr.call(ctor)")
ns={'__file__':str(fixture),'__name__':'diag_arm_fixture'}
exec(compile(src,str(fixture),'exec'),ns)
r=ns['r'];g=ns['game'];p=g.port;out=0x24800000
text=[]
def fprintf(handle,fmt,a,b):
    f=bytes(r.uc.mem_read(fmt,8192)).split(b'\0')[0].decode()
    count=len(re.findall(r'%(?:0?\d*)l?[udxi]',f))
    args=[a,b]+list(struct.unpack('<'+'I'*max(0,count-2),r.uc.mem_read(r.uc.reg_read(UC_ARM_REG_SP),max(0,count-2)*4)))
    it=iter(args)
    def sub(m):
        v=next(it);code=m[0][-1]
        if code in 'di' and v&0x80000000:v-=1<<32
        return format(v,'08x' if '08x' in m[0] else 'x') if code=='x' else str(v)
    text.append(re.sub(r'%(?:0?\d*)l?[udxi]',sub,f));r.ret(len(f))
r.bridge('fprintf',fprintf)
def snapshot():
    text.clear();r.call('game_xa_report',1);r.call('game_spu_audio_report',1)
    return dict(line.split('=',1) for line in ''.join(text).splitlines() if '=' in line)
def number(s,key):return int(s[key])
def drain():
    for _ in range(20):r.call('Sd_TaskPoolExecute')
def start():r.call('SD_Call',4097);drain()
start()
for _ in range(4):r.call('game_xa_step')
r.call('game_spu_render',out,4096);r.call('game_spu_xa_submitted',4096,8192)
audible=snapshot()
for key in ('xa_requests','xa_active_transitions','xa_worker_starts','xa_open_success','xa_seeks','xa_valid_form2',
            'xa_filter_matches','xa_decoded_sectors','xa_decoded_frames','xa_decoded_nonzero','xa_resampled_frames',
            'xa_resampled_nonzero','xa_ring_in','xa_ring_out','xa_matrix_nonzero','xa_spu_input_nonzero',
            'xa_spu_mix_nonzero','xa_spu_final_active_nonzero','xa_ndsp_submitted_frames'):
    assert number(audible,key)>0,(key,audible)
r.call('SdSetSerialVol',0,0,0)
r.call('game_xa_step');r.call('game_spu_render',out,1024)
muted=snapshot()
assert number(muted,'xa_ring_out')>number(audible,'xa_ring_out')
assert muted['xa_spu_mix_nonzero']==audible['xa_spu_mix_nonzero']
assert muted['xa_spu_last_audio_cd_volume']=='0,0'
r.call('SdSetSerialAttr',0,0,0)
r.call('game_spu_render',out,1024)
disabled=snapshot()
assert disabled['xa_ring_out']==muted['xa_ring_out']
assert number(disabled,'xa_spu_disabled_active_blocks')>number(muted,'xa_spu_disabled_active_blocks')
r.call('SdSetSerialVol',0,83,83);r.call('SdSetSerialAttr',0,0,1)
r.call('game_spu_render',out,1024)
assert number(snapshot(),'xa_spu_mix_nonzero')>number(disabled,'xa_spu_mix_nonzero')
r.call('SD_Call',19);drain()
# Link a fixture against the actual ELF symbols to drive Game3ds_Observe with
# the real game structs. No fixture functions are included in the candidate.
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage9_r3_probe.o';elf=p/'build/stage9_r3_probe.elf'
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage9_r3_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(g.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    v=line.split()
    if len(v)==3 and v[2]=='stage9_r3_context':g.symbols[v[2]]=int(v[0],16)
for name in ('game3ds_debug_enabled','game3ds_inventory_observe','stage4_fs_game_observe','game3ds_map_observe',
             'game3ds_player_observe','game3ds_animation_observe','game3ds_observe'):
    r.bridge(name,lambda *_:r.ret(0))
cases=[]
for name,ctx,reason in [('skip',(11,10,3,1),2),('return_gameplay',(11,0,3,0),3),
                        ('room',(11,10,4,0),4),('title',(7,10,3,0),5)]:
    r.call('stage9_r3_context',11,10,3,0)
    start()
    before=number(snapshot(),'xa_cancel_count')
    r.call('stage9_r3_context',11,10,3,0)
    assert number(snapshot(),'xa_cancel_count')==before,'normal cutscene observer canceled XA'
    r.call('stage9_r3_context',*ctx)
    s=snapshot();assert number(s,'xa_cancel_last')==reason,(name,s)
    assert not r.call('game_xa_pull',out,512)
    drain();assert not r.call('game_audio_xa_pending')
    cases.append(dict(case=name,reason=reason))
assert not r.failure and not r.invalid,(r.failure,r.invalid)
r.call('game_xa_close');r.call('game_audio_cd_close')
for f in r.handles.values():f.close()
report=dict(status='PASS',scope=__doc__,audible_pipeline=audible,zero_cd_volume=muted,disabled_cd_input=disabled,
    actual_native_lifecycle_cases=cases,normal_cutscene_does_not_cancel=True,
    elf_sha256=hashlib.sha256(g.game_elf.read_bytes()).hexdigest())
(p/'reports/stage9-r3-diagnostics-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('audible_pipeline','zero_cd_volume','disabled_cd_input')},indent=2))
