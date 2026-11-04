#!/usr/bin/env python3
"""Capture the exact user-accepted Level A artifact and current native sources."""
from pathlib import Path
import hashlib
import json
import zipfile

port = Path(__file__).resolve().parents[1]
root = port.parent
expected = 'a600285eb2748a33fa2def95b85c77c3091ed53c32d00aa77334fe5e9f090db4'
candidate = port / 'build/hardware-stage42-level-a'
assert hashlib.sha256((candidate/'silenthill_game.3dsx').read_bytes()).hexdigest() == expected
archive = port/'baselines/stage4-level-a-accepted.zip'
assert not archive.exists(), 'Never overwrite an accepted baseline'
paths = []
for base in ('3ds_port/source','3ds_port/include','3ds_port/shaders','3ds_port/patches',
             'include','src/bodyprog','src/screens','pc_port/include'):
    paths += [p for p in (root/base).rglob('*') if p.is_file()]
paths += [root/p for p in ('3ds_port/Makefile','3ds_port/Makefile.game','3ds_port/engine_sources.mk',
    'src/main/main.c','src/main/fsqueue_1.c','src/main/fsqueue_2.c','src/main/fsqueue_3.c',
    'src/main/fileinfo.c','src/main/fsmem.c','pc_port/src/psx_memory.c',
    'docs/3ds-port.md','docs/3ds-stage4-audit.md','docs/3ds-stage42-handoff.md')]
paths += list(candidate.glob('silenthill_game.*'))
paths += [p for p in (port/'reports/azahar-stage42-level-a').iterdir() if p.is_file()]
manifest = {p.relative_to(root).as_posix(): {'bytes':p.stat().st_size,
    'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(set(paths))}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(paths)): z.write(p,p.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
report = {'status':'STAGE 4 LEVEL A HARDWARE ACCEPTED', 'platform':'real New Nintendo 3DS',
    'authority':'user hardware report, 2026-10-24', 'bytes':261944,'sha256':expected,
    'build':'stage4.2-src-240eda36c9a0f1a2','archive':archive.relative_to(root).as_posix(),
    'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
    'observed':['original boot and warning screens','KONAMI/KCET',
        'original memory card not inserted warning','unsupported intro FMV skipped',
        'original title rendered correctly','START and OPTION visible',
        'real menu input and selection cursor movement work',
        'no blocking visual/runtime issue before title'],
    'level_b':'NOT ACCEPTED', 'files':manifest}
(port/'reports/stage4-level-a-accepted.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
