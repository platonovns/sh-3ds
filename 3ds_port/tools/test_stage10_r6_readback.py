"""ASan/UBSan bit-exact R5 oracle for region/phase-preserving CPU readback."""
import hashlib,json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];exe=p/'build/stage10_r6_readback_test'
subprocess.run(['cc','-std=c11','-O2','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(p/'include'),str(p/'tests/stage10_r6_readback_test.c'),'-o',str(exe)],check=True)
run=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
assert run.stdout.startswith('PASS:') and not run.stderr,run
report=dict(status='PASS',scope=__doc__,result=run.stdout.strip(),source_sha256=hashlib.sha256((p/'include/psx_readback_region.h').read_bytes()).hexdigest())
(p/'reports/stage10-r6-readback-host.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
