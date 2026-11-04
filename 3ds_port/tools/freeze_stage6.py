#!/usr/bin/env python3
"""Freeze an analyzed normal-route Cafe candidate; never accept hardware here."""
import argparse, ast, contextlib, hashlib, io, json, runpy, shutil, zipfile
from pathlib import Path

p = Path(__file__).resolve().parents[1]
root = p.parent
parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
parser.add_argument('--label', default='stage6-fixed-cafe')
args = parser.parse_args()
read = lambda f: json.loads(f.read_text(encoding='utf-8-sig'))
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
info = read(args.run / 'run.json')
analysis = read(args.run / (args.label + '-analysis.json'))
assert analysis['status'].startswith('AZAHAR LOG PASS')
assert all(analysis['route'].values()) and analysis['variant'] == 'NORMAL_NEW_GAME'
assert analysis['functional_cafe_seconds'] >= 596
assert info['gdb_stub'] is False and info['diagnostic_gameplay'] is False
assert analysis['last']['stage6_pad_route'] == '0'
assert analysis['sha256'] == info['build_sha256'] == sha(p / 'silenthill_game.3dsx')
assert sha(args.run / 'silenthill_3ds.3dsx') == info['build_sha256']
assert sha(p / 'build/hardware-stage5-edge/silenthill_game.3dsx') == \
    '482db74e5b541ea70de80f8e7a58005a511fe6b697ac4c18e9f7c922e78b3b0b'
assert 'SH_3DS_DEV_START_MAP' not in (p / 'build-game/flags').read_text()
assert read(p / 'reports/stage6-particle-hull-after.json')['closed_convex_contour']
assert read(p / 'reports/stage6-particle-hull-before.json')['returned'] is False
for name in ('stage6-contract-arm', 'stage6-pose-arm'):
    assert read(p / ('reports/' + name + '.json'))['failure_bits'] == 0
assert read(p / 'reports/stage6-menu-arm.json')['passed']
for name in ('stage4_autoinput.txt', 'stage5_profile.txt', 'stage6_route.txt', 'stage6_observe.txt'):
    assert not (root / 'sh1_data' / name).exists(), name
with contextlib.redirect_stdout(io.StringIO()):
    identity = runpy.run_path(str(p / 'tools/build_identity.py'))
assert identity['identity'] == info['build_identity']

candidate = p / 'build/hardware-stage6-cafe'
archive = p / 'baselines/stage6-cafe-candidate.zip'
evidence = p / 'reports/azahar-stage6-cafe'
assert not candidate.exists() and not archive.exists() and not evidence.exists()
handoff = root / 'docs/3ds-stage6-handoff.md'
assert handoff.exists() and 'HARDWARE PENDING' in handoff.read_text()
assert '{{' not in handoff.read_text()
candidate.mkdir()
for ext in ('.3dsx', '.elf', '.map', '.smdh'):
    shutil.copy2(p / ('silenthill_game' + ext), candidate / ('silenthill_game' + ext))
evidence.mkdir()
for name in ('run.json', 'qt-config.ini', 'stage4_status.txt', 'azahar_log.txt',
             args.label + '-samples.json', args.label + '-result.json', args.label + '-analysis.json'):
    shutil.copy2(args.run / name, evidence / name)
if analysis['movement_evidence']['run'] != args.run.name:
    motion_run = args.run.parent / analysis['movement_evidence']['run']
    motion_dir = evidence / 'separate-motion'
    motion_dir.mkdir()
    for name in ('run.json', args.label + '-samples.json', args.label + '-result.json'):
        shutil.copy2(motion_run / name, motion_dir / name)
build = {'status': 'HARDWARE PENDING', 'build': info['build_identity'],
         'binary': (candidate / 'silenthill_game.3dsx').relative_to(root).as_posix(),
         'bytes': info['build_bytes'], 'sha256': info['build_sha256'],
         'normal_route_run': args.run.name, 'analysis': analysis,
         'hardware_acceptance': 'Requires user validation on real New Nintendo 3DS'}
report = p / 'reports/stage6-candidate.json'
report.write_text(json.dumps(build, indent=2) + '\n')

# Preserve the previous source closure and add every input of the current
# bounded build identity, plus the new tooling, fixtures and evidence.
with zipfile.ZipFile(p / 'baselines/stage5-edge-candidate.zip') as z:
    previous = json.loads(z.read('manifest.json'))
paths = [root / n for n in previous if not n.startswith('3ds_port/build/')]
paths += identity['paths']
# Include the pinned upstream GTE inputs and headers as actual bytes, in
# addition to the input hashes and native patch inherited from Stage 5.
prepare = ast.parse((p / 'tools/prepare_psycross.py').read_text())
upstream_inputs = next(ast.literal_eval(n.value) for n in prepare.body
                       if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'sources' for t in n.targets))
upstream = root / 'pc_port/PsyCross'
paths += [upstream / name for name in upstream_inputs]
paths += list((upstream / 'include').rglob('*'))
paths += [f for f in upstream.iterdir() if f.is_file() and f.name.lower().startswith(('license', 'copying'))]
paths += [root / '.gitmodules']
paths += [f for directory in (candidate, evidence, p / 'tools', p / 'tests')
          for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
paths += list((p / 'reports').glob('stage6-*'))
paths += list((root / 'docs').glob('3ds-stage6-*'))
paths += [p / 'build-game/flags', p / 'build/build_identity.h', report]
paths = sorted(set(f for f in paths if f.is_file()))
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin', '.cue') for f in paths)
manifest = {f.relative_to(root).as_posix(): {'bytes': f.stat().st_size, 'sha256': sha(f)} for f in paths}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
    for f in paths:
        z.write(f, f.relative_to(root).as_posix())
    z.writestr('manifest.json', json.dumps(manifest, indent=2) + '\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == len(manifest) + 1
    for name, expected in manifest.items():
        data = z.read(name)
        assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
build['archive'] = {'path': archive.relative_to(root).as_posix(), 'bytes': archive.stat().st_size,
                    'sha256': sha(archive), 'verified_members': len(manifest)}
report.write_text(json.dumps(build, indent=2) + '\n')
print(json.dumps({k: v for k, v in build.items() if k != 'analysis'}, indent=2))
