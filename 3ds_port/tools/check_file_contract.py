#!/usr/bin/env python3
"""Reproduce PsyQ/newlib collisions and verify the engine-only call guard."""
from pathlib import Path
import json
import re
import subprocess
import sys

port = Path(__file__).resolve().parent.parent
out = port / 'build/file-contract'
out.mkdir(exist_ok=True)
cc, *flags = sys.argv[1:]
def compile(name, source, profile=True):
    path = out / (name+'.c')
    path.write_text(source)
    used = flags if profile else ['-std=gnu11']
    p = subprocess.run([cc, *used, '-c', str(path), '-o', str(out / (name+'.o'))],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (name+'.log')).write_text(p.stdout)
    return p
headers = '#include <fcntl.h>\n#include <unistd.h>\n'
upstream = (port.parent / 'pc_port/PsyCross/src/psx/libapi.c').read_text()
collisions = {}
for name in ('open', 'read', 'write', 'close', 'lseek'):
    declarations = re.findall(r'^int '+name+r'\([^\n]*\)', upstream, re.M)
    assert declarations, name
    p = compile('collision_'+name, headers + declarations[-1]+';\n', False)
    collisions[name] = p.returncode != 0
assert all(collisions[n] for n in ('open', 'read', 'write', 'lseek')), collisions
assert not collisions['close'] # same C signature, still a semantic interposition hazard
calls = {'open': 'open("x", 0)', 'read': 'read(0, 0, 0)', 'write': 'write(0, 0, 0)',
         'close': 'close(0)', 'lseek': 'lseek(0, 0, 0)'}
for name, call in calls.items():
    p = compile('forbidden_'+name, 'int probe(void) { return (int)'+call+'; }\n')
    assert p.returncode and 'explicit PsxFile_' in p.stdout, (name, p.stdout)
p = compile('namespaced', '#include "psyq_file.h"\nint probe(void) { return PsxFile_Open("bu00:", 0); }\n')
assert p.returncode == 0, p.stdout
p = compile('hal_newlib', headers + 'int probe(void) { int f = open("x", O_RDONLY); return close(f); }\n', False)
assert p.returncode == 0, p.stdout
report = {'newlib_incompatible_prototypes': collisions, 'engine_guards': '5/5 PASS',
          'namespaced_contract': 'PASS (no backend linked)', 'hal_newlib': 'PASS'}
(port / 'reports/file-contract.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
