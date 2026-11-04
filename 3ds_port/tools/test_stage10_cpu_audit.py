"""Host sanitizer oracle for the SDK-only CPU audit (not hardware evidence)."""
import hashlib,json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1]
target=p/'build/game-cpu-audit-test'
source=p/'tests/game_cpu_audit_test.c'
subprocess.run(['gcc','-std=gnu11','-O2','-g','-pthread','-Wall','-Wextra','-Werror',
    '-fsanitize=address,undefined','-I'+str(p/'tests/cpu_audit_mock'),'-I'+str(p/'include'),
    str(source),'-lm','-o',str(target)],check=True)
run=subprocess.run([str(target)],capture_output=True,text=True)
assert run.returncode==0 and 'PASS' in run.stdout and not run.stderr,(run.returncode,run.stdout,run.stderr)
record=dict(status='PASS',scope='Host SDK mock; not hardware utilization',
    output=run.stdout.strip(),source_sha256=hashlib.sha256((p/'source/game_cpu_audit.c').read_bytes()).hexdigest())
(p/'reports/stage10-r6-cpu-host.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
