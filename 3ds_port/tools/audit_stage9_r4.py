"""Verify the narrow production change and preserve frozen acceptance evidence."""
from pathlib import Path
import hashlib,json,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
expected={
    'baselines/stage8-diagnostic-r2.zip':'dffd08a195f33304f72c2abdb45784d9cfed7d410cfeca5eb66c88cbbc0911ee',
    'baselines/stage9-audio-r1.zip':'f1dea799457a6fa6f488d6d7135c2317477f3efbec5c41d01706167587e39613',
    'baselines/stage9-audio-r2.zip':'37fd3037e7f6f37227981d23eaece686883366cc5f4d4319c2af8614542941f2',
    'baselines/stage9-audio-r3-diagnostic.zip':'7c8ac772275f44be5504a00f2fcaa342e0353667d65656f51d52d04fefe05bb6',
    'build/hardware-stage9-audio-r1/silenthill_game.3dsx':'64fa06ea86ad82c7ad6ea5df7dbaddb24a5807a9d306db5ea15b2491d165e92c',
    'build/hardware-stage9-audio-r3/silenthill_game.3dsx':'87a20bb31c46e36d4d577386f95a983c5b233f8cd42cd0c80bae3fa0837c1345',
}
for name,value in expected.items():assert sha(p/name)==value,name
with zipfile.ZipFile(p/'baselines/stage9-audio-r3-diagnostic.zip') as z:
    prefixes=('src/','include/','pc_port/','3ds_port/source/','3ds_port/include/','3ds_port/build/audio/')
    names=[n for n in z.namelist() if n.startswith(prefixes) and n.endswith(('.c','.cpp','.h','.inc'))]
    names+=['3ds_port/Makefile.game','3ds_port/tools/prepare_audio.py']
    changed=[n for n in names if (root/n).read_bytes()!=z.read(n)]
    assert changed==['3ds_port/source/game_xa.cpp'],changed
old=json.loads((p/'reports/stage9-audio-arm.json').read_text())
new=json.loads((p/'reports/stage9-r4-audio-arm.json').read_text())
assert old['cases']==new['cases']
for key in ('original_volume_options','KDT_music_nonzero','KDT_keyons','timer_ticks_10_seconds'):
    assert old[key]==new[key],key
oldpcm=json.loads((p/'reports/stage9-r4-r3-arm-capture.json').read_text())
newpcm=json.loads((p/'reports/stage9-r4-corrected-arm-capture.json').read_text())
assert oldpcm['frames']==newpcm['frames']==130095
assert oldpcm['telemetry']['xa_played']==newpcm['telemetry']['xa_played']=='129360'
assert oldpcm['stages']['matrix_spu_input']['saturated']==130668
assert newpcm['stages']['matrix_spu_input']['saturated']==0
assert newpcm['stages']['final_pcm']['saturated']==0
assert newpcm['telemetry']['xa_underflows']=='0'
candidate=p/'build/hardware-stage9-audio-r4'
approval=p/'reports/stage9-r4-listening-feedback.json'
confirmed=False
if approval.exists():
    feedback=json.loads(approval.read_text(encoding='utf-8'))
    assert feedback['user_confirmed_audio_quality'] is True
    assert feedback['elf_sha256']==sha(p/'silenthill_game.elf')
    assert feedback['wav_sha256']==sha(p/'build/stage9-r4-analysis/entry13-corrected-arm-spu.wav')
    confirmed=True
if candidate.exists():
    assert confirmed
    for ext in ('.3dsx','.elf','.map','.smdh'):
        assert sha(candidate/('silenthill_game'+ext))==sha(p/('silenthill_game'+ext))
report=dict(status='PASS',production_files_changed_from_frozen_R3=changed,compared_source_files=len(names),
    preserved_frozen_hashes=expected,R1_all_nine_PCM_cases_and_KDT_volume_clock_identical=True,
    rate_and_duration_unchanged=True,no_hardware_R4_candidate_created=not candidate.exists(),
    user_listening_confirmed=confirmed,
    hardware_acceptance='NOT ACCEPTED; awaiting New Nintendo 3DS test' if confirmed else
        'NOT ACCEPTED; awaiting user listening feedback before preparing a hardware candidate',
    corrected_elf_sha256=sha(p/'silenthill_game.elf'))
(p/'reports/stage9-r4-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
