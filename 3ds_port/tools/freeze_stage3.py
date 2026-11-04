#!/usr/bin/env python3
"""Preserve the hardware accepted inputs and binaries, without any game data."""
from pathlib import Path
import hashlib
import json
import zipfile

port = Path(__file__).resolve().parent.parent
root = port.parent
archive = port / 'baselines/stage3-accepted.zip'
archive.parent.mkdir(exist_ok=True)
assert not archive.exists(), 'Accepted baseline must never be overwritten'
paths = []
for folder in ['source', 'include', 'shaders', 'patches', 'tools', 'tests', 'reports']:
    paths += [p for p in (port / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
              and 'stage4' not in p.name and p.name != 'freeze_stage3.py']
paths += [port / p for p in ['Makefile', 'engine_sources.mk', 'silenthill_3ds.3dsx',
                            'silenthill_3ds.elf', 'silenthill_3ds.smdh', 'silenthill_3ds.map']]
paths += [root / p for p in ['docs/3ds-port.md', 'pc_port/include/psx_memory.h',
                            'pc_port/src/psx_memory.c', 'include/bodyprog/anim.h',
                            'include/bodyprog/formats/tmd.h']]
manifest = {str(p.relative_to(root)): {'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(paths):
        z.write(p, str(p.relative_to(root)))
    z.writestr('manifest.json', json.dumps(manifest, indent=2))
report = {'status': 'HARDWARE ACCEPTED on New Nintendo 3DS, user report 2026-10-24',
          'archive': str(archive.relative_to(root)), 'bytes': archive.stat().st_size,
          'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': manifest}
(port / 'reports/stage3-accepted.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))
