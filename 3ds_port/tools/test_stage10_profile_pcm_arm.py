"""Enabled ARM SPU profiling must retain accepted R6 PCM bit-for-bit."""
import hashlib,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0
fixture=Path(__file__).with_name('test_stage9_audio_arm.py')
src=fixture.read_text().split('# Original option gain')[0]
src=src.replace("r.call('SD_Init')","r.call('SD_Init')\nr.call('game_prof_enable',1)")
src=src.replace('cases=[]', '''categories=[]
r.uc.hook_add(UC_HOOK_CODE,lambda u,*_:categories.append(u.reg_read(UC_ARM_REG_R0)),
    begin=game.symbols['game_prof_audio_add'],end=game.symbols['game_prof_audio_add'])
cases=[]''')
ns={'__file__':str(fixture),'__name__':'stage10_profile_pcm','UC_ARM_REG_R0':UC_ARM_REG_R0}
exec(compile(src,str(fixture),'exec'),ns)
g=ns['game'];r=ns['r'];p=g.port
accepted=json.loads((p/'reports/stage9-r6-audio-arm.json').read_text())
disabled=json.loads((p/'reports/stage9-audio-arm.json').read_text())
assert ns['cases']==disabled['cases'],'Profiling changed current PCM or voice allocation'
# Original SdVoKeyOn returns uninitialized vc when a program has no matching
# tones (smf_snd.c). The two accepted silent negative cases therefore have
# no stable return-register oracle across link layouts. Compare all PCM bits
# and all audible voice allocations; do not change the accepted audio code.
silent_returns=[]
for current,baseline in zip(ns['cases'],accepted['cases'],strict=True):
    for key in ('sfx','nonzero','peak','sha256'):assert current[key]==baseline[key],(key,current,baseline)
    if baseline['nonzero']:assert current['voice']==baseline['voice'],(current,baseline)
    elif current['voice']!=baseline['voice']:silent_returns.append(current['sfx'])
assert {20,21,23,24,25}.issubset(ns['categories']),set(ns['categories'])
assert not r.failure and not r.invalid
for f in r.handles.values():f.close()
report=dict(status='PASS',scope=__doc__,PCM_cases=len(ns['cases']),
    negative_case_undefined_return_ids=silent_returns,
    observed_profiler_categories=sorted(set(ns['categories'])),
    elf_sha256=hashlib.sha256(g.game_elf.read_bytes()).hexdigest(),hardware_accepted=False)
(p/'reports/stage10-profile-pcm-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
