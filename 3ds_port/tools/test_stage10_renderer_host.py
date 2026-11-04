"""Sanitizer checks for native feedback sampling and conservative clipping."""
import json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];cases=[]
for name in ('feedback','culling','modern_controls','cadence'):
    target=p/'build'/('stage10-'+name+'-host')
    subprocess.run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-I'+str(p/'include'),
        str(p/'tests'/('stage10_'+name+'_test.c')),'-lm','-o',str(target)],check=True)
    run=subprocess.run([str(target)],capture_output=True,text=True,check=True)
    assert 'PASS' in run.stdout and not run.stderr,run
    cases.append(dict(case=name,result=run.stdout.strip()))
report=dict(status='PASS',cases=cases)
(p/'reports/stage10-renderer-host.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
