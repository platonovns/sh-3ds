"""Create a standalone Stage 10 closure backup without rebuilding or relabeling."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
NAME = 'stage10-hardware-accepted-20261028'
DEST = PORT / 'build' / 'hardware-stage10-accepted-20261028'
ARCHIVE = PORT / 'baselines' / (NAME + '.zip')
RECEIPT = PORT / 'reports' / (NAME + '-freeze.json')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def copy(source, target):
    target = DEST / target
    check(source.is_file() and not target.exists(), f'Missing source or duplicate target: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    check(sha(source) == sha(target), f'Copy mismatch: {target}')


def main():
    check(not any(p.exists() for p in (DEST, ARCHIVE, RECEIPT)), 'Never overwrite a frozen package')
    acceptance = read(PORT / 'reports/stage10-hardware-accepted.json')
    check(acceptance['closed'] and acceptance['status'] == 'HARDWARE_ACCEPTED', 'Stage not closed')
    published = read(PORT / 'dev_server/published/manifest.json')
    recorder = read(PORT / 'build/hardware-stage10-cpu-recorder/manifest.json')
    normal = read(PORT / 'build/hardware-stage10-r6-cpu-audit/candidate.json')
    delivery = read(PORT / 'reports/stage10-cpu-recorder-http.json')
    check(delivery['verified'] and delivery['sha256'] == published['sha256'] == recorder['sha256'],
          'HTTP/current recorder identity mismatch')
    check(delivery['size'] == published['size'] == recorder['size'], 'HTTP/current size mismatch')
    check(delivery['source_build'] == recorder['build'], 'HTTP source ID mismatch')
    published_binary = PORT / 'dev_server/published' / published['file']
    check(sha(published_binary) == recorder['sha256'], 'Published binary changed')
    archives = {
        'stage10-r5.zip': acceptance['functional_baseline_archive_sha256'],
        'stage10-r6.zip': '0c4143c4cfa4c252007953f868c8e93d7d9c2d3c0158f6051abf18547bb26119',
        'stage10-r6-cpu-audit.zip': '32e4f726f9e7ae742fe70fa8a578911f8f7a0bf1db9d601309c4fee5e79a4660',
        'stage10-cpu-recorder.zip': '596990f697a0859e1f36af56e75ccd53c44e2225b116ed19d313445fdb84a780',
    }
    for name, expected in archives.items():
        check(sha(PORT / 'baselines' / name) == expected, f'Frozen dependency changed: {name}')
    golden = ROOT / 'sh1_data/memcard.mcr'
    golden_sha = '69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
    check(sha(golden) == golden_sha, 'Golden card changed')
    DEST.mkdir()
    copy(published_binary, 'current-published/silenthill_game.3dsx')
    copy(PORT / 'dev_server/published/manifest.json', 'current-published/http-manifest.json')
    for name in ('silenthill_cpu_recorder.elf', 'recorder.map', 'manifest.json'):
        copy(PORT / 'build/hardware-stage10-cpu-recorder' / name, 'current-published/' + name)
    check(sha(DEST / 'current-published/silenthill_cpu_recorder.elf') == recorder['elf_sha256'], 'Recorder ELF mismatch')
    for source, target, binary_hash, elf_hash in (
        (PORT / 'build/hardware-stage10-r6-cpu-audit', 'normal-r6', normal['sha256'], normal['elf_sha256']),
        (PORT / 'build/hardware-stage10-r5', 'functional-r5', acceptance['functional_baseline_sha256'],
         read(PORT / 'reports/stage10-r5-hardware-accepted.json')['elf_sha256']),
    ):
        check(sha(source / 'silenthill_game.3dsx') == binary_hash, f'{target} binary mismatch')
        check(sha(source / 'silenthill_game.elf') == elf_hash, f'{target} ELF mismatch')
        for f in sorted(source.iterdir()):
            if f.is_file() and f.suffix in ('.3dsx', '.elf', '.map', '.smdh', '.json'):
                copy(f, target + '/' + f.name)
    for name in archives:
        copy(PORT / 'baselines' / name, 'frozen-source-packages/' + name)
    evidence = PORT / 'reports/stage10-r6-cpu-hardware-20261028'
    for f in sorted(evidence.iterdir()):
        if f.is_file():
            copy(f, 'hardware-cpu-evidence/' + f.name)
    for name in ('stage10-hardware-accepted.json', 'stage10-r5-hardware-accepted.json',
                 'stage10-r6-freeze.json', 'stage10-r6-cpu-candidate.json',
                 'stage10-cpu-recorder-freeze.json', 'stage10-cpu-recorder-http.json'):
        copy(PORT / 'reports' / name, 'receipts/' + name)
    for name in ('3ds-stage10-accepted.md', '3ds-stage10-freeze.md',
                 '3ds-stage10-r6-cpu-hardware.md', '3ds-stage10-cpu-recorder.md'):
        copy(ROOT / 'docs' / name, 'documentation/' + name)
    for name in ('freeze_stage10_accepted.py', 'analyze_stage10_cpu_windows.py'):
        copy(PORT / 'tools' / name, 'tools/' + name)
    for name in ('manifest.json', 'config.json', 'run_stage1a.sh'):
        copy(ROOT.parent / '.toolchain' / name, 'toolchain-provenance/' + name)
    (DEST / 'RESTORE.md').write_text('''# Stage 10 accepted milestone: standalone recovery package

Frozen on 2026-10-28 without recompilation. Final stage acceptance is the user's
decision in receipts/stage10-hardware-accepted.json. Historical candidate flags
inside older packages retain their original values.

## Ready-to-use binaries

- current-published/silenthill_game.3dsx: exact currently published CPU recorder
  (CPU_AUDIT_RECORDER_ONLY), source stage10.0-cpurec-src-a5ed13f76dac9640.
- normal-r6/silenthill_game.3dsx: ordinary R6 without the recording control,
  source stage10.0-src-ca390b6b8b45e70c.
- functional-r5/silenthill_game.3dsx: preserved hardware-good complete route
  baseline, source stage10.0-src-f470a7ecb962de17.

Each variant has its exact ELF/map. Choose the intended existing binary; retain
its original identity. No rebuild is needed to run the archived versions.
For HTTP restoration use the project's dev_server/publish.ps1 -Source with the
chosen binary and its original source build ID via -Build; verify HTTP delivery.
Existing external game data and a compatible installed launcher remain required.

## Exact source package chain

The nested ZIPs below are byte-identical to their prior frozen versions; all
dependencies are inside this backup. Use a separate recovery directory.

1. Extract frozen-source-packages/stage10-r6.zip to the repository root layout.
2. Extract stage10-r6-cpu-audit.zip separately. Overlay its source-overlay/
   contents onto that root to recover the ordinary R6 CPU-audit sources.
3. Extract stage10-cpu-recorder.zip separately. Overlay its source-overlay/
   contents on the same root to recover the CPU recorder sources/tools.
4. The accepted R5 is independently preserved in stage10-r5.zip, in repository
   root layout. Restore it separately when choosing that baseline.

The pinned SDK/toolchain provenance is in toolchain-provenance/. SDK binaries,
the external game BIN/CUE and user memory cards are not part of this archive.
Build instructions and historical evidence are retained inside the source ZIPs.
The frozen binaries are the identity reference; bit-identical future rebuilds
are not asserted. Current working-tree files are not substituted for historical
source snapshots. Hardware CPU windows are separate from emulator evidence.

## Verification

files.json lists SHA-256 and size for every payload file. Check all entries after
extraction. The outer ZIP SHA-256 is recorded in the adjacent .sha256 file and
the separate project freeze receipt. Do not overwrite this archive or older
baselines. A future freeze must have a new name.
''', encoding='utf-8')
    inventory = [dict(path=f.relative_to(DEST).as_posix(), bytes=f.stat().st_size, sha256=sha(f))
                 for f in sorted(DEST.rglob('*')) if f.is_file()]
    write(DEST / 'files.json', inventory)
    print(f'Payload prepared: {len(inventory)} files; creating immutable ZIP.', flush=True)
    with zipfile.ZipFile(ARCHIVE, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(DEST.rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(DEST).as_posix(),
                        compress_type=zipfile.ZIP_STORED if f.suffix == '.zip' else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(ARCHIVE) as z:
        check(len(z.namelist()) == len(inventory) + 1, 'ZIP file count mismatch')
        check(z.read('files.json') == (DEST / 'files.json').read_bytes(), 'ZIP inventory mismatch')
        for row in inventory:
            info = z.getinfo(row['path'])
            with z.open(info) as f:
                check(info.file_size == row['bytes'] and
                      hashlib.file_digest(f, 'sha256').hexdigest() == row['sha256'],
                      f'ZIP payload mismatch: {row["path"]}')
    check(sha(golden) == golden_sha, 'Golden card changed during freeze')
    archive_sha = sha(ARCHIVE)
    receipt = dict(status='PASS', stage_status='HARDWARE_ACCEPTED', frozen_on='2026-10-28',
                   archive=ARCHIVE.relative_to(ROOT).as_posix(), archive_bytes=ARCHIVE.stat().st_size,
                   archive_sha256=archive_sha, verified_payload_files=len(inventory),
                   current_published_build=recorder['build'], current_published_variant=recorder['variant'],
                   current_published_sha256=recorder['sha256'], included_frozen_packages=archives,
                   source_dependencies_included=True, historical_archives_preserved=True,
                   game_rebuilt=False, golden_memory_card_unchanged=True,
                   recovery_directory=DEST.relative_to(ROOT).as_posix(), http_verification=delivery)
    with RECEIPT.open('x', encoding='utf-8') as f:
        f.write(json.dumps(receipt, indent=2) + '\n')
    with ARCHIVE.with_suffix('.zip.sha256').open('x', encoding='ascii') as f:
        f.write(archive_sha + '  ' + ARCHIVE.name + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
