#!/usr/bin/env python3
"""Audit-only retail-source projection, never linked into the application.

Desktop policy blocks are excluded while shared headers keep the existing
native pointer/packet ABI. This inventories the proposed platform split before
editing original game translation units. No stub implementation is supplied.
"""
from pathlib import Path
import json
import subprocess
import sys

port = Path(__file__).resolve().parents[1]
root = port.parent
cc, *flags = sys.argv[1:]
flags = [f for f in flags if f not in ('-Werror=implicit-function-declaration', '-Werror=incompatible-pointer-types')]
out = port / 'build/title-native-audit'
out.mkdir(exist_ok=True)
sources = ['sys/game_main.c', 'events/title.c', 'sys/syswork_globals.c', 'screen/screen_data.c',
           'screen/screen_draw.c', 'screen/screen_fade.c', 'screen/background_draw.c', 'text/text_draw.c',
           'sys/fs_screens.c', 'sys/settings_reset.c', 'sys/joy.c', 'sys/vsync.c',
           'game_boot/game_load.c', 'game_boot/game_boot.c', 'gfx/world_draw.c',
           'bodyprog_8005E0DC.c', 'sys/memcard_2.c', 'memcard.c', 'math/math.c']
paths = [root / 'src/bodyprog' / p for p in sources if (root / 'src/bodyprog' / p).exists()]
paths += [root / 'src/screens/b_konami/b_konami.c', root / 'src/screens/stream/stream.c']
report = {'purpose': 'proposed native split only, no app linkage or stubs', 'units': {}}
objects = []
for path in paths:
    text = path.read_text(encoding='utf-8-sig')
    # Production source guards now carry the selected split. No source projection.
    projected = out / path.name
    projected.write_text(text)
    if path.name == 'game_main.c':
        pre = subprocess.check_output([cc, *flags, '-E', '-P', str(projected)], text=True)
        start = pre.index('void MainLoop(void)\n{')
        (out / 'MainLoop.preprocessed.c').write_text(pre[start:])
    obj = projected.with_suffix('.o')
    run = subprocess.run([cc, '-fpermissive', *flags, '-c', str(projected), '-o', str(obj)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    projected.with_suffix('.log').write_text(run.stdout)
    report['units'][str(path.relative_to(root))] = {'exit': run.returncode,
        'errors': [line for line in run.stdout.splitlines() if 'error:' in line][:20]}
    if not run.returncode: objects.append(obj)
nm = cc.replace('gcc', 'nm')
defined, undefined = set(), set()
for obj in objects:
    for line in subprocess.check_output([nm, '-g', str(obj)], text=True).splitlines():
        f = line.split()
        if len(f) == 2 and f[0] == 'U': undefined.add(f[1])
        elif len(f) == 3: defined.add(f[2])
report['compiled_objects'] = len(objects)
report['raw_unresolved'] = sorted(undefined - defined)
report['raw_unresolved_count'] = len(report['raw_unresolved'])
(port / 'reports/title-native-audit.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'compiled': len(objects), 'attempted': len(paths),
                  'raw_unresolved': report['raw_unresolved_count'],
                  'failed': {p:v['errors'][:2] for p,v in report['units'].items() if v['exit']}}, indent=2))
