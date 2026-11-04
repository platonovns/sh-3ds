"""Verify and preserve initial instrumentation evidence, NOT a Stage 11A freeze."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from stage11a_baseline import verify

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    verify()
    control = PORT / 'build/stage11a-control-profile'
    candidate = read(control / 'manifest.json')
    assert sha(control / 'silenthill_stage11a_control.3dsx') == candidate['sha256']
    assert sha(control / 'silenthill_stage11a_control.elf') == candidate['elf_sha256']
    for name, expected in candidate['provenance']['sources'].items():
        assert sha(ROOT / name) == expected, f'Source changed since link: {name}'
    baseline = read(PORT / 'reports/stage11a-baseline.json')
    changed = []
    for row in read(ROOT / baseline['source_inventory']):
        if sha(ROOT / row['path']) != row['sha256']:
            changed.append(row['path'])
    assert set(changed) == {'3ds_port/source/main_game.c', '3ds_port/source/game_audio_ndsp.c',
                            '3ds_port/source/game_profile.c', '3ds_port/source/game_cpu_recorder.c',
                            '3ds_port/tools/run_azahar.ps1'}, changed
    oracle = read(PORT / 'reports/stage11a-spu-oracle.json')
    assert oracle['status'] == 'PASS'
    for name, expected in oracle['inputs'].items():
        assert sha(ROOT / name) == expected, f'Stale test: {name}'
    arm = read(PORT / 'reports/stage11a-arm.json')
    assert arm['status'] == 'PASS' and arm['elf_sha256'] == candidate['elf_sha256']
    assert arm['post_submit_queue_depths'] == [1, 2, 3, 4]
    assert read(PORT / 'reports/stage11a-analysis-tests.json')['status'] == 'PASS'
    delivery = read(PORT / 'reports/stage11a-control-http.json')
    assert delivery['verified'] and delivery['sha256'] == candidate['sha256']
    assert delivery['source_build'] == candidate['build'] and delivery['size'] == candidate['size']
    run = read(PORT / 'build/azahar/last-run.json')
    assert run['result'] == 'TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'
    assert run['build_sha256'] == candidate['sha256'] and run['build_identity'] == candidate['build']
    title = Path(run['launched']).parent / 'stage4_status.txt'
    # This packager is run on Windows, beside the emulator and HTTP verifier.
    data = dict(line.split('=', 1) for line in title.read_text().splitlines() if '=' in line)
    assert data['build'] == candidate['build'] and data['checkpoint'] == 'TITLE_FRAME_SUBMITTED'
    assert data['first_failure'] == '0' and data['report_complete'] == '1'
    assert data['cpu_record_errno'] == '0'
    title_dest = PORT / 'reports/stage11a-control-title'
    title_dest.mkdir(exist_ok=True)
    shutil.copy2(title, title_dest / 'status.txt')
    (title_dest / 'run.json').write_text(json.dumps(run, indent=2) + '\n')
    assert sha(ROOT / 'sh1_data/memcard.mcr') == baseline['golden_card_sha256']
    result = dict(status='READY_FOR_INITIAL_HARDWARE_PROFILE', stage='11A.0', build=candidate['build'],
                  sha256=candidate['sha256'], size=candidate['size'], elf_sha256=candidate['elf_sha256'],
                  branch=baseline['branch'], inherited_files_changed=changed,
                  stage10_archives_verified=True, normal_objects_unchanged=candidate['normal_objects_unchanged'],
                  golden_card_unchanged=True, automated_checks=['256 byte-exact SPU state/PCM checkpoints',
                      'ASan PCM oracle', 'ASan/UBSan window/recorder checks', 'nine linked ARM retail SFX',
                      'linked ARM NDSP pause/sleep/format/queue/shutdown', 'synthetic A/B analyzer', 'Azahar Boot/Title'],
                  hardware_measurements_after=None, hardware_audio_listening_pending=True,
                  optimizations_adopted=[], core2_experiment_started=False, core3_production_job=None,
                  static_memory_delta_from_stage10_recorder=dict(text=5904, data=0, bss=7000),
                  new_linear_allocations=0, new_vram_allocations=0, runtime_heap_delta_unmeasured=True,
                  stage11a_accepted=False, stage11a_frozen=False, delivery=delivery,
                  next_gate='Real New 3DS SPU profile, matched scenes A-E; no affinity change before algorithm A/B')
    receipt = PORT / 'reports/stage11a-0-candidate.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    name = 'stage11a-0-control-profile-' + candidate['build'].rsplit('-', 1)[1]
    archive = PORT / 'baselines' / (name + '.zip')
    assert not archive.exists(), 'Never overwrite a candidate evidence package'
    paths = {ROOT / f for f in changed}
    paths.update(PORT / 'source' / f for f in ('stage11a_perf.c',))
    paths.add(PORT / 'include/stage11a_perf.h')
    paths.update(f for f in (PORT / 'tools').glob('*stage11a*') if f.is_file())
    paths.update(f for f in (PORT / 'tests').glob('stage11a*') if f.is_file())
    paths.update(f for f in (PORT / 'reports').glob('stage11a-*.json') if f.is_file())
    paths.update((title_dest / 'status.txt', title_dest / 'run.json',
                  ROOT / 'docs/3ds-stage11a-handoff.md', ROOT / 'docs/3ds-stage11a-request.md',
                  PORT / 'reports/STAGE11A-HARDWARE-RU.md', ROOT / baseline['source_snapshot']))
    paths.update(f for f in control.rglob('*') if f.is_file() and f.suffix != '.o')
    inventory = [dict(path=f.relative_to(ROOT).as_posix(), bytes=f.stat().st_size, sha256=sha(f)) for f in sorted(paths)]
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for row in inventory:
            bundle.write(ROOT / row['path'], row['path'],
                         compress_type=zipfile.ZIP_STORED if row['path'].endswith('.zip') else zipfile.ZIP_DEFLATED)
        bundle.writestr('candidate-files.json', json.dumps(inventory, indent=2) + '\n')
    with zipfile.ZipFile(archive) as bundle:
        for row in inventory:
            with bundle.open(row['path']) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
    package = dict(archive=archive.relative_to(ROOT).as_posix(), bytes=archive.stat().st_size,
                   sha256=sha(archive), files=len(inventory), stage11a_frozen=False,
                   note='Instrumentation evidence and starting source snapshot; rebuild still uses preserved normal objects/SDK in the workspace')
    (PORT / 'reports/stage11a-0-package.json').write_text(json.dumps(package, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    print(json.dumps(package, indent=2))


if __name__ == '__main__':
    main()
