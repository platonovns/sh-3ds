"""Audit the hardware starvation evidence and bounded XA-only correction."""
from pathlib import Path
import hashlib,json,re,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
frozen=read(p/'reports/stage9-r5-audit.json')['preserved_hashes']
# The working output is now authorized to become R6; immutable R4 stays frozen.
frozen.pop('silenthill_game.3dsx')
for name,value in frozen.items():assert sha(p/name)==value,name
with zipfile.ZipFile(p/'baselines/stage9-audio-r4.zip') as z:
    names=[n for n in z.namelist() if n.startswith(('src/','include/','pc_port/','3ds_port/source/','3ds_port/include/','3ds_port/build/audio/')) and n.endswith(('.c','.cpp','.h','.inc'))]
    changed=sorted(n for n in names if (root/n).read_bytes()!=z.read(n))
    assert changed==['3ds_port/include/game_xa.h','3ds_port/source/game_xa.cpp',
        '3ds_port/source/game_xa_thread.c','src/bodyprog/text/map_msg_display.c'],changed
    current=(p/'Makefile.game').read_text()
    baseline=z.read('3ds_port/Makefile.game').decode()
    delivery_hook='\t@python3 dev_server/after_build.py "$(OUTPUT).3dsx"\n'
    assert current==baseline or current==baseline.replace('link: $(OUTPUT).3dsx\n',
        'link: $(OUTPUT).3dsx\n'+delivery_hook), 'Unexpected build recipe changes'
old=read(p/'reports/stage9-audio-arm.json');new=read(p/'reports/stage9-r6-audio-arm.json')
assert old['cases']==new['cases']
for key in ('original_volume_options','KDT_music_nonzero','KDT_keyons','timer_ticks_10_seconds'):assert old[key]==new[key],key
elfsha=sha(p/'silenthill_game.elf')
for name in ('audio-arm','ndsp-arm','xa-arm','diagnostics-arm','supplemental'):
    r=read(p/f'reports/stage9-r6-{name}.json');assert r['status']=='PASS' and r['elf_sha256']==elfsha,name
hashes=lambda n:re.findall(r'line (\d+).*pcm=([0-9a-f]+)',(p/f'reports/{n}').read_text())
assert len(hashes('stage9-r6-xa-host.log'))==37
assert hashes('stage9-r6-xa-host.log')==hashes('stage9-r5-xa-host.log')
model=read(p/'reports/stage9-r6-latency.json');sweep=read(p/'reports/stage9-r6-latency-phase-sweep.json')
assert len(model)==6 and len(sweep)==46
assert all(v['missing']>0 for v in model if v['label']=='r4')
assert all(v['missing']==v['longest_gap_frames']==0 for v in model if v['label']=='working')
assert all(v['missing']==0 for v in sweep)
hw=read(p/'reports/stage9-r6-hardware-r4/analysis.json')
assert hw['underflow_blocks']==672 and hw['total_missing_including_startup_frames']==292704
assert sha(p/'reports/stage9-r6-hardware-r4/stage4_status.txt')==hw['sha256']
candidate=p/'build/hardware-stage9-audio-r6'
if candidate.exists():
    record=read(p/'reports/stage9-r6-candidate.json')
    assert not record['hardware_accepted']
    assert record['elf_sha256']==elfsha==sha(candidate/'silenthill_game.elf')
    assert record['sha256']==sha(candidate/'silenthill_game.3dsx')==sha(p/'silenthill_game.3dsx')
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
report=dict(status='PASS',production_files_changed_from_R4=changed,compared_source_files=len(names),
    R1_nine_PCM_cases_gain_KDT_clock_identical=True,first_37_XA_PCM_hashes_identical=True,
    slow_IO_profiles=3,jitter_phase_cases=len(sweep),hardware_R4_starvation_confirmed=True,
    correction_hardware_validated=False,hardware_accepted=False,hardware_candidate_present=candidate.exists(),
    build_recipe_only_delivery_hook_changed=current!=baseline,
    frozen_hashes_preserved=frozen,elf_sha256=elfsha)
(p/'reports/stage9-r6-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
