#!/usr/bin/env python3
"""Freeze the exact user-accepted Stage 4.1 build and implementation."""
from pathlib import Path
import hashlib
import json
import zipfile

port = Path(__file__).resolve().parents[1]
root = port.parent
expected = 'd99dde9f695ee8595aa1e57d9a4ac0d9c169344f5473e56f353045d5476d9092'
assert hashlib.sha256((port / 'silenthill_3ds.3dsx').read_bytes()).hexdigest() == expected
archive = port / 'baselines/stage4.1-accepted.zip'
assert not archive.exists(), 'Never overwrite an accepted baseline'
paths = []
for directory in ('source', 'include', 'shaders', 'patches', 'tests', 'reports', 'tools'):
    paths += [p for p in (port / directory).rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.name != 'freeze_stage41.py']
paths += [port / p for p in ('Makefile', 'engine_sources.mk', 'silenthill_3ds.3dsx',
                             'silenthill_3ds.elf', 'silenthill_3ds.map', 'silenthill_3ds.smdh')]
paths += [root / p for p in ('src/main/fsqueue_1.c', 'src/main/fsqueue_2.c', 'src/main/fsqueue_3.c',
                             'src/main/fileinfo.c', 'pc_port/src/psx_memory.c', 'pc_port/include/psx_memory.h',
                             'include/bodyprog/anim.h', 'include/bodyprog/formats/tmd.h',
                             'docs/3ds-port.md', 'docs/3ds-stage4-audit.md')]
manifest = {p.relative_to(root).as_posix(): {'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(paths):
        z.write(p, p.relative_to(root).as_posix())
    z.writestr('manifest.json', json.dumps(manifest, indent=2))
report = {'status': 'HARDWARE ACCEPTED on real New Nintendo 3DS, user report 2026-10-24',
          'observed': {'checkpoint': 'FS_DONE', 'files': 2, 'reads': 2, 'uploads': 4,
                       'ticks': 12, 'vram_crc': 'B6E4F832', 'first_failure': 0,
                       'pica': ['PASS', 'PASS'], 'orientation': 'correct, Japanese readable',
                       'visible_regressions': 'none observed'},
          'build_sha256': expected, 'archive': archive.relative_to(root).as_posix(),
          'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': manifest}
(port / 'reports/stage4.1-accepted.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k != 'files'}, indent=2))
