"""Freeze the exact hardware-checked B, with source/test/evidence hashes; no rebuild."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from stage11a_baseline import verify as verify_stage10
from analyze_stage11a_cpu_hardware import assess

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
REPORT = PORT / 'reports/stage11a-cpu-freeze-candidate.json'
ARCHIVE = PORT / 'baselines/stage11a-cpu-freeze-candidate-8c51d74ee1feb7e0.zip'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def local(name):
    return Path(name[5].upper() + ':/' + name[7:]) if name.startswith('/mnt/') else Path(name)


def check_inputs():
    verify_stage10()
    assessment = assess()
    saved = PORT / 'reports/stage11a-cpu-hardware-019-022/assessment.json'
    assert assessment == read(saved), 'Hardware assessment changed: regenerate and review'
    files = set()
    previous = read(PORT / 'reports/stage11a-cpu-package.json')
    prior = ROOT / previous['archive']
    assert sha(prior) == previous['sha256'] == '3aaae2158e42c5055dd6ea72792a60c0663e38c6c89cdea6ff98ca5deae21c30'
    files.add(prior)
    manifests = {}
    for label in ('A', 'B'):
        folder = PORT / ('build/stage11a-cpu-' + label)
        manifest_path = folder / 'manifest.json'
        manifest = read(manifest_path)
        binary = folder / ('silenthill_stage11a_cpu_' + label + '.3dsx')
        elf = binary.with_suffix('.elf')
        assert sha(binary) == manifest['sha256'] and binary.stat().st_size == manifest['size']
        assert sha(elf) == manifest['elf_sha256'] and manifest['build'].encode() in binary.read_bytes()
        assert manifest['spu_affinity'] == (2 if label == 'B' else -2)
        assert manifest['silent_candidate_default'] == 1
        assert all(sha(ROOT / p) == h for p, h in manifest['source_provenance']['sources'].items())
        assert all(sha(local(p)) == h for p, h in manifest['source_provenance']['base_objects'].items())
        files.update((manifest_path, binary, elf, folder / 'symbols.txt', folder / 'tracefix.map'))
        files.update(folder.glob('*.o'))
        if label == 'B':
            files.update(ROOT / p for p in manifest['source_provenance']['sources'])
        manifests[label] = manifest
    b = manifests['B']
    assert b['build'] == 'stage11a-cpu-B-src-8c51d74ee1feb7e0'
    assert b['sha256'] == 'af896f46797e8df7f71188f3ef9faed60364176d69029569a8ff84b4f02c1690'
    a_dir, b_dir = (PORT / ('build/stage11a-cpu-' + label) for label in ('A', 'B'))
    different = [p.name for p in sorted(a_dir.glob('*.o')) if p.read_bytes() != (b_dir / p.name).read_bytes()]
    assert different == ['game_audio_ndsp.o', 'main_game.o']
    validation_path = PORT / 'reports/stage11a-cpu-validation.json'
    validation = read(validation_path)
    for name, expected in validation['checks'].items():
        assert sha(PORT / 'reports' / name) == expected, 'Prior proof changed: ' + name
        files.add(PORT / 'reports' / name)
    regression = read(PORT / 'reports/stage11a-cpu-regression.json')
    assert len(regression['cases']) == 17 and all(c['status'] == 'PASS' for c in regression['cases'])
    assert regression['elf_sha256'] == manifests['A']['elf_sha256'] and regression['golden_card_unchanged']
    for name, expected in (
            ('silenthill_game.3dsx', '43462215152cf6405aa0437ab4bbee6fd0fe27cc2ee1c339dfa4cb4f3cf42bd6'),
            ('silenthill_game.elf', '8c41fc2a3281f71bb3583b058c7d56ce2e3e6ae59667c4a217262b96807cd981')):
        assert sha(PORT / name) == expected, 'Normal frozen R6 changed'
    http_path = PORT / 'reports/stage11a-cpu-http-current.json'
    http = read(http_path)
    assert http['default'] == 'B' and all(c['verified'] for c in http['candidates'])
    assert http['candidates'][1]['manifest']['sha256'] == b['sha256']
    files.update((validation_path, http_path, PORT / 'reports/stage11a-cpu-package.json',
                  PORT / 'Makefile.stage11a', Path(__file__),
                  PORT / 'tools/analyze_stage11a_cpu_hardware.py',
                  PORT / 'tools/analyze_stage11a_cpu.py', PORT / 'tools/analyze_stage11a_tracefix.py',
                  PORT / 'tools/analyze_stage11a_lifetime.py', PORT / 'tools/select_stage11a_cpu_build.ps1',
                  PORT / 'tools/publish_stage11a_cpu_variants.py',
                  ROOT / 'docs/3ds-stage11a-freeze-candidate.md', ROOT / 'docs/3ds-stage11a-handoff.md'))
    files.update(p for p in (PORT / 'reports/stage11a-cpu-hardware-019-022').rglob('*') if p.is_file())
    files.update(p for p in (PORT / 'reports/stage11a-cpu-regression').glob('*') if p.is_file())
    return files, manifests, assessment, previous


def verify_archive():
    record = read(REPORT)
    assert record['archive'] == ARCHIVE.relative_to(ROOT).as_posix()
    assert sha(ARCHIVE) == record['archive_sha256'] and ARCHIVE.stat().st_size == record['archive_size']
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        inventory = json.loads(z.read('freeze-inventory.json'))
        assert len(inventory) == record['files']
        for name, item in inventory.items():
            raw = z.read(name)
            assert len(raw) == item['size'] and hashlib.sha256(raw).hexdigest() == item['sha256'], name
            assert sha(ROOT / name) == item['sha256'], 'Working file diverged from candidate: ' + name
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    files, manifests, assessment, previous = check_inputs()
    if args.verify:
        record = verify_archive()
        print(json.dumps(dict(status='PASS', build=record['build'], files=record['files'], stage11a_accepted=False)))
        return
    assert not REPORT.exists() and not ARCHIVE.exists(), 'Immutable freeze already exists: use --verify'
    inventory = {p.relative_to(ROOT).as_posix(): dict(size=p.stat().st_size, sha256=sha(p)) for p in sorted(files)}
    b = manifests['B']
    record = dict(status='CORE2_DEFAULT_FREEZE_CANDIDATE_FINAL_HARDWARE_SMOKE_PENDING',
        date='2026-10-28', build=b['build'], sha256=b['sha256'], size=b['size'], elf_sha256=b['elf_sha256'],
        source_manifest='3ds_port/build/stage11a-cpu-B/manifest.json',
        runtime_binary_changed_since_hardware_AB=False, source_provenance_verified=True,
        default_build_entry='3ds_port/Makefile.stage11a', default_variant='B', spu_core=2,
        core2_school_hardware_verified=True, hardware_writer_confirmed=True, F1_lifetime_school_verified=True,
        full_stage11a_accepted=False, stage11a_accepted=False, stage11b_started=False,
        hardware_assessment='3ds_port/reports/stage11a-cpu-hardware-019-022/assessment.json',
        prior_local_proof='3ds_port/reports/stage11a-cpu-validation.json',
        prior_source_archive=previous['archive'], prior_source_archive_sha256=previous['sha256'],
        stage10_preserved=True, golden_card_sha256=sha(ROOT / 'sh1_data/memcard.mcr'),
        pending=['B school warm -> Title -> New Game/MAP0 stability',
                 'B pause/HOME/suspend/resume and subsequent SFX/KeyOn; normal/quick reload confirmation',
                 'Final user confirmation of no new visual/control/save regressions'],
        document='docs/3ds-stage11a-freeze-candidate.md',
        archive=ARCHIVE.relative_to(ROOT).as_posix(), files=len(inventory))
    with zipfile.ZipFile(ARCHIVE, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(files):
            z.write(p, p.relative_to(ROOT).as_posix())
        z.writestr('freeze-inventory.json', json.dumps(inventory, indent=2) + '\n')
        z.writestr('freeze-decision.json', json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    record.update(archive_sha256=sha(ARCHIVE), archive_size=ARCHIVE.stat().st_size)
    REPORT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verify_archive()
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
