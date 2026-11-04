#!/usr/bin/env python3
"""Record the user's real New 3DS result without changing frozen artifacts."""
import hashlib, json, zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
binary = root / '3ds_port/build/hardware-stage6-cafe/silenthill_game.3dsx'
archive = root / '3ds_port/baselines/stage6-cafe-candidate.zip'
expected = 'a48506efab80c29ef57dbc55c2083a09ab69855f456ee544291cdc376d83b674'
assert binary.stat().st_size == 794936
assert hashlib.sha256(binary.read_bytes()).hexdigest() == expected
with zipfile.ZipFile(archive) as z:
    manifest = json.loads(z.read('manifest.json'))
    for name, entry in manifest.items():
        data = z.read(name)
        assert len(data) == entry['bytes']
        assert hashlib.sha256(data).hexdigest() == entry['sha256'], name
record = {
    'status': 'HARDWARE ACCEPTED',
    'authority': 'User report of real New Nintendo 3DS validation, 2026-10-25',
    'binary': binary.relative_to(root).as_posix(), 'bytes': 794936, 'sha256': expected,
    'source_archive': archive.relative_to(root).as_posix(),
    'source_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'verified_source_members': len(manifest),
    'route': 'normal boot/title/New Game/prologue/nightmare/knife fall/Cafe/full Cybil dialogue/free control',
    'gameplay_fps': '29-30', 'cybil_cutscene_fps': 'approximately 24; performance backlog',
    'stability': 'No progressive slowdown or instability reported',
}
(root / '3ds_port/reports/stage6-accepted.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
