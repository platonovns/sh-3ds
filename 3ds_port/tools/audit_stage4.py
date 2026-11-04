#!/usr/bin/env python3
"""Current ARM dependency census. Audit objects are never linked into the app.

Counts are raw object unions (not runtime closure or a promise of linkability).
Compile failures remain failures; no fabricated declarations or zero stubs.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

port = Path(__file__).resolve().parent.parent
root = port.parent
cc, *flags = sys.argv[1:]
nm = cc.replace('gcc', 'nm')
out = port / 'build/stage4-audit'
out.mkdir(parents=True, exist_ok=True)
groups = {
    'title': ['src/bodyprog/sys/game_main.c', 'src/bodyprog/events/title.c',
              'src/bodyprog/game_boot/game_boot.c', 'src/bodyprog/game_boot/game_load.c',
              'src/bodyprog/game_boot/load_screen.c', 'src/bodyprog/sys/fs_screens.c',
              'src/bodyprog/screen/background_draw.c', 'src/bodyprog/text/text_draw.c',
              'src/main/fsqueue_1.c', 'src/main/fsqueue_2.c', 'src/main/fsqueue_3.c',
              'src/bodyprog/view/vc_main.c', 'src/bodyprog/gfx/world_draw.c',
              'src/bodyprog/gfx/bodyprog_80040B74.c', 'src/screens/b_konami/b_konami.c',
              'src/screens/stream/stream.c'],
}
report = {'method': 'raw ARM object union before GC/libc; failed TUs excluded and listed',
          'units': {}, 'groups': {}}

def inventory(paths):
    defined, undefined = set(), set()
    for obj in paths:
        for line in subprocess.check_output([nm, '-g', str(obj)], text=True).splitlines():
            f = line.split()
            if len(f) == 2 and f[0] == 'U':
                undefined.add(f[1])
            elif len(f) == 3 and f[1].upper() != 'U':
                defined.add(f[2])
    return defined, undefined

baseline = list((port / 'build').glob('*.o'))
satisfied, _ = inventory(baseline)
report['baseline_objects'] = [p.name for p in baseline]
objects = []
for path in groups['title']:
    obj = out / (Path(path).stem + '.o')
    run = subprocess.run([cc, *flags, '-c', str(root / path), '-o', str(obj)],
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (obj.stem + '.log')).write_text(run.stdout)
    report['units'][path] = {'strict_exit': run.returncode,
        'source_sha256': hashlib.sha256((root / path).read_bytes()).hexdigest() if (root / path).exists() else None,
        'errors': [s for s in run.stdout.splitlines() if 'error:' in s][:30]}
    if run.returncode:
        exploratory = [f for f in flags if f not in
                       ('-Werror=implicit-function-declaration', '-Werror=incompatible-pointer-types')]
        run = subprocess.run([cc, '-fpermissive', *exploratory, '-c', str(root / path), '-o', str(obj)],
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out / (obj.stem + '.exploratory.log')).write_text(run.stdout)
        report['units'][path]['exploratory_exit'] = run.returncode
    if not run.returncode:
        objects.append(obj)

map_objects = list((port / 'build/map0_s00-audit').glob('*.o'))
for name, paths in [('map0_s00', map_objects), ('title_compilable_subset', objects),
                    ('title_and_map_compilable_subset', objects + map_objects)]:
    defined, undefined = inventory(paths)
    remaining = sorted(undefined - defined - satisfied)
    report['groups'][name] = {'objects': [p.name for p in paths], 'unresolved_count': len(remaining),
                            'unresolved': remaining,
                            'satisfied_by_stage1_3': sorted((undefined - defined) & satisfied)}
(port / 'reports/stage4-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: {a: b for a, b in v.items() if a != 'unresolved'}
                  for k, v in report['groups'].items()}, indent=2))
