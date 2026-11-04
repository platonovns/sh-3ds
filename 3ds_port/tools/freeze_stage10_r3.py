"""Freeze a qualified normal R3 with exact delivery and no hardware acceptance."""
import hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def write(f,v):f.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
candidate=p/'build/hardware-stage10-r3';archive=p/'baselines/stage10-r3.zip'
assert not candidate.exists() and not archive.exists(),'Never overwrite a frozen candidate'
accepted=[]
for name in ('stage9-r6-accepted','stage10-r1a','stage10-r2'):
    receipt=read(p/f'reports/{name}-freeze.json')
    assert sha(root/receipt['archive'])==receipt['archive_sha256']
    accepted.append(dict(name=name,archive_sha256=receipt['archive_sha256']))
elf=p/'silenthill_game.elf';binary=p/'silenthill_game.3dsx';elfsha=sha(elf)
identity=re.search(r'"(stage10[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
ns={'__file__':str(p/'tools/build_identity.py')}
exec(compile((p/'tools/build_identity.py').read_text().split('digest = hashlib.sha256()')[0],'identity-inputs','exec'),ns)
digest=hashlib.sha256()
for f in sorted(set(ns['paths'])):digest.update(f.relative_to(root).as_posix().encode()+b'\0'+f.read_bytes()+b'\0')
assert identity=='stage10.0-src-'+digest.hexdigest()[:16]
assert identity.encode() in elf.read_bytes() and identity.encode() in binary.read_bytes()
assert 'SH_3DS_DEV_' not in (p/'build-game/flags').read_text()
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
symbols=subprocess.check_output([prefix+'nm','-n',str(elf)],text=True)
assert 'Game3ds_DevEnter' not in symbols and 'Game3ds_DevNewGame' not in symbols and 'Game3ds_DevCafePad' not in symbols
qualification=read(p/'reports/stage10-r3-runtime-qualification.json')
assert qualification['status']=='PASS' and qualification['normal_elf_sha256']==elfsha
assert qualification['foundation_tests']==26 and qualification['actual_cafe_exit_to_map2']
assert not qualification['hardware_accepted'] and qualification['memory_card_unchanged']
delivery=read(p/'reports/stage10-r3-http.json');published=read(p/'dev_server/published/manifest.json')
assert delivery['verified'] and delivery['sha256']==sha(binary) and delivery['size']==binary.stat().st_size
assert published['sha256']==sha(binary) and published['size']==binary.stat().st_size
run=read(p/'build/azahar/last-run.json')
assert run['build_sha256']==sha(binary) and run['build_identity']==identity
assert run['result']=='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'
launched=Path(run['launched'])
if os.name!='nt' and re.match(r'^[A-Za-z]:',run['launched']):
    launched=Path(subprocess.check_output(['wslpath','-u',run['launched']],text=True).strip())
normal=launched.parent/'stage4_status.txt'
status=dict(line.split('=',1) for line in normal.read_text().splitlines() if '=' in line)
assert status['build']==identity and status['first_failure']=='0' and status['boot_variant']=='NORMAL_NEW_GAME'
assert status['report_complete']=='1'
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
shutil.copy2(root/'docs/3ds-stage10-r3-handoff.md',candidate/'README.md')
record=dict(status='ПРОМЕЖУТОЧНЫЙ АППАРАТНЫЙ КАНДИДАТ; ПРОВЕРКА ПОЛЬЗОВАТЕЛЕМ ОЖИДАЕТСЯ',
    build=identity,binary=(candidate/binary.name).relative_to(root).as_posix(),sha256=sha(binary),
    bytes=binary.stat().st_size,elf_sha256=elfsha,archive=archive.relative_to(root).as_posix(),
    foundation_tests='26/26 PASS',runtime_qualification=qualification,delivery=delivery,
    previous_archives_preserved=accepted,hardware_accepted=False,stage10_complete=False,
    normal_gameplay_no_diagnostic_setup=True,source_identity_inputs=len(set(ns['paths'])),
    pending=['Аппаратная проверка R3','Общий feedback/fade на New 3DS','Существенное ускорение Cafe',
        'Полные Groaner/melee encounters и progression pickups','Достижение школы и сохранение'])
write(p/'reports/stage10-r3-candidate.json',record)
with zipfile.ZipFile(root/read(p/'reports/stage10-r2-freeze.json')['archive']) as z:previous=json.loads(z.read('manifest.json'))
paths={root/n for n in previous if (root/n).is_file() and not n.startswith(('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
paths.update(ns['paths'])
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',p/'build/audio',candidate,p/'reports/stage10-r3-ui'):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(f for f in (p/'reports').glob('stage10-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update(f for f in (root/'docs').glob('3ds-stage10-*.md'))
paths.update((p/'build/build_identity.h',p/'build-game/flags',p/'build-game/native_data.inc',
    p/'build-game/native_items.inc',p/'build-game/tmd_emit.inc',p/'build-game/map0_s01.native.ld',p/'build-game/map2_s00.native.ld',
    p/'reports/stage9-r6-accepted-freeze.json',p/'reports/stage10-r1a-freeze.json',p/'reports/stage10-r2-freeze.json',
    p/'reports/stage8-r2-pixel-index.json',normal))
for folder in ('stage10-dev-scene-3','stage10-dev-scene-5-menus','stage10-dev-scene-5-menus-no-map','stage10-dev-scene-2-exit'):
    paths.add(p/f'build/{folder}/manifest.json')
paths={f for f in paths if f.is_file()}
manifest={f.relative_to(root).as_posix():dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(paths)}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sorted(paths):z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for name,value in manifest.items():
        data=z.read(name);assert len(data)==value['bytes'] and hashlib.sha256(data).hexdigest()==value['sha256'],name
receipt=dict(status='PASS',build=identity,archive=archive.relative_to(root).as_posix(),archive_bytes=archive.stat().st_size,
    archive_sha256=sha(archive),manifest_files_verified=len(manifest),binary_sha256=sha(binary),elf_sha256=elfsha,
    hardware_accepted=False,stage10_complete=False)
write(p/'reports/stage10-r3-freeze.json',receipt)
print(json.dumps(receipt,indent=2,ensure_ascii=False))
