"""ASan/UBSan: direct tiled decode equals accepted R5 row decoder and swizzle."""
import hashlib,json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];exe=p/'build/stage10_r6_decode_test'
subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(p/'include'),str(p/'tests/stage10_r6_decode_test.c'),str(p/'source/game_texture_decode.c'),'-o',str(exe)],check=True)
r=subprocess.run([str(exe)],capture_output=True,text=True,check=True);assert r.stdout.startswith('PASS:') and not r.stderr,r
report=dict(status='PASS',scope=__doc__,result=r.stdout.strip(),source_sha256=hashlib.sha256((p/'source/game_texture_decode.c').read_bytes()).hexdigest())
(p/'reports/stage10-r6-decode-host.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
