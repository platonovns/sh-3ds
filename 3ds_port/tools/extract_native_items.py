#!/usr/bin/env python3
"""Select exact retail declarations without linking unrelated inventory UI."""
from pathlib import Path
import hashlib,json,re
port=Path(__file__).resolve().parents[1];root=port.parent
selections={
 'src/bodyprog/items/item_screens_3.c': '''g_Inventory_EquippedItem g_Player_GrabReleaseInputTimer
 g_Player_DisableControl g_Player_LastWeaponSelected D_800AE1C0 D_800AE204 D_800AD4C4 D_800AD4C8 D_800AE1B4
 D_800AE4DC D_800AE500 D_800AE5CC D_800AE5F0 D_800AE700 D_800AEEDC D_800AEF78 D_800AF014
 D_800AF04C D_800AF070 D_800AF1FC D_800AF216 D_800AF220 D_800AF5C6 D_800AF624 D_800AF626 D_800AFBF4
 g_Player_AttackAnimIdx g_Player_FlexRotationX g_Player_FlexRotationY g_Player_IsInWalkToRunTransition
 g_Player_IsMultiTapAttack g_Player_MeleeAttackType g_Player_RockDrill_DirectionAttack g_Player_TargetNpcIdx
 g_Items_GunsMaxLoadAmmo GameFs_Tim00TIMLoad GameFs_MapItemsModelLoad Gfx_PlayerHeldItemAttach Items_AmmoReloadCalculation
 g_CollisionPointCache Inventory_AddSpecialItem'''.split(),
 'src/bodyprog/items/item_screens_2.c':['Game_TimerUpdate','D_80025EB0','func_8004F190'],
 'src/bodyprog/items/item_screens_1.c':['Inventory_HyperBlasterFunctionalTest','Game_HyperBlasterBeamColorGet','func_8004C564'],
 'pc_port/src/stubs/data_stubs.c':['g_AsRodataPsxRaw'],
 'src/bodyprog/events/events_util.c':['D_8002AB10']
}
for full in ('src/bodyprog/items/item_screens_1.c', 'src/bodyprog/items/item_screens_2.c', 'src/bodyprog/items/item_screens_3.c', 'src/bodyprog/events/events_util.c'):
    selections.pop(full, None)
declarations=[];manifest=[]
def cleaned(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:'\n'.join(' '*len(s) for s in m[0].split('\n')),text,flags=re.S)
def record(path,symbol,start,end,text):
    declaration=text[start:end]
    assert len(declaration)<65536,symbol
    declarations.append(declaration)
    manifest.append({'symbol':symbol,'source':str(path.relative_to(root)),
        'line':text[:start].count('\n')+1,'bytes':len(declaration.encode()),
        'sha256':hashlib.sha256(declaration.encode()).hexdigest()})
for name,symbols in selections.items():
    path=root/name;text=path.read_text();clean=cleaned(text)
    for symbol in symbols:
        storage=r'(?:static\s+)?' if symbol=='D_80025EB0' else ''
        matches=list(re.finditer(r'^'+storage+r'(?:const\s+)?\w+[ \t]+(?:\*[ \t]*)?'+symbol+r'\b',clean,re.M))
        assert len(matches)==1,(symbol,len(matches))
        start=matches[0].start();end=start;depth=0
        function=clean[matches[0].end():].lstrip().startswith('(')
        if symbol=='g_Items_GunsMaxLoadAmmo':
            start=text.rfind('#ifdef SH_PC_PORT',0,start)
            end=text.index('\n};',end)+3
            record(path,symbol,start,end,text)
            continue
        seen_body=False
        while end<len(clean):
            c=clean[end]
            if c in '{[(':
                depth+=1
                if c=='{':seen_body=True
            elif c in '}])':
                depth-=1
                if function and seen_body and depth==0 and c=='}':end+=1;break
            elif c==';' and depth==0: end+=1;break
            end+=1
        record(path,symbol,start,end,text)
out=port/'build-game/native_data.inc'
result='/* Generated from exact original C declarations; do not edit. */\n'+'\n\n'.join(declarations)+'\n'
out.parent.mkdir(exist_ok=True)
if not out.exists() or out.read_text()!=result:out.write_text(result)
reports=port/'build/reports'
reports.mkdir(parents=True,exist_ok=True)
(reports/'native-data-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
