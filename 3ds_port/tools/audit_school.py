"""Inventory original school dependencies, without altering progression state."""
from pathlib import Path
import json,re,hashlib
ROOT=Path(__file__).resolve().parents[2]
MAPS=[f'map1_s{i:02}' for i in range(7)]
def tokens(text,pattern):return sorted(set(re.findall(pattern,text)))
def audit():
    maps={}
    for name in MAPS:
        directory=ROOT/'src/maps'/name
        data=(directory/(name+'_events_data.c')).read_text()
        header=(directory/(name+'_header.c')).read_text()
        sources=list(directory.glob('*.c'))+list(directory.glob('*.h'))
        text='\n'.join(p.read_text() for p in sources)
        events=[]
        for match in re.finditer(r'\{([^{}]+)\}',data,re.S):
            fields=dict(re.findall(r'\.(\w+)\s*=\s*([^,\n]+)',match[1]))
            if 'sysState' in fields:events.append(fields)
        callbacks=re.search(r'g_MapEventFuncs\[\]\)\(\)\s*=\s*\{(.*?)\};',header,re.S)
        if not callbacks:callbacks=re.search(r'g_MapEventFuncs\[\][^=]*=\s*\{(.*?)\};',header,re.S)
        maps[name]=dict(events=events,transitions=[e for e in events if e.get('sysState')=='SysState_LoadOverlay'],
            items=tokens(text,r'InvItemId_\w+'),flags=tokens(text,r'EventFlag_\w+'),
            characters=tokens(header,r'Chara_\w+'),
            includes=tokens(text,r'#include\s+"([^"\n]+)"'),
            callbacks=tokens(callbacks[1],r'\b(?:MapEvent_\w+|func_\w+)') if callbacks else [],
            fmv=[e for e in events if e.get('sysState')=='SysState_Fmv'],
            sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    return dict(scope='MAP1_S00..S06 -> MAP2_S00 exterior; next chapter excluded',
        method='Original event-table and header source inventory; no simulated hardware acceptance',maps=maps)
if __name__=='__main__':
    result=audit()
    out=ROOT/'3ds_port/reports/school-dependency-audit.json'
    out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    for name,row in result['maps'].items():
        print(name,len(row['events']),'events;',len(row['callbacks']),'callbacks;',
              'destinations=',sorted(set(e['mapIdx'] for e in row['transitions'])),
              'items=',','.join(row['items']),'FMV=',row['fmv'])
