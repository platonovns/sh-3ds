"""Verify immutable Stage 10 evidence and capture the dirty Stage 11A starting tree.

No checkout/reset, save writes, build or publication. Run once before code edits.
"""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
DEST = PORT / 'build/stage11a-baseline'
RECEIPT = PORT / 'reports/stage11a-baseline.json'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def verify():
    frozen = read(PORT / 'reports/stage10-hardware-accepted-20261028-freeze.json')
    archives = {**frozen['included_frozen_packages'],
                Path(frozen['archive']).name: frozen['archive_sha256']}
    for name, expected in archives.items():
        assert sha(PORT / 'baselines' / name) == expected, f'Frozen archive changed: {name}'
    recorder = PORT / 'build/hardware-stage10-cpu-recorder'
    manifest = read(recorder / 'manifest.json')
    for name, expected in [('silenthill_cpu_recorder.3dsx', manifest['sha256']),
                           ('silenthill_cpu_recorder.elf', manifest['elf_sha256'])]:
        assert sha(recorder / name) == expected, f'Frozen recorder changed: {name}'
    evidence = PORT / 'reports/stage10-r6-cpu-hardware-20261028'
    for sample in read(evidence / 'samples.json'):
        assert sha(evidence / sample['file']) == sample['sha256']
    card = ROOT / 'sh1_data/memcard.mcr'
    assert sha(card) == '69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
    return archives, manifest, sha(card)


def main():
    archives, recorder, card = verify()
    if RECEIPT.exists():
        previous = read(RECEIPT)
        assert sha(ROOT / previous['source_snapshot']) == previous['source_snapshot_sha256']
        print('PASS: frozen Stage 10 archives, recorder, raw hardware logs, card and starting snapshot unchanged')
        return
    assert not DEST.exists(), 'Do not overwrite a partial baseline capture'
    DEST.mkdir()
    # Use the existing source dependency list WITHOUT executing its header writer.
    script = PORT / 'tools/build_identity.py'
    ns = {'__file__': str(script)}
    exec(compile(script.read_text().split('digest = hashlib.sha256()')[0], str(script), 'exec'), ns)
    paths = set(ns['paths'])
    paths.update(p for directory in ('tools', 'tests') for p in (PORT / directory).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts)
    paths.update(p for p in (PORT / 'build/audio').iterdir() if p.is_file())
    paths.update((PORT / 'build-game/flags', PORT / 'build/build_identity.h', ROOT / 'AGENTS.md'))
    inventory = [dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
                 for p in sorted(paths)]
    (DEST / 'files.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (DEST / 'git-status.txt').write_bytes(git('status', '--porcelain=v1', '-uall'))
    (DEST / 'tracked-changes.patch').write_bytes(git('diff', '--binary', 'HEAD'))
    snapshot = DEST / 'starting-source.zip'
    with zipfile.ZipFile(snapshot, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in inventory:
            archive.write(ROOT / row['path'], row['path'])
        for name in ('files.json', 'git-status.txt', 'tracked-changes.patch'):
            archive.write(DEST / name, 'capture/' + name)
    with zipfile.ZipFile(snapshot) as archive:
        for row in inventory:
            assert hashlib.sha256(archive.read(row['path'])).hexdigest() == row['sha256']
    result = dict(status='PASS', stage='11A.0', date='2026-10-28',
                  branch=git('branch', '--show-current').decode().strip(),
                  head=git('rev-parse', 'HEAD').decode().strip(), parent_branch='3ds-port',
                  dirty_start=True, git_commit_alone_is_insufficient=True,
                  frozen_archives=archives, hardware_measurement_baseline=recorder,
                  source_snapshot=snapshot.relative_to(ROOT).as_posix(),
                  source_snapshot_sha256=sha(snapshot), files=len(inventory),
                  source_inventory=(DEST / 'files.json').relative_to(ROOT).as_posix(),
                  golden_card_sha256=card, golden_card_written=False,
                  stage10_frozen=True, performance_optimizations=0,
                  hardware_accepted=False)
    with RECEIPT.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
