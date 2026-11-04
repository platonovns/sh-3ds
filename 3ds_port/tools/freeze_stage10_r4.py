"""Freeze the qualified normal R4; never mark hardware acceptance or overwrite baselines."""
import hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def write(f,v):f.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
candidate=p/'build/hardware-stage10-r4';archive=p/'baselines/stage10-r4.zip'
assert not candidate.exists() and not archive.exists(),'Never overwrite a frozen candidate'
accepted=[]
for name in ('stage9-r6-accepted','stage10-r1a','stage10-r2','stage10-r3'):
    r=read(p/f'reports/{name}-freeze.json');assert sha(root/r['archive'])==r['archive_sha256']
    accepted.append(dict(name=name,archive_sha256=r['archive_sha256']))
elf=p/'silenthill_game.elf';binary=p/'silenthill_game.3dsx';elfsha=sha(elf)
identity=re.search(r'"(stage10[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
ns={'__file__':str(p/'tools/build_identity.py')}
exec(compile((p/'tools/build_identity.py').read_text().split('digest = hashlib.sha256()')[0],'identity-inputs','exec'),ns)
digest=hashlib.sha256()
for f in sorted(set(ns['paths'])):digest.update(f.relative_to(root).as_posix().encode()+b'\0'+f.read_bytes()+b'\0')
assert identity=='stage10.0-src-'+digest.hexdigest()[:16]
assert identity.encode() in elf.read_bytes() and identity.encode() in binary.read_bytes()
assert 'SH_3DS_DEV_' not in (p/'build-game/flags').read_text()
symbols=subprocess.check_output([os.environ['DEVKITARM']+'/bin/arm-none-eabi-nm','-n',str(elf)],text=True)
assert not any(n in symbols for n in ('Game3ds_DevEnter','Game3ds_DevNewGame','Game3ds_DevCafePad'))
q=read(p/'reports/stage10-r4-runtime-qualification.json')
assert q['status']=='PASS' and q['normal_elf_sha256']==elfsha and q['foundation_tests']==28
assert q['actual_cafe_window_combat_radio_exit_to_map2'] and q['memory_card_unchanged'] and not q['hardware_accepted']
delivery=read(p/'reports/stage10-r4-http.json');published=read(p/'dev_server/published/manifest.json')
assert delivery['verified'] and delivery['sha256']==sha(binary)==published['sha256']
assert delivery['size']==binary.stat().st_size==published['size']
run=read(p/'build/azahar/last-run.json');assert run['build_sha256']==sha(binary) and run['build_identity']==identity
assert run['result']=='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'
launched=Path(subprocess.check_output(['wslpath','-u',run['launched']],text=True).strip())
normal=launched.parent/'stage4_status.txt';s=dict(line.split('=',1) for line in normal.read_text().splitlines() if '=' in line)
assert s['build']==identity and s['first_failure']=='0' and s['boot_variant']=='NORMAL_NEW_GAME' and s['report_complete']=='1'
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
shutil.copy2(root/'docs/3ds-stage10-r4-handoff.md',candidate/'README.md')
record=dict(status='АППАРАТНЫЙ КАНДИДАТ; ПРИЁМКА ПОЛЬЗОВАТЕЛЕМ ОЖИДАЕТСЯ',build=identity,
    binary=(candidate/binary.name).relative_to(root).as_posix(),sha256=sha(binary),bytes=binary.stat().st_size,
    elf_sha256=elfsha,archive=archive.relative_to(root).as_posix(),runtime_qualification=q,delivery=delivery,
    previous_archives_preserved=accepted,hardware_accepted=False,stage10_complete=False,
    normal_gameplay_no_diagnostic_setup=True,pending=['Аппаратная проверка R4 и reload','Fade/loading на New 3DS',
        'Modern/Hybrid и настройки','Groaner/melee и дальнейшие предметы','Дорога к школе и сохранение','Производительность активного Cafe'])
write(p/'reports/stage10-r4-candidate.json',record)
with zipfile.ZipFile(p/'baselines/stage10-r3.zip') as z:prior=json.loads(z.read('manifest.json'))
paths={root/n for n in prior if (root/n).is_file() and not n.startswith(('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
paths.update(ns['paths'])
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',candidate,p/'reports/stage10-r4-ui',p/'reports/stage10-r4-cafe',p/'reports/stage10-r4-hardware'):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(f for f in (p/'reports').glob('stage10-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update(f for f in (root/'docs').glob('3ds-stage10-*.md'))
paths.update((p/'build/build_identity.h',p/'build-game/flags',normal,p/'reports/stage8-r2-pixel-index.json'))
for folder,extras in (('stage10-dev-scene-3',('diagnostic.elf',)),('stage10-dev-scene-5-menus',('diagnostic.3dsx',)),('stage10-dev-scene-6-exit',('diagnostic.3dsx',)),('stage10-r4-window-cpu',('diagnostic.elf',))):
    paths.add(p/f'build/{folder}/manifest.json')
    paths.update(p/f'build/{folder}/{name}' for name in extras)
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
write(p/'reports/stage10-r4-freeze.json',receipt);print(json.dumps(receipt,indent=2,ensure_ascii=False))
