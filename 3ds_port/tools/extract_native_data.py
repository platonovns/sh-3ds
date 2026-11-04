#!/usr/bin/env python3
"""Share exact original C declarations without linking unrelated inventory UI."""
from pathlib import Path
import hashlib
import json
import re

port=Path(__file__).resolve().parents[1]
root=port.parent
source=root/'src/bodyprog/items/item_screens_3.c'
text=source.read_text()
clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),text,flags=re.S)
symbols=('g_Inventory_EquippedItem','g_Player_GrabReleaseInputTimer',
         'g_Player_DisableControl','g_Player_LastWeaponSelected','D_800AE1C0','D_800AE204')
declarations=[];manifest=[]
for symbol in symbols:
    matches=list(re.finditer(r'^\w+[ \t]+(?:\*[ \t]*)?'+symbol+r'\b',clean,re.M))
    assert len(matches)==1,(symbol,len(matches))
    start=matches[0].start();end=start;depth=0
    while end<len(clean):
        c=clean[end]
        if c in '{[(':depth+=1
        elif c in '}])':depth-=1
        elif c==';' and depth==0:break
        end+=1
    declaration=text[start:end+1]
    assert declaration.endswith(';') and len(declaration)<65536,symbol
    declarations.append(declaration)
    manifest.append({'symbol':symbol,'source':str(source.relative_to(root)),
        'line':text[:start].count('\n')+1,'bytes':len(declaration.encode()),
        'sha256':hashlib.sha256(declaration.encode()).hexdigest()})
out=port/'build-game/native_data.inc'
result='/* Generated from exact original C declarations; do not edit. */\n'+'\n\n'.join(declarations)+'\n'
out.parent.mkdir(exist_ok=True)
if not out.exists() or out.read_text()!=result:out.write_text(result)
(port/'reports/native-data-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
