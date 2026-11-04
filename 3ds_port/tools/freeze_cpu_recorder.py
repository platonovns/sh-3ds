"""Freeze a distinct recorder package; never alter an earlier R6 archive."""
import hashlib,json,shutil,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
q=read(p/'reports/stage10-cpu-recorder-qualification.json')
c=read(p/'reports/stage10-cpu-recorder-candidate.json')
h=read(p/'reports/stage10-cpu-recorder-http.json')
assert q['status']=='PASS' and q['build']==c['build'] and h['source_build']==c['build']
assert h['verified'] and q['sha256']==c['sha256']==h['sha256']
assert sha(p/'baselines/stage10-r6-cpu-audit.zip')=='32e4f726f9e7ae742fe70fa8a578911f8f7a0bf1db9d601309c4fee5e79a4660'
d=p/'build/hardware-stage10-cpu-recorder';archive=p/'baselines/stage10-cpu-recorder.zip'
assert not d.exists() and not archive.exists(),'Never overwrite a frozen package'
d.mkdir()
for name in ('silenthill_cpu_recorder.3dsx','silenthill_cpu_recorder.elf','recorder.map','manifest.json'):
    shutil.copy2(p/'build/stage10-cpu-recorder'/name,d/name)
assert sha(d/'silenthill_cpu_recorder.3dsx')==c['sha256']
overlay=['3ds_port/source/main_game.c','3ds_port/source/game_native.c',
    '3ds_port/source/game_profile.c','3ds_port/source/game_cpu_audit.c','3ds_port/source/game_cpu_recorder.c',
    '3ds_port/include/game_cpu_recorder.h','3ds_port/include/game_profile.h',
    '3ds_port/tests/game_cpu_recorder_test.c','3ds_port/tests/cpu_recorder_snapshot_test.c',
    '3ds_port/tools/build_stage10_cpu_recorder.py','3ds_port/tools/build_cpu_recorder_pica.py',
    '3ds_port/tools/test_stage10_cpu_recorder.py','3ds_port/tools/verify_cpu_recorder.py',
    '3ds_port/tools/verify_cpu_recorder_http.ps1','3ds_port/tools/freeze_cpu_recorder.py',
    '3ds_port/tools/run_azahar.ps1','3ds_port/tools/qualify_stage10_pica.ps1',
    'docs/3ds-stage10-cpu-recorder.md']
for name in overlay:
    target=d/'source-overlay'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,target)
shutil.copy2(p/'reports/CPU-RECORDER-HARDWARE-RU.md',d/'HARDWARE-RU.md')
for f in (p/'reports').glob('stage10-cpu-recorder-*'):
    target=d/'evidence'/f.name;target.parent.mkdir(exist_ok=True)
    if f.is_dir():shutil.copytree(f,target)
    elif f.suffix=='.json':shutil.copy2(f,target)
manifest=[dict(path=f.relative_to(d).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
    for f in sorted(d.rglob('*')) if f.is_file()]
(d/'files.json').write_text(json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sorted(d.rglob('*')):
        if f.is_file():z.write(f,f.relative_to(d).as_posix())
with zipfile.ZipFile(archive) as z:
    for row in manifest:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
receipt=dict(build=c['build'],variant=c['variant'],bytes=c['size'],sha256=c['sha256'],
    archive=str(archive.relative_to(root)),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
    verified_files=len(manifest),normal_production_unchanged=True,hardware_accepted=False)
(p/'reports/stage10-cpu-recorder-freeze.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
