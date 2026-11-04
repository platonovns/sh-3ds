"""Host sanitizer checks for profiler accounting and original timing contracts."""
import json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1]
cases=[]
for name,sources in [('profile',['tests/game_profile_test.c','source/game_profile.c']),
                     ('timing',['tests/stage8_timing_test.c'])]:
    target=p/'build'/('stage10-'+name+'-test')
    subprocess.run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-I'+str(p/'include'),*[str(p/s) for s in sources],'-o',str(target)],check=True)
    run=subprocess.run([str(target)],capture_output=True,text=True,check=True)
    assert 'PASS' in run.stdout and not run.stderr,run
    cases.append(dict(case=name,result=run.stdout.strip()))
(p/'reports/stage10-host-profile.json').write_text(json.dumps(dict(status='PASS',cases=cases),indent=2)+'\n')
print(json.dumps(cases,indent=2))
