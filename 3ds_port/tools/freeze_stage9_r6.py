"""Freeze the authorized R6 audio candidate without publishing or accepting it."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,zipfile

p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def write(f,value):f.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

candidate=p/'build/hardware-stage9-audio-r6';archive=p/'baselines/stage9-audio-r6.zip'
assert not candidate.exists() and not archive.exists(),'Never overwrite a frozen candidate'
subprocess.run([sys.executable,str(p/'tools/audit_stage9_r6.py')],check=True,capture_output=True)
audit=read(p/'reports/stage9-r6-audit.json');assert audit['status']=='PASS'
elfsha=sha(p/'silenthill_game.elf')
assert elfsha=='3306e6252fd020ffb1d77053853e798c21e03292f2cc99054b7937b00041a18a'
assert sha(p/'silenthill_game.3dsx')=='dafee0513d08e841e34bbe177a7a1e8d02d365bd307dc184999c95acefd0f3ed'
assert (p/'silenthill_game.3dsx').stat().st_size==1014484
identity=re.search(r'"(stage9[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
assert identity=='stage9.0-src-b1645a424e58cb44'
reports={name:read(p/f'reports/stage9-r6-{name}.json') for name in
    ('audio-arm','ndsp-arm','xa-arm','diagnostics-arm','supplemental')}
assert all(r['status']=='PASS' and r['elf_sha256']==elfsha for r in reports.values())
host=(p/'reports/stage9-r6-xa-host.log').read_text()
for marker in ('PASS: 726 original XA requests','PASS: signed CD matrix','PsyX_XAStream fidelity: OK'):
    assert marker in host,marker
assert len(re.findall('identical at 30/60/12 FPS',host))==37
assert 'runtime error:' not in host and 'ERROR: AddressSanitizer' not in host
for name in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/name).exists(),name
assert not (p/'build/azahar/user/sdmc/3ds/dspfirm.cdc').exists()
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):
    src=p/('silenthill_game'+ext);dst=candidate/src.name
    shutil.copy2(src,dst);assert sha(src)==sha(dst)
shutil.copy2(root/'docs/3ds-stage9-r6-handoff.md',candidate/'README.md')
record=dict(status='HARDWARE CANDIDATE; NEW NINTENDO 3DS TEST PENDING',hardware_accepted=False,
    correction_hardware_validated=False,build=identity,
    binary=(candidate/'silenthill_game.3dsx').relative_to(root).as_posix(),
    bytes=(candidate/'silenthill_game.3dsx').stat().st_size,sha256=sha(candidate/'silenthill_game.3dsx'),
    elf_sha256=elfsha,archive=archive.relative_to(root).as_posix(),
    changes=dict(raw_batch_sectors=32,raw_batch_bytes=75264,stdio_buffer_bytes=75264,
        startup_threshold_frames=4096,ring_capacity_frames=16384,
        subtitle_ready_gate_preserved=True,rate_pitch_gain_unchanged=True),
    tests={name:'PASS' for name in reports},host_XA_entries=726,host_XA_complete_lines=37,
    host_XA_query_fps=[30,60,12],slow_IO_profiles=3,jitter_phase_cases=46,
    slow_IO_and_ARM_are_not_hardware_validation=True,
    hardware_test='New Game -> first voiced Cheryl sequence -> all Harry lines -> Quit application -> full stage4_status.txt',
    gameplay_validation_boundary='Hardware gameplay through Cafe only',
    diagnostics='Existing telemetry plus startup/missing/EOF/gap/batch/worker counters',
    next_steps_require_user_hardware_feedback=['Cafe/Cybil','Original START Skip','Single cap-60 check','Source/data audio coverage audit'],
    memory_card_unchanged=True,performance_backlog_unchanged='S9-PERF-01',
    delivery=dict(local_candidate_ready=True,HTTP_published=False,
        reason='Automatic approval review rejected publication and persistent HTTP server; no network action performed'))
write(p/'reports/stage9-r6-candidate.json',record)
subprocess.run([sys.executable,str(p/'tools/audit_stage9_r6.py')],check=True,capture_output=True)
with zipfile.ZipFile(p/'baselines/stage9-audio-r4.zip') as z:prior=json.loads(z.read('manifest.json'))
paths={root/n for n in prior if (root/n).is_file() and not n.startswith(
    ('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',p/'build/audio',candidate):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(root/n for n in read(p/'build/audio/inputs.json'))
paths.update(root/'pc_port/PsyCross/src/audio'/n for n in ('PsyX_XAStream.cpp','PsyX_XAStream.h'))
paths.add(root/'pc_port/PsyCross/tests/audio/PsyX_XAStream_fidelity_test.cpp')
paths.update(f for f in (p/'reports').rglob('stage9-r6-*') if f.is_file() and
    f.name!='stage9-r6-freeze.json' and f.stat().st_size<5*1024*1024)
paths.update(f for f in (p/'reports/stage9-r6-hardware-r4').rglob('*') if f.is_file())
paths.update(root/'docs'/n for n in ('3ds-stage9-r6-handoff.md','3ds-stage9-r6-hardware-starvation.md',
    '3ds-stage9-r5-stream-continuity.md','3ds-stage9-r4-playback-feedback.md',
    '3ds-stage9-r3-hardware-feedback.md','3ds-stage9-r2-hardware-feedback.md',
    '3ds-stage9-r1-hardware-feedback.md','3ds-stage8-r2-accepted.md','3ds-backlog.md'))
paths.update((p/'build/build_identity.h',p/'build-game/flags',p/'Makefile.game'))
# Only archive existing delivery dependencies referenced by the Makefile hook;
# do not invoke or modify them.
paths.update(f for f in (p/'dev_server').glob('*.py'))
paths=sorted(paths)
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in
    ('.bin','.cue','.mcr','.cdc','.wav','.pcm') for f in paths)
manifest={f.relative_to(root).as_posix():dict(bytes=f.stat().st_size,sha256=sha(f)) for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:
        name=f.relative_to(root).as_posix();data=f.read_bytes()
        assert hashlib.sha256(data).hexdigest()==manifest[name]['sha256'],name
        z.writestr(name,data)
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for name,v in manifest.items():
        data=z.read(name)
        assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256'],name
receipt=dict(status='PASS',hardware_accepted=False,build=identity,
    archive=archive.relative_to(root).as_posix(),archive_sha256=sha(archive),
    verified_archive_members=len(manifest),binary_sha256=record['sha256'],elf_sha256=elfsha)
write(p/'reports/stage9-r6-freeze.json',receipt)
print(json.dumps(dict(candidate=record,freeze=receipt),indent=2,ensure_ascii=False))
