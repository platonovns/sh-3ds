"""Freeze the tested normal Stage 10 checkpoint; never grant hardware acceptance."""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def write(f,v):f.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
candidate=p/'build/hardware-stage10-r1a';archive=p/'baselines/stage10-r1a.zip'
assert not candidate.exists() and not archive.exists(),'Never overwrite an archived candidate'
accepted=read(p/'reports/stage9-r6-accepted-freeze.json')
assert sha(root/accepted['archive'])==accepted['archive_sha256']
assert sha(p/'build/hardware-stage9-audio-r6-accepted/silenthill_game.3dsx')==accepted['sha256']
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
identity=re.search(r'"(stage10[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
ns={'__file__':str(p/'tools/build_identity.py')}
exec(compile((p/'tools/build_identity.py').read_text().split('digest = hashlib.sha256()')[0],
    'identity-inputs','exec'),ns)
digest=hashlib.sha256()
for f in sorted(set(ns['paths'])):digest.update(f.relative_to(root).as_posix().encode()+b'\0'+f.read_bytes()+b'\0')
assert identity=='stage10.0-src-'+digest.hexdigest()[:16]
elf=p/'silenthill_game.elf';binary=p/'silenthill_game.3dsx';elfsha=sha(elf)
assert identity.encode() in elf.read_bytes() and identity.encode() in binary.read_bytes()
assert 'SH_3DS_DEV_' not in (p/'build-game/flags').read_text()
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
nm=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
assert 'Game3ds_DevEnter' not in nm and 'Game3ds_DevNewGame' not in nm
suite=read(p/'reports/stage10-foundation-regressions.json')
assert suite['status']=='PASS' and len(suite['tests'])==20 and suite['elf_sha256']==elfsha,suite
for name in ('transition','particle','boot-warning','pause-stress','original-pause','gate-audio','profile-pcm'):
    test=read(p/f'reports/stage10-{name}-arm.json')
    assert test['status']=='PASS' and test['elf_sha256']==elfsha,(name,test)
assert read(p/'reports/stage10-cache-equivalence.json')['status']=='PASS'
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
published=read(p/'dev_server/published/manifest.json')
assert published['sha256']==sha(binary) and published['size']==binary.stat().st_size
http=read(p/'reports/stage10-r1a-http.json')
assert http['verified'] and http['sha256']==sha(binary) and http['size']==binary.stat().st_size
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):
    src=p/('silenthill_game'+ext);shutil.copy2(src,candidate/src.name)
shutil.copy2(root/'docs/3ds-stage10-r1a-handoff.md',candidate/'README.md')
record=dict(status='INTERMEDIATE HARDWARE CANDIDATE; USER TEST PENDING',hardware_accepted=False,
    stage10_complete=False,build=identity,binary=(candidate/binary.name).relative_to(root).as_posix(),
    bytes=binary.stat().st_size,sha256=sha(binary),elf_sha256=elfsha,
    archive=archive.relative_to(root).as_posix(),tests='20/20 PASS on final ELF',
    baseline_stage9_r6_preserved=True,memory_card_unchanged=True,normal_gameplay_no_diagnostic_setup=True,
    delivery=http,source_identity_inputs=len(set(ns['paths'])),
    performance=dict(scope='Azahar Cafe diagnostic; no NDSP, not hardware',
        work_before_ms=81.8779,work_after_ms=75.6401,cache_before_ms=8.5417,cache_after_ms=2.3222,
        remaining_command_ms=34.5636,remaining_world_ms=18.2397,remaining_primitive_ms=13.1949),
    pending=['real New 3DS presentation/START/audio/profile validation','natural Cafe firearm completion',
        'post-Cafe MAP2_S00 resident closure','melee/outdoor enemies/pickups','C-stick enhancement',
        'school approach and save','30 FPS performance target'])
write(p/'reports/stage10-r1a-candidate.json',record)
with zipfile.ZipFile(root/accepted['archive']) as z:previous=read_manifest=json.loads(z.read('manifest.json'))
paths={root/n for n in previous if (root/n).is_file() and not n.startswith(
    ('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
paths.update(ns['paths'])
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',p/'build/audio',candidate):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(f for f in (p/'reports').glob('stage10-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update((p/'build/build_identity.h',p/'build-game/flags',p/'build-game/native_data.inc',
    p/'build-game/native_items.inc',p/'build-game/tmd_emit.inc',p/'build-game/map0_s01.native.ld',
    root/'docs/3ds-stage10-r1a-handoff.md',root/'docs/3ds-stage10-request.md',
    root/'docs/3ds-stage9-r6-accepted.md',p/'reports/stage9-r6-accepted.json',
    p/'reports/stage9-r6-accepted-freeze.json',normal))
paths={f for f in paths if f.is_file()}
manifest={f.relative_to(root).as_posix():dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(paths)}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sorted(paths):z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for n,v in manifest.items():
        data=z.read(n);assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256'],n
receipt=dict(status='PASS',build=identity,archive=archive.relative_to(root).as_posix(),
    archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),manifest_files_verified=len(manifest),
    binary_sha256=sha(binary),elf_sha256=elfsha,hardware_accepted=False,stage10_complete=False)
write(p/'reports/stage10-r1a-freeze.json',receipt)
print(json.dumps(record,indent=2,ensure_ascii=False));print(json.dumps(receipt,indent=2))
