"""Record the user's real New 3DS acceptance without rewriting the snapshot."""
import hashlib, json, zipfile
from pathlib import Path
p = Path(__file__).resolve().parents[1]
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
binary = p/'build/hardware-stage7-native-wide/silenthill_game.3dsx'
archive = p/'baselines/stage7-native-wide-candidate.zip'
assert binary.stat().st_size == 900004
assert sha(binary) == '6a7155fba72e2598c23ebbd0242ef87d7934b4979f73f94158dbe526477b199d'
with zipfile.ZipFile(archive) as z:
    manifest = json.loads(z.read('manifest.json'))
    for name, expected in manifest.items():
        data = z.read(name)
        assert len(data) == expected['bytes']
        assert hashlib.sha256(data).hexdigest() == expected['sha256'], name
record = dict(status='HARDWARE ACCEPTED', date='2026-10-26',
    authority='User report: real New Nintendo 3DS',
    binary=str(binary.relative_to(p.parent)), bytes=binary.stat().st_size,
    sha256=sha(binary), archive_sha256=sha(archive), verified_members=len(manifest),
    accepted=['normal route to Cafe', 'native 400x240 world', 'pickup and original TMD',
              'bottom Status navigation/equipment', 'pistol acquisition and aiming',
              'save, full application exit, restart, load', 'progress beyond Cafe',
              'first flying-monster cutscene and flying gameplay enemy'],
    stage8_blocker='First flying-monster attack stops/crashes the game',
    immutable_snapshot=True)
out = p/'reports/stage7-accepted.json'
if out.exists():
    assert json.loads(out.read_text()) == record
else:
    out.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
