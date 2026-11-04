"""Freeze only the user-listened R4 correction; never infer hardware acceptance."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile,subprocess,sys
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
subprocess.run([sys.executable,str(p/'tools/audit_stage9_r4.py')],check=True,capture_output=True)
audit=read(p/'reports/stage9-r4-audit.json');assert audit['status']=='PASS'
feedback=read(p/'reports/stage9-r4-listening-feedback.json')
assert feedback['user_confirmed_audio_quality'] and not feedback['hardware_accepted']
elf_sha=sha(p/'silenthill_game.elf');assert elf_sha==feedback['elf_sha256']
assert sha(p/'build/stage9-r4-analysis/entry13-corrected-arm-spu.wav')==feedback['wav_sha256']
reports={n:read(p/f'reports/stage9-r4-{n}.json') for n in ('audio-arm','ndsp-arm','ndsp-format-arm','supplemental')}
for name,r in reports.items():
    assert r['status']=='PASS',name
    if 'elf_sha256' in r:assert r['elf_sha256']==elf_sha,name
capture=read(p/'reports/stage9-r4-corrected-arm-capture.json')
assert capture['elf_sha256']==elf_sha and capture['stages']['final_pcm_matches_each_modeled_sample']
assert capture['stages']['matrix_spu_input']['saturated']==0
assert capture['stages']['final_pcm']['saturated']==0
tests=(p/'reports/stage9-r4-xa-host.log').read_text()
for check in ('PASS: 726 original XA requests','PASS: signed CD matrix','PsyX_XAStream fidelity: OK'):
    assert check in tests,check
assert len(re.findall('identical at 30/60/12 FPS',tests))==37
assert 'runtime error:' not in tests and 'ERROR: AddressSanitizer' not in tests
for name in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/name).exists(),name
assert not (p/'build/azahar/user/sdmc/3ds/dspfirm.cdc').exists()
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
identity=re.search(r'"(stage9[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
candidate=p/'build/hardware-stage9-audio-r4';archive=p/'baselines/stage9-audio-r4.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):
    src=p/('silenthill_game'+ext);dst=candidate/src.name;shutil.copy2(src,dst);assert sha(src)==sha(dst)
shutil.copy2(root/'docs/3ds-stage9-r4-handoff.md',candidate/'README.md')
record=dict(status='HARDWARE CANDIDATE; NEW NINTENDO 3DS TEST PENDING',hardware_accepted=False,
    build=identity,binary=(candidate/'silenthill_game.3dsx').relative_to(root).as_posix(),
    bytes=(candidate/'silenthill_game.3dsx').stat().st_size,sha256=sha(candidate/'silenthill_game.3dsx'),elf_sha256=elf_sha,
    user_listening_feedback=feedback,correction='Signed PCM arithmetic in XA CD matrix; no rate or volume changes',
    R1_SFX_PCM_hashes_identical=True,host_XA_entries=726,host_XA_complete_lines=37,host_XA_query_fps=[30,60,12],
    hardware_test='New Game -> first voiced Cheryl event at 30 FPS -> Quit application -> return full stage4_status.txt',
    diagnostics='R3 telemetry retained',memory_card_unchanged=True,
    gameplay_validation_boundary='Hardware gameplay through Cafe only',performance_backlog_unchanged='S9-PERF-01')
report=p/'reports/stage9-r4-candidate.json';report.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
subprocess.run([sys.executable,str(p/'tools/audit_stage9_r4.py')],check=True,capture_output=True)
with zipfile.ZipFile(p/'baselines/stage9-audio-r3-diagnostic.zip') as z:prior=json.loads(z.read('manifest.json'))
paths={root/n for n in prior if (root/n).is_file() and not n.startswith(('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',p/'build/audio',candidate):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(root/n for n in read(p/'build/audio/inputs.json'))
paths.update(root/'pc_port/PsyCross/src/audio'/n for n in ('PsyX_XAStream.cpp','PsyX_XAStream.h'))
paths.add(root/'pc_port/PsyCross/tests/audio/PsyX_XAStream_fidelity_test.cpp')
paths.update(f for f in (p/'reports').glob('stage9-r4-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update(root/'docs'/n for n in ('3ds-stage9-r4-handoff.md','3ds-stage9-r3-hardware-feedback.md',
    '3ds-stage9-r2-hardware-feedback.md','3ds-stage9-r1-hardware-feedback.md','3ds-stage8-r2-accepted.md','3ds-backlog.md'))
paths.update((p/'build/build_identity.h',p/'build-game/flags',p/'Makefile.game'))
paths=sorted(paths)
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin','.cue','.mcr','.cdc','.wav') for f in paths)
manifest={f.relative_to(root).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for name,v in manifest.items():
        b=z.read(name);assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'],name
record.update(archive=archive.relative_to(root).as_posix(),archive_sha256=sha(archive),verified_archive_members=len(manifest))
report.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({k:record[k] for k in ('status','build','bytes','sha256','archive_sha256','verified_archive_members')},indent=2))
