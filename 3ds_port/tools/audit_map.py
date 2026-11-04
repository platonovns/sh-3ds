#!/usr/bin/env python3
"""Compile-only starting-map dependency audit; NEVER link these objects to app."""
from pathlib import Path
import json
import subprocess
import sys

port = Path(__file__).resolve().parent.parent
root = port.parent
out = port / 'build/map0_s00-audit'
out.mkdir(exist_ok=True)
cc, *flags = sys.argv[1:]
flags += ['-DMAP0_S00', '-DSH_MAP_NAME=map0_s00']
sources = ['player.c', 'map0_s00_2.c', 'map0_s00_anim_info.c',
           'map0_s00_events_data.c', 'map0_s00_header.c', 'Chara_Cheryl.c',
           'Chara_Stalker.c', 'particle.c']
report = {'purpose': 'dependency audit only; no extracted data, no stubs, no app linkage', 'units': {}}
objects = []
for name in sources:
    obj = out / (Path(name).stem + '.o')
    cmd = [cc, *flags, '-c', str(root / 'src/maps/map0_s00' / name), '-o', str(obj)]
    run = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (name + '.log')).write_text(run.stdout)
    item = {'strict_exit': run.returncode}
    # For a precise dependency inventory even when old decomp pointer signatures
    # fail GCC's strict gate. All warnings remain in this audit-only log.
    if run.returncode:
        exploratory = [v for v in cmd if v not in
                       ('-Werror=incompatible-pointer-types', '-Werror=implicit-function-declaration')]
        exploratory.insert(1, '-fpermissive')
        run = subprocess.run(exploratory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out / (name + '.exploratory.log')).write_text(run.stdout)
        item['exploratory_exit'] = run.returncode
    if run.returncode == 0:
        objects.append(obj)
    report['units'][name] = item
nm = cc.replace('gcc', 'nm')
def inventory(paths):
    defined, undefined = set(), set()
    for obj in paths:
        listing = subprocess.check_output([nm, '-g', str(obj)], text=True)
        for line in listing.splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[0] == 'U':
                undefined.add(fields[1])
            elif len(fields) == 3:
                defined.add(fields[2])
    return defined, undefined
defined, undefined = inventory(objects)
core, _ = inventory([port / 'build' / n for n in
    ('psx_memory.o', 'rng.o', 'memmove32.o', 'fsmem.o', 'PsyX_GTE.o', 'libgte.o', 'inline_c.o')])
unresolved = sorted(undefined - defined - core)
report['compiled_objects'] = len(objects)
report['unresolved_after_map_and_core'] = unresolved
report['unresolved_count'] = len(unresolved)
(out / 'unresolved.txt').write_text('\n'.join(unresolved)+'\n')
(out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
