"""Record exact production source changes relative to hardware-accepted R5."""
import difflib,hashlib,json,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
ns={'__file__':str(p/'tools/build_identity.py')}
exec(compile((p/'tools/build_identity.py').read_text().split('digest = hashlib.sha256()')[0],'inputs','exec'),ns)
changed=[];diff=[]
with zipfile.ZipFile(p/'baselines/stage10-r5.zip') as z:
    names=set(z.namelist())
    for f in sorted(set(ns['paths'])):
        n=f.relative_to(root).as_posix();old=z.read(n) if n in names else b'';new=f.read_bytes()
        if old==new:continue
        changed.append(dict(file=n,old_sha256=hashlib.sha256(old).hexdigest() if old else None,new_sha256=hashlib.sha256(new).hexdigest()))
        diff.extend(difflib.unified_diff(old.decode(errors='replace').splitlines(True),new.decode(errors='replace').splitlines(True),fromfile='R5/'+n,tofile='R6/'+n))
    for n in ('3ds_port/source/game_gpu.c','src/bodyprog/game_boot/game_boot.c',
              'src/bodyprog/events/title.c','3ds_port/source/game_controls.c'):
        if n in names:assert z.read(n)==(root/n).read_bytes(),n
report=dict(status='PASS',scope=__doc__,changes=changed)
(p/'reports/stage10-r6-source-diff.json').write_text(json.dumps(report,indent=2)+'\n')
(p/'reports/stage10-r6-source.diff').write_text(''.join(diff))
print(json.dumps(report,indent=2))
