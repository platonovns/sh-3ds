"""Independent development links for valid-street R5/R6 benchmark pairs."""
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1]
cases=[('street-off',['--flashlight-benchmark','off']),('street-on',['--flashlight-benchmark','on']),
       ('street-before-off',['--flashlight-benchmark','off','--renderer-reference-r5']),
       ('street-before-on',['--flashlight-benchmark','on','--renderer-reference-r5'])]
for kind in ('air','groaner'):
    for label,ref in (('after',[]),('before',['--renderer-reference-r5'])):
        cases.append((f'street-{kind}-{label}',['--flashlight-benchmark','off','--town-enemy',kind,*ref]))
def build(case):
    name,args=case
    with (p/f'reports/stage10-r6-{name}-build.log').open('w') as out:
        r=subprocess.run([sys.executable,str(p/'tools/build_stage10_diagnostic.py'),'--scene','8','--package',*args],stdout=out,stderr=subprocess.STDOUT)
    assert r.returncode==0,(name,r.returncode)
    print(name+' PASS',flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(build,cases))
