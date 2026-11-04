"""Capture original XA task -> actual linked ARM worker/resampler/SPU PCM.

Only IO, allocation and lock scheduling are host boundaries. No decoder,
resampler, volume, SPU arithmetic or output samples are replaced.
"""
import struct, hashlib, json, wave, os, math
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R1,UC_ARM_REG_R2
from pathlib import Path
fixture=Path(__file__).with_name('test_stage9_r3_diagnostics_arm.py')
src=fixture.read_text().split('start()\nfor _ in range(4)')[0]
ns={'__file__':str(fixture),'__name__':'capture_arm_fixture'}
exec(compile(src,str(fixture),'exec'),ns)
r=ns['r'];g=ns['g'];p=g.port;out=ns['out'];snapshot=ns['snapshot']
idx=int(os.environ.get('XA_ENTRY','13'));label=os.environ.get('XA_LABEL','r3')
ticks=next(int(l.split()[2]) for l in (p/'build/stage9-r2-xa-items.txt').read_text().splitlines() if int(l.split()[0])==idx)
matrix=[]
push=next(v for k,v in g.symbols.items() if 'PushCdStereoFrameEss' in k)
def pushed(uc,*_):
    for reg in (UC_ARM_REG_R1,UC_ARM_REG_R2):
        v=uc.reg_read(reg)&65535;matrix.append(v-65536 if v&32768 else v)
r.uc.hook_add(UC_HOOK_CODE,pushed,begin=push,end=push)
r.call('SD_Call',4096+idx);ns['drain']()
pcm=bytearray()
for frame in range(0,ticks*735,512):
    for _ in range(4):r.call('game_xa_step')
    n=min(512,ticks*735-frame)
    r.call('game_spu_render',out,n);r.call('game_spu_xa_submitted',n,n*2)
    pcm.extend(r.uc.mem_read(out,n*4))
    if frame%16384==0:print(f'{label}: {frame}/{ticks*735} frames',flush=True)
samples=struct.unpack('<'+'h'*(len(pcm)//2),pcm)
dest=p/'build/stage9-r4-analysis';dest.mkdir(parents=True,exist_ok=True)
with wave.open(str(dest/f'entry{idx}-{label}-arm-spu.wav'),'wb') as w:
    w.setparams((2,2,44100,0,'NONE','not compressed'));w.writeframes(pcm)
report=dict(elf=str(g.game_elf),elf_sha256=hashlib.sha256(g.game_elf.read_bytes()).hexdigest(),entry=idx,
    frames=len(pcm)//4,seconds=len(pcm)/4/44100,peak=max(map(abs,samples)),
    saturated=sum(v in (-32768,32767) for v in samples),pcm_sha256=hashlib.sha256(pcm).hexdigest(),telemetry=snapshot())
def stats(values):
    return dict(samples=len(values),peak=max(map(abs,values),default=0),minimum=min(values,default=0),maximum=max(values,default=0),
        saturated=sum(v in (-32768,32767) for v in values),rms=math.sqrt(sum(v*v for v in values)/max(1,len(values))),
        dc=sum(values)/max(1,len(values)))
cdvol=list(map(int,report['telemetry']['xa_spu_last_audio_cd_volume'].split(',')))
master=list(map(int,report['telemetry']['xa_spu_last_audio_current_master'].split(',')))
postcd=[v*cdvol[i%2]>>15 for i,v in enumerate(matrix)]
expected=[max(-32768,min(32767,v))*master[i%2]>>15 for i,v in enumerate(postcd)]
assert list(samples[:len(expected)])==expected,'isolated XA output differs from CD/mix/master model'
assert not any(samples[len(expected):]),'unexpected non-XA tail'
report['stages']=dict(matrix_spu_input=stats(matrix),post_cd_and_mix_accumulator=stats(postcd),final_pcm=stats(samples),
    cd_volume=cdvol,master_volume=master,xa_master_gain_q16=65536,
    final_pcm_matches_each_modeled_sample=True,isolated_voice_fixture_no_other_active_voices=True)
assert not r.failure and not r.invalid,(r.failure,r.invalid)
(p/f'reports/stage9-r4-{label}-arm-capture.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='telemetry'},indent=2))
r.call('game_xa_close');r.call('game_audio_cd_close')
for f in r.handles.values():f.close()
