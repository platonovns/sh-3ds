"""ASan/UBSan and API/state equivalence to the accepted R6 texture cache."""
import json,subprocess,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];dest=p/'build/stage10-cache';dest.mkdir(exist_ok=True)
with zipfile.ZipFile(p/'baselines/stage9-audio-r6-accepted.zip') as z:
    (dest/'reference.c').write_bytes(z.read('3ds_port/source/game_texture_cache.c'))
flags=['gcc','-std=gnu11','-O2','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(p/'include')]
renames=['-Dgame_texture_'+k+'=ref_'+v for k,v in
    [('begin','begin'),('pin','pin'),('acquire','acquire'),('invalidate','invalidate')]]
subprocess.run([*flags,*renames,'-c',str(dest/'reference.c'),'-o',str(dest/'reference.o')],check=True)
for name,source,objects in [('contract','game_texture_cache_test.c',[]),
                            ('equivalence','stage10_cache_equivalence.c',[str(dest/'reference.o')])]:
    target=dest/name
    subprocess.run([*flags,str(p/'tests'/source),str(p/'source/game_texture_cache.c'),*objects,'-o',str(target)],check=True)
    run=subprocess.run([str(target)],capture_output=True,text=True,check=True)
    assert not run.stderr,run.stderr
    print(run.stdout.strip())
    if name=='equivalence':(p/'reports/stage10-cache-equivalence.json').write_text(run.stdout)
