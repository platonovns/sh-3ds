#!/usr/bin/env python3
"""Retain reviewed portable C branches whose alternative contains MIPS asm."""
from pathlib import Path
import re
import sys
for name in sys.argv[1:]:
    path=Path(name);lines=path.read_text().splitlines();stack=[];changes=[]
    for n,line in enumerate(lines):
        if re.match(r'\s*#\s*if',line):stack.append([n,None])
        elif re.match(r'\s*#\s*else\b',line) and stack:stack[-1][1]=n
        elif re.match(r'\s*#\s*endif\b',line) and stack:
            start,other=stack.pop()
            if other is not None and lines[start].strip()=='#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)' and '__asm__' in '\n'.join(lines[other+1:n]):
                changes.append(start+1);lines[start]=lines[start].replace('#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)','#ifdef SH_PC_PORT')
    if changes:path.write_text('\n'.join(lines)+'\n')
    print(name,changes)
