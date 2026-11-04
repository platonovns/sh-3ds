"""Freeze qualified normal R2 sources/binary/evidence without hardware acceptance."""
import hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def write(f,v):f.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
candidate=p/'build/hardware-stage10-r2';archive=p/'baselines/stage10-r2.zip'
assert not candidate.exists() and not archive.exists(),'Never overwrite a frozen candidate'
r6=read(p/'reports/stage9-r6-accepted-freeze.json');r1a=read(p/'reports/stage10-r1a-freeze.json')
assert sha(root/r6['archive'])==r6['archive_sha256']
assert sha(root/r1a['archive'])==r1a['archive_sha256']
assert sha(p/'build/hardware-stage9-audio-r6-accepted/silenthill_game.3dsx')==r6['sha256']
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
identity=re.search(r'"(stage10[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
ns={'__file__':str(p/'tools/build_identity.py')}
exec(compile((p/'tools/build_identity.py').read_text().split('digest = hashlib.sha256()')[0],'identity-inputs','exec'),ns)
digest=hashlib.sha256()
for f in sorted(set(ns['paths'])):digest.update(f.relative_to(root).as_posix().encode()+b'\0'+f.read_bytes()+b'\0')
assert identity=='stage10.0-src-'+digest.hexdigest()[:16]
elf=p/'silenthill_game.elf';binary=p/'silenthill_game.3dsx';elfsha=sha(elf)
assert identity.encode() in elf.read_bytes() and identity.encode() in binary.read_bytes()
assert 'SH_3DS_DEV_' not in (p/'build-game/flags').read_text()
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
assert 'Game3ds_DevEnter' not in nm and 'Game3ds_DevNewGame' not in nm
assert 'map2_s00_g_MapOverlayHeader_map2_s00' in nm
suite=read(p/'reports/stage10-foundation-regressions.json')
assert suite['status']=='PASS' and len(suite['tests'])==24 and suite['elf_sha256']==elfsha,suite
for name in ('transition','particle','boot-warning','pause-stress','original-pause','gate-audio','profile-pcm','status','polyline'):
    test=read(p/f'reports/stage10-{name}-arm.json')
    assert test['status']=='PASS' and test['elf_sha256']==elfsha,(name,test)
assert read(p/'reports/stage10-weapon-table-audit.json')['elf_sha256']==elfsha
combat=read(p/'reports/stage10-cafe-original-exit-runtime.json')
assert combat['map']==10 and combat['outdoor_ticks']>=20
assert {f['flag'] for f in combat['natural_event_flags']}=={48,51}
assert not any(combat['run'][k] for k in ('failure','invalid','exception'))
run=read(p/'build/azahar/last-run.json')
assert run['build_sha256']==sha(binary) and run['build_identity']==identity
assert run['result']=='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED',run
launched=Path(run['launched'])
if os.name!='nt' and re.match(r'^[A-Za-z]:',run['launched']):
    launched=Path(subprocess.check_output(['wslpath','-u',run['launched']],text=True).strip())
normal=launched.parent/'stage4_status.txt'
status=dict(line.split('=',1) for line in normal.read_text().splitlines() if '=' in line)
assert status['first_failure']=='0' and status['boot_variant']=='NORMAL_NEW_GAME'
assert status['build']==identity and status['report_complete']=='1'
http=read(p/'reports/stage10-r2-http.json');published=read(p/'dev_server/published/manifest.json')
assert http['verified'] and http['sha256']==sha(binary) and http['size']==binary.stat().st_size
assert published['sha256']==sha(binary) and published['size']==binary.stat().st_size
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):
    f=p/('silenthill_game'+ext);shutil.copy2(f,candidate/f.name)
shutil.copy2(root/'docs/3ds-stage10-r2-handoff.md',candidate/'README.md')
record=dict(status='INTERMEDIATE HARDWARE CANDIDATE; USER TEST PENDING',hardware_accepted=False,
    stage10_complete=False,build=identity,binary=(candidate/binary.name).relative_to(root).as_posix(),
    bytes=binary.stat().st_size,sha256=sha(binary),elf_sha256=elfsha,
    archive=archive.relative_to(root).as_posix(),tests='24/24 PASS on final ELF',delivery=http,
    stage9_r6_preserved=True,stage10_r1a_preserved=True,memory_card_unchanged=True,
    normal_gameplay_no_diagnostic_setup=True,source_identity_inputs=len(set(ns['paths'])),
    combat_evidence='Development entry, then original pad/AI/death/event/door/MAP2 chain',
    performance=dict(scope='Azahar Cafe, no NDSP; different AI windows, not hardware',
        work_before_ms=75.6401,work_after_ms=69.4442,command_before_ms=34.5636,command_after_ms=28.0264),
    pending=['New 3DS visual/audio/input/performance validation','Air Screamer behind-Harry PS1 comparison',
        'outdoor Groaner/Air Screamer encounters, melee and pickups','C-stick directional movement',
        'school approach and save','30 FPS performance target'])
write(p/'reports/stage10-r2-candidate.json',record)
with zipfile.ZipFile(root/r1a['archive']) as z:previous=json.loads(z.read('manifest.json'))
paths={root/n for n in previous if (root/n).is_file() and not n.startswith(
    ('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
paths.update(ns['paths'])
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',p/'build/audio',candidate):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(f for f in (p/'reports').glob('stage10-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update(f for f in (root/'docs').glob('3ds-stage10-*.md'))
paths.update((p/'build/build_identity.h',p/'build-game/flags',p/'build-game/native_data.inc',
    p/'build-game/native_items.inc',p/'build-game/tmd_emit.inc',p/'build-game/map0_s01.native.ld',
    p/'build-game/map2_s00.native.ld',p/'reports/stage9-r6-accepted-freeze.json',
    p/'reports/stage10-r1a-freeze.json',normal))
paths={f for f in paths if f.is_file()}
manifest={f.relative_to(root).as_posix():dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(paths)}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sorted(paths):z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for name,v in manifest.items():
        data=z.read(name);assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256'],name
receipt=dict(status='PASS',build=identity,archive=archive.relative_to(root).as_posix(),
    archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),manifest_files_verified=len(manifest),
    binary_sha256=sha(binary),elf_sha256=elfsha,hardware_accepted=False,stage10_complete=False)
write(p/'reports/stage10-r2-freeze.json',receipt)
print(json.dumps(record,indent=2,ensure_ascii=False));print(json.dumps(receipt,indent=2))
