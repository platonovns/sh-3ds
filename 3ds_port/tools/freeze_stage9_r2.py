"""Freeze native XA candidate and evidence; never grant hardware acceptance."""
from pathlib import Path
import hashlib,json,re,shutil,struct,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
baseline=read(p/'reports/stage9-r2-baseline.json');assert baseline['status']=='PASS'
elf_sha=sha(p/'silenthill_game.elf')
reports={n:read(p/'reports'/('stage9-r2-'+n+'.json')) for n in ('audio-arm','ndsp-arm','xa-arm','regressions','compatibility')}
for name,r in reports.items():assert r['status']=='PASS' and r['elf_sha256']==elf_sha,(name,r)
assert len(reports['regressions']['results'])==14
assert reports['xa-arm']['original_xa_requests_verified']==726
assert reports['xa-arm']['natural_completion_via_original_watchdog']
r1=read(p/'reports/stage9-audio-arm.json')
assert reports['audio-arm']['cases']==r1['cases']
tests=(p/'reports/stage9-r2-xa-tests.log').read_text()
assert 'PASS: 726 original XA requests match raw Form2/filter/coding headers' in tests
assert len(re.findall(r'identical at 30/60/12 FPS',tests))==37
assert 'PsyX_XAStream fidelity: OK' in tests and 'concurrent seek/stop' in tests
assert 'runtime error:' not in tests and 'ERROR: AddressSanitizer' not in tests
identity=re.search(r'"(stage9[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
evidence=p/'reports/azahar-stage9-r2-cafe'
observations={}
for mode in ('30','60'):
    s=dict(line.split('=',1) for line in (evidence/('cafe-'+mode+'.txt')).read_text().splitlines() if '=' in line)
    assert s['build']==identity and s['first_failure']=='0' and s['report_complete']=='1'
    assert s['game_state']=='11' and s['map_idx']=='1' and s['audio_ndsp_result']=='0' and s['audio_started']=='1'
    assert s['xa_error']=='0' and int(s['audio_nonzero_samples'])>0
    observations[mode]={k:s[k] for k in ('recent_fps','audio_ndsp_dropped','audio_busy','xa_starts','xa_error','player_x','player_z','player_yaw')}
assert sha(root/'sh1_data/memcard.mcr').upper()==read(evidence/'card-before.json')['Hash']
assert read(evidence/'card-before.json')['Hash']==read(evidence/'card-after.json')['Hash']
for n in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/n).exists(),n
assert not (p/'build/azahar/user/sdmc/3ds/dspfirm.cdc').exists()
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
candidate=p/'build/hardware-stage9-audio-r2';archive=p/'baselines/stage9-audio-r2.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
shutil.copy2(root/'docs/3ds-stage9-r2-handoff.md',candidate/'README.md')
(candidate/'diagnostics').mkdir();(candidate/'diagnostics/stage6_observe.txt').write_bytes(b'OBSERVE\n')
def sections(f):
    b=f.read_bytes();off=struct.unpack_from('<I',b,32)[0];size,count,strings=struct.unpack_from('<HHH',b,46)
    h=[struct.unpack_from('<10I',b,off+i*size) for i in range(count)]
    names=b[h[strings][4]:h[strings][4]+h[strings][5]]
    return {names[s[0]:].split(b'\0')[0].decode():s[5] for s in h}
current=sections(p/'silenthill_game.elf');prior_sections=sections(p/'build/hardware-stage9-audio-r1/silenthill_game.elf')
record=dict(status='HARDWARE CANDIDATE; USER NEW 3DS XA TEST PENDING',hardware_accepted=False,
    build=identity,binary=str((candidate/'silenthill_game.3dsx').relative_to(root)),
    bytes=(candidate/'silenthill_game.3dsx').stat().st_size,sha256=sha(candidate/'silenthill_game.3dsx'),elf_sha256=elf_sha,
    baseline_audit=baseline,tests=reports,all_R1_SFX_fixture_PCM_hashes_identical=True,
    host_XA=dict(entries=726,complete_lines=37,query_FPS=[30,60,12],sanitizers='ASan+UBSan',spectral_fidelity='PASS',
        log='3ds_port/reports/stage9-r2-xa-tests.log'),
    sections={n:current[n] for n in ('.text','.rodata','.data','.bss')},
    bss_delta_to_R1=current['.bss']-prior_sections['.bss'],xa_pcm_ring_bytes=65536,xa_worker_stack_bytes=24576,
    emulator=dict(context='Azahar HLE DSP; labelled emulator-only placeholder removed; no firmware bundled',
        scope='Original Title and existing Cafe save, not full Cybil dialogue completion',caps=observations,memory_card_unchanged=True),
    hardware_validation_pending=['Cafe Cybil/Harry voice quality and timing','normal conversation completion','original START skip',
        'pause where eligible and APT sleep/resume','Title/reload','simultaneous original music/SFX/voices'],
    gameplay_validation_boundary='Cafe only; no beyond-Cafe hardware validation claimed',
    performance_backlog='S9-PERF-01: user R1 Cafe monster cutscene 10–12 FPS, deferred')
report=p/'reports/stage9-r2-candidate.json';report.write_text(json.dumps(record,indent=2)+'\n')
with zipfile.ZipFile(p/'baselines/stage9-audio-r1.zip') as z:prior=json.loads(z.read('manifest.json'))
paths={root/n for n in prior if (root/n).is_file() and not n.startswith(('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',candidate,p/'build/audio',evidence):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(root/n for n in read(p/'build/audio/inputs.json'))
paths.update(root/'pc_port/PsyCross/src/audio'/n for n in ('PsyX_XAStream.cpp','PsyX_XAStream.h'))
paths.add(root/'pc_port/PsyCross/tests/audio/PsyX_XAStream_fidelity_test.cpp')
paths.update(f for f in (p/'reports').glob('stage9-r2-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update(root/'docs'/n for n in ('3ds-stage9-r2-handoff.md','3ds-stage9-r1-hardware-feedback.md','3ds-backlog.md','3ds-stage8-r2-accepted.md'))
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
print(json.dumps({k:record[k] for k in ('status','build','bytes','sha256','elf_sha256','archive_sha256','verified_archive_members','bss_delta_to_R1')},indent=2))
