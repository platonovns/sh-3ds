"""Actual original approach -> attack -> Harry damage for front, side and rear.
Only initial Harry yaw is prepared; the original enemy AI and player damage
execute from the scene-2 development start. World draw/audio are isolated.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1];rows=[]
base=json.loads((p/'build/stage10-dev-scene-2/manifest.json').read_text())
elf=p/'build/stage10-dev-scene-2/diagnostic.elf'
assert hashlib.sha256(elf.read_bytes()).hexdigest()==base['elf_sha256']
for label,yaw in [('front',0),('side',1024),('rear',2048)]:
    env=dict(os.environ,SH_GAME_ELF=str(elf),SH_STAGE9_REGRESSION='1',SH_CAFE_NO_FIRE='1',
        SH_CAFE_PLAYER_YAW=str(yaw),SH_CAFE_TICKS='350',SH_CAFE_REPORT=f'stage10-r5-air-{label}.json')
    env.pop('SH_CAFE_FACE_AWAY',None)
    with (p/f'reports/stage10-r5-air-{label}.log').open('w') as out:
        result=subprocess.run([sys.executable,str(p/'tools/test_stage10_cafe_combat_runtime.py')],env=env,stdout=out,stderr=subprocess.STDOUT)
    assert result.returncode==0,(label,result.returncode)
    r=json.loads((p/f'reports/stage10-r5-air-{label}.json').read_text())
    assert r['fixture_player_yaw']==yaw and r['elf_sha256']==base['elf_sha256']
    before=r['rows'][0]['v'][1];after=min(row['v'][1] for row in r['rows'])
    assert before>after>0
    rows.append(dict(direction=label,yaw=yaw,health_before=before,health_min=after,ticks=r['ticks']))
    print(json.dumps(rows[-1]),flush=True)
report=dict(status='PASS',scope=__doc__,cases=rows,diagnostic=base,hardware_accepted=False)
(p/'reports/stage10-r5-air-directions.json').write_text(json.dumps(report,indent=2)+'\n')
