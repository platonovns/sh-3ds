"""Twelve real MainLoop quick-reload cases: stance/aim, 30/60 and reserve/repeat."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1];all_cases=[]
elf=Path(os.environ['SH_GAME_ELF']);digest=hashlib.sha256(elf.read_bytes()).hexdigest()
for style in ('held','stance'):
    env=dict(os.environ,SH_QUICK_REPORT=f'stage10-r6-quick-{style}.json')
    env.pop('SH_QUICK_OBSERVE',None);env.pop('SH_QUICK_FROM_STANCE',None)
    if style=='stance':env['SH_QUICK_FROM_STANCE']='1'
    with (p/f'reports/stage10-r6-quick-{style}.log').open('w') as out:
        r=subprocess.run([sys.executable,str(p/'tools/test_stage10_r6_quick_reload.py')],env=env,stdout=out,stderr=subprocess.STDOUT)
    assert r.returncode==0,(style,r.returncode)
    report=json.loads((p/f'reports/stage10-r6-quick-{style}.json').read_text());assert report['elf_sha256']==digest and len(report['cases'])==6
    for reserve in (60,3):
        pair=[c for c in report['cases'] if c['reserve']==reserve]
        assert abs(pair[0]['reload_sim_ms']-pair[1]['reload_sim_ms'])<70,(style,reserve,pair[0]['reload_sim_ms'],pair[1]['reload_sim_ms'])
    all_cases.extend({k:v for k,v in c.items() if k not in ('steps','run')} for c in report['cases'])
    print(json.dumps(dict(style=style,status='PASS',cases=6)),flush=True)
result=dict(status='PASS',scope=__doc__,cases=all_cases,elf_sha256=digest,hardware_accepted=False)
(p/'reports/stage10-r6-quick-matrix.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
