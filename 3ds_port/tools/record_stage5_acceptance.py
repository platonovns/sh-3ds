#!/usr/bin/env python3
"""Record user-supplied hardware acceptance without mutating frozen artifacts."""
from pathlib import Path
import hashlib, json, zipfile

p = Path(__file__).resolve().parents[1]
binary = p/'build/hardware-stage5-edge/silenthill_game.3dsx'
archive = p/'baselines/stage5-edge-candidate.zip'
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
expected = '482db74e5b541ea70de80f8e7a58005a511fe6b697ac4c18e9f7c922e78b3b0b'
assert sha(binary) == expected and binary.stat().st_size == 667868
with zipfile.ZipFile(archive) as z:
    manifest = json.loads(z.read('manifest.json'))
    for name, item in manifest.items():
        data = z.read(name)
        assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], name
report = {'status':'HARDWARE ACCEPTED', 'date':'2026-10-25',
    'authority':'User report: real New Nintendo 3DS validation',
    'binary':binary.relative_to(p.parent).as_posix(), 'bytes':binary.stat().st_size,
    'sha256':expected, 'archive':archive.relative_to(p.parent).as_posix(),
    'archive_sha256':sha(archive), 'verified_archive_members':len(manifest),
    'confirmed':['original boot/title/New Game','map0_s00 stable', 'physical controls',
        'in-engine cutscenes','no progressive slowdown','no perceptible garage I/O stalls',
        'major Stage 5 renderer regressions no longer observed','long gameplay stable'],
    'accepted_limitations':['occasional minor visual imperfections'],
    'policy':'Frozen Stage 5 baseline. Reopen cosmetic issues only if later blocking.'}
out = p/'reports/stage5-accepted.json'
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
