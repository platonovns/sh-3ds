"""Audit only the native XA readiness integration; no hardware acceptance."""
from pathlib import Path
import hashlib,json,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
expected={
    'baselines/stage8-diagnostic-r2.zip':'dffd08a195f33304f72c2abdb45784d9cfed7d410cfeca5eb66c88cbbc0911ee',
    'baselines/stage9-audio-r1.zip':'f1dea799457a6fa6f488d6d7135c2317477f3efbec5c41d01706167587e39613',
    'baselines/stage9-audio-r3-diagnostic.zip':'7c8ac772275f44be5504a00f2fcaa342e0353667d65656f51d52d04fefe05bb6',
    'baselines/stage9-audio-r4.zip':'319aa67723c0880f0347f0f7f2fa22d34ea72386c64ffbdb6933e8ead0cb8d8d',
    'build/hardware-stage9-audio-r4/silenthill_game.3dsx':'d957a6ea27a3d183038a78e64a5cc17b186cea117806bdc841beb71408db3dde',
    'build/hardware-stage9-audio-r4/silenthill_game.elf':'81e6183e17357f884ff72148b91ce7144ea37d2edd595343e341a6c4f3dc8379',
    'silenthill_game.3dsx':'d957a6ea27a3d183038a78e64a5cc17b186cea117806bdc841beb71408db3dde',
}
for name,value in expected.items():assert sha(p/name)==value,name
with zipfile.ZipFile(p/'baselines/stage9-audio-r4.zip') as z:
    names=[n for n in z.namelist() if n.startswith(('src/','include/','pc_port/','3ds_port/source/','3ds_port/include/','3ds_port/build/audio/')) and n.endswith(('.c','.cpp','.h','.inc'))]
    changed=sorted(n for n in names if (root/n).read_bytes()!=z.read(n))
    assert changed==['3ds_port/include/game_xa.h','3ds_port/source/game_xa.cpp','src/bodyprog/text/map_msg_display.c'],changed
    added='uint32_t game_xa_ready(void) { Guard g;return s.active && !s.error && s.played!=0; }\n'
    assert (p/'source/game_xa.cpp').read_text().replace(added,'')==z.read('3ds_port/source/game_xa.cpp').decode().replace('\r\n','\n')
    assert (p/'Makefile.game').read_bytes()==z.read('3ds_port/Makefile.game')
old=read(p/'reports/stage9-audio-arm.json');new=read(p/'reports/stage9-r5-audio-arm.json')
assert old['cases']==new['cases']
for k in ('original_volume_options','KDT_music_nonzero','KDT_keyons','timer_ticks_10_seconds'):assert old[k]==new[k],k
elfsha=sha(p/'silenthill_game.elf')
for name in ('audio-arm','ndsp-arm','subtitle-arm','regressions','compatibility'):
    result=read(p/f'reports/stage9-r5-{name}.json');assert result['status']=='PASS' and result['elf_sha256']==elfsha,name
assert len(read(p/'reports/stage9-r5-regressions.json')['results'])==14
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
assert not (p/'build/hardware-stage9-audio-r5').exists()
assert not (p/'build/azahar/user/sdmc/3ds/dspfirm.cdc').exists()
for n in ('stage7_input.txt','stage7_pad.txt','stage6_observe.txt'):assert not (root/'sh1_data'/n).exists(),n
report=dict(status='PASS',production_files_changed=changed,compared_source_files=len(names),
    preserved_hashes=expected,R1_nine_PCM_cases_KDT_gain_clock_identical=True,
    audio_decode_resample_matrix_SPU_NDSP_math_unchanged=True,
    authored_timers_rates_pitch_unchanged=True,final_elf_sha256=elfsha,
    hardware_accepted=False,no_new_hardware_candidate=True,emulator_only_HLE_placeholder_removed=True)
(p/'reports/stage9-r5-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
