#!/usr/bin/env python3
"""Classify the current linker gap using source definitions and retail symbols."""
from pathlib import Path
import re,json
port=Path(__file__).resolve().parents[1];root=port.parent
log=(port/'reports/build-level-b.log').read_text()
missing=sorted(set(re.findall(r"undefined reference to [`']([^']+)'",log)))
result={name:[] for name in missing}
pattern=re.compile(r'^((?:const\s+|static\s+)?\w+[ \t]+(?:\*[ \t]*)?('+ '|'.join(map(re.escape,missing))+r')\b[^\n]*)',re.M)
for directory in ('src','pc_port/src'):
    for path in (root/directory).rglob('*.c'):
        if 'stubs' in path.parts:continue
        source=path.read_text(errors='replace')
        for m in pattern.finditer(source):
            result[m[2]].append({'file':path.relative_to(root).as_posix(),'declaration':m[1][:160]})
(port/'reports/level-b-link-gap.json').write_text(json.dumps(result,indent=2)+'\n')
for name,providers in result.items():
    print(name+': '+ '; '.join(p['file'] for p in providers))
