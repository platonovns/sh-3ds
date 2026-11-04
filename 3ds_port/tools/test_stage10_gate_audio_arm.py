"""Original door/gate and weapon requests resolve through VAB/SPU to real PCM."""
import hashlib,json,struct
from pathlib import Path
fixture=Path(__file__).with_name('test_stage9_audio_arm.py')
ns={'__file__':str(fixture),'__name__':'stage10_gate_audio'}
exec(compile(fixture.read_text().split('out=0x24800000')[0],str(fixture),'exec'),ns)
r=ns['r'];g=ns['game'];cases=[];out=0x24800000
for sfx in (1309,1354,1283,1284,1293):
    r.call('SD_Call',16)
    if sfx in (1309,1354):r.call('SD_Call',sfx)
    else:
        # Original handgun fire/reload and knife wrappers at half gain.
        # This component uses mono/no-distance flags; spatial mixing has
        # separate R6 regressions. No replacement sample or direct SPU key-on.
        position=out+0x10000;r.uc.mem_write(position,bytes(12))
        r.call('func_8005DC1C',sfx,position,128,3)
    for _ in range(4):r.call('Sd_TaskPoolExecute')
    r.call('game_spu_render',out,8192)
    pcm=bytes(r.uc.mem_read(out,8192*4));samples=struct.unpack('<16384h',pcm)
    nz=sum(x!=0 for x in samples)
    assert nz>0,(sfx,r.failure,r.invalid)
    cases.append(dict(original_sfx=sfx,nonzero_samples=nz,peak=max(abs(x) for x in samples),sha256=hashlib.sha256(pcm).hexdigest()))
assert not r.failure and not r.invalid
for f in r.handles.values():f.close()
report=dict(status='PASS',scope=__doc__,cases=cases,hardware_acceptance=False,
    elf_sha256=hashlib.sha256(g.game_elf.read_bytes()).hexdigest())
(g.port/'reports/stage10-gate-audio-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
