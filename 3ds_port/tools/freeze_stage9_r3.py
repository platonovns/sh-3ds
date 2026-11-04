"""Freeze a diagnostic hardware candidate; never mark Stage 9 accepted."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
baseline=read(p/'reports/stage9-r3-baseline.json');assert baseline['status']=='PASS'
elf_sha=sha(p/'silenthill_game.elf')
reports={n:read(p/'reports'/('stage9-r3-'+n+'.json')) for n in ('audio-arm','ndsp-arm','xa-arm','diagnostics-arm','regressions','compatibility')}
for name,r in reports.items():assert r['status']=='PASS' and r['elf_sha256']==elf_sha,(name,r)
assert len(reports['regressions']['results'])==14
assert reports['audio-arm']['cases']==read(p/'reports/stage9-audio-arm.json')['cases']
assert reports['diagnostics-arm']['normal_cutscene_does_not_cancel']
assert len(reports['diagnostics-arm']['actual_native_lifecycle_cases'])==4
tests=(p/'reports/stage9-r3-xa-tests.log').read_text()
assert 'PASS: 726 original XA requests' in tests and len(re.findall('identical at 30/60/12 FPS',tests))==37
assert 'PsyX_XAStream fidelity: OK' in tests and 'runtime error:' not in tests and 'ERROR: AddressSanitizer' not in tests
identity=re.search(r'"(stage9[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
evidence=p/'reports/azahar-stage9-r3-cheryl'
s=dict(line.split('=',1) for line in (evidence/'r3-cheryl.txt').read_text().splitlines() if '=' in line)
assert s['build']==identity and s['first_failure']=='0' and s['report_complete']=='1' and s['map_idx']=='0'
for n in ('xa_requests','xa_active_transitions','xa_worker_starts','xa_decoded_nonzero','xa_spu_input_nonzero','xa_spu_mix_nonzero','xa_spu_final_active_nonzero','xa_ndsp_submitted_frames'):
    assert int(s[n])>0,n
assert s['xa_last_error']=='0' and s['audio_ndsp_result']=='0'
assert sha(root/'sh1_data/memcard.mcr').upper()==read(evidence/'card-before.json')['Hash']==read(evidence/'card-after.json')['Hash']
for name in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/name).exists(),name
assert not (p/'build/azahar/user/sdmc/3ds/dspfirm.cdc').exists()
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
candidate=p/'build/hardware-stage9-audio-r3';archive=p/'baselines/stage9-audio-r3-diagnostic.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
shutil.copy2(root/'docs/3ds-stage9-r3-handoff.md',candidate/'README.md')
record=dict(status='DIAGNOSTIC HARDWARE CANDIDATE; USER NEW 3DS CHERYL TEST PENDING',candidate_kind='DIAGNOSTIC',
    hardware_accepted=False,root_cause='NOT PROVEN WITHOUT INTEGRATED HARDWARE TELEMETRY',build=identity,
    binary=str((candidate/'silenthill_game.3dsx').relative_to(root)),bytes=(candidate/'silenthill_game.3dsx').stat().st_size,
    sha256=sha(candidate/'silenthill_game.3dsx'),elf_sha256=elf_sha,baseline_audit=baseline,tests=reports,
    R1_SFX_PCM_hashes_identical=True,host_XA_entries=726,host_XA_complete_lines=37,host_XA_query_fps=[30,60,12],
    emulator=dict(scope='Actual original New Game/Cheryl event, Azahar HLE only; hardware failure not reproduced',
        counters={k:s[k] for k in ('xa_requests','xa_first_request','xa_last_request','xa_worker_starts','xa_decoded_nonzero',
            'xa_ring_in','xa_ring_out','xa_spu_mix_nonzero','xa_spu_final_active_nonzero','xa_ndsp_submitted_frames','xa_cancel_last','xa_cancel_played','xa_last_error')},
        memory_card_unchanged=True,emulator_only_placeholder_removed=True),
    hardware_test='New Game, first spoken Cheryl encounter, clean Quit application, return entire stage4_status.txt',
    no_Cafe_progression_for_testing=True,performance_backlog_unchanged='S9-PERF-01, Cafe monster R1 10–12 FPS',
    gameplay_validation_boundary='Cafe only; no broader gameplay/hardware claims')
report=p/'reports/stage9-r3-candidate.json';report.write_text(json.dumps(record,indent=2)+'\n')
with zipfile.ZipFile(p/'baselines/stage9-audio-r2.zip') as z:prior=json.loads(z.read('manifest.json'))
paths={root/n for n in prior if (root/n).is_file() and not n.startswith(('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',p/'build/audio',candidate,evidence):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(root/n for n in read(p/'build/audio/inputs.json'))
paths.update(root/'pc_port/PsyCross/src/audio'/n for n in ('PsyX_XAStream.cpp','PsyX_XAStream.h'))
paths.add(root/'pc_port/PsyCross/tests/audio/PsyX_XAStream_fidelity_test.cpp')
paths.update(f for f in (p/'reports').glob('stage9-r3-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update(root/'docs'/n for n in ('3ds-stage9-r3-handoff.md','3ds-stage9-r2-hardware-feedback.md',
    '3ds-stage9-r1-hardware-feedback.md','3ds-stage8-r2-accepted.md','3ds-backlog.md'))
paths.update((p/'build/build_identity.h',p/'build-game/flags',p/'Makefile.game'))
paths=sorted(paths)
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin','.cue','.mcr','.cdc') for f in paths)
manifest={str(f.relative_to(root)).replace('\\','/'):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:z.write(f,str(f.relative_to(root)))
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for n,v in manifest.items():
        b=z.read(n);assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'],n
record.update(archive_sha256=sha(archive),verified_archive_members=len(manifest))
report.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('status','candidate_kind','build','bytes','sha256','archive_sha256','verified_archive_members')},indent=2))
