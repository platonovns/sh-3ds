#!/usr/bin/env python3
"""Make legacy buffer pointer conversions explicit from strict GCC diagnostics.

Only pointer assignments with a simple expected pointer type are handled.
Call arguments require manual ABI review. No compiler checks are disabled.
"""
from pathlib import Path
import json
import re
import sys
import shlex
import subprocess

port=Path(__file__).resolve().parents[1]
log=Path(sys.argv[1]).read_text()
if len(sys.argv)>2:
    source=sys.argv[2]
    command=next(line for line in log.splitlines() if line.startswith('arm-none-eabi-gcc ') and ('-c '+source+' ') in line)
    args=shlex.split(command)
    pre=subprocess.check_output(args[:args.index('-c')]+['-E','-P',source],cwd=port,text=True)
    (port/'build/native-preprocessed.c').write_text(pre)
    clean=re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:'\n'*m[0].count('\n'),pre,flags=re.S)
    stack=[]
    for i,line in enumerate(clean.splitlines()):
        for c in line:
            if c=='{':stack.append((i+1,line.strip()))
            elif c=='}':
                if stack:stack.pop()
                else:print('Extra closing brace',i+1)
    print(json.dumps({'unclosed':stack},indent=2));sys.exit(0)
errors=list(re.finditer(r'^([^\n:]+):(\d+):(\d+): error: (.+)$',log,re.M))
changes={}
for n,m in enumerate(errors):
    message=m[4]
    typ=None
    if q:=re.match(r"assignment to '([^']+\*)' .*from incompatible pointer type",message): typ=q[1]
    if not typ or not re.fullmatch(r'(?:const )?[A-Za-z_]\w*(?: \w+)* \*',typ):continue
    path=(port/m[1]).resolve()
    assert path.is_relative_to(port.parent/'src'),path
    lines=path.read_text().splitlines()
    row=int(m[2])-1; line=lines[row]
    positions=[i for i in range(len(line)) if len(line[:i].expandtabs(8))==int(m[3])-1]
    if not positions:continue
    start=positions[0]
    if message.startswith('assignment to'):
        if line[start:start+1]!='=':continue
        start+=1
        while start<len(line) and line[start].isspace():start+=1
    if start>=len(line):continue
    depth=0;end=start
    while end<len(line):
        c=line[end]
        if depth==0 and c in ',;)':break
        if c in '([':depth+=1
        elif c in ')]':depth-=1
        end+=1
    expr=line[start:end].rstrip()
    if not expr or depth:continue
    changes.setdefault(path,[]).append((row,start,start+len(expr),f'({typ})({expr})'))
summary=[]
for path,edits in changes.items():
    lines=path.read_text().splitlines()
    for row,start,end,new in sorted(set(edits),reverse=True):
        summary.append({'file':str(path.relative_to(port.parent)),'line':row+1,'before':lines[row][start:end],'after':new})
        lines[row]=lines[row][:start]+new+lines[row][end:]
    path.write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,indent=2))
