"""Build internal ARM ELF only; no .3dsx and no publication."""
from pathlib import Path
import hashlib, json, subprocess, sys

port=Path(__file__).resolve().parents[1]
root=port.parent
out=port/'build/sewer1-compile-probe'
def snapshot():
    paths=set()
    for d in (root/'include',root/'pc_port/include',port/'include'):
        paths.update(d.rglob('*.h'))
    for d in (root/'src/maps/map5_s00',root/'src/maps/map5_s01',root/'src/maps/characters'):
        paths.update(p for p in d.rglob('*') if p.is_file())
    paths.update(root/p for p in ['pc_port/src/hanged_scratcher_anim_infos.c','pc_port/src/groaner_m5s01_anim_infos.c','3ds_port/source/game_map.c',
        '3ds_port/source/game_native.c','3ds_port/Makefile.game','3ds_port/sewer1_sources.mk',
        '3ds_port/tools/native_overlay.py','3ds_port/tools/probe_sewer1_compile.py',
        '3ds_port/tools/probe_sewer1_link.py','3ds_port/tools/probe_sewer1_elf.py','3ds_port/tools/build_sewer1.py',
        'pc_port/build_gen/extracted_data/map5_s00_extracted_data.c','pc_port/build_gen/extracted_data/map5_s01_extracted_data.c',
        'configs/USA/maps/sym.map5_s00.txt','configs/USA/maps/sym.map5_s01.txt'])
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
before=snapshot()
for script in ('probe_sewer1_compile.py','probe_sewer1_link.py','probe_sewer1_elf.py'):
    subprocess.run([sys.executable,str(port/'tools'/script)],check=True)
manifest=json.loads((out/'build-manifest.json').read_text())
assert snapshot()==before==manifest['sources'],'Input changed while building'
print('Internal ELF source inventory verified; validation remains required.')
