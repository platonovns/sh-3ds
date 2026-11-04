"""Sanitizer checks of the actual diagnostic recorder with real host filesystem operations."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
p=Path(__file__).resolve().parents[1]
target=p/'build/game-cpu-recorder-test'
subprocess.run(['gcc','-std=gnu11','-O2','-g','-Wall','-Wextra','-Werror',
    '-fsanitize=address,undefined','-DSH_CPU_AUDIT_RECORDER=1','-I'+str(p/'include'),
    str(p/'tests/game_cpu_recorder_test.c'),str(p/'source/game_profile.c'),'-o',str(target)],check=True)
with tempfile.TemporaryDirectory(prefix='sh-cpu-recorder-') as directory:
    run=subprocess.run([str(target),directory],capture_output=True,text=True)
    assert run.returncode==0 and 'PASS' in run.stdout and not run.stderr,(run.returncode,run.stdout,run.stderr)
record=dict(status='PASS',scope=__doc__,output=run.stdout.strip(),
    recorder_sha256=hashlib.sha256((p/'source/game_cpu_recorder.c').read_bytes()).hexdigest())
snapshot=p/'build/cpu-recorder-snapshot-test'
subprocess.run(['gcc','-std=gnu11','-O2','-g','-Wall','-Wextra','-Werror',
    '-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fsanitize=address,undefined',
    '-I'+str(p/'tests/cpu_audit_mock'),'-I'+str(p/'include'),
    str(p/'tests/cpu_recorder_snapshot_test.c'),'-o',str(snapshot)],check=True)
run=subprocess.run([str(snapshot)],capture_output=True,text=True)
assert run.returncode==0 and 'PASS' in run.stdout and not run.stderr,(run.returncode,run.stdout,run.stderr)
record['snapshot_test']=run.stdout.strip()
(p/'reports/stage10-cpu-recorder-host.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
