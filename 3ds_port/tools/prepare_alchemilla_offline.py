"""Private frozen Post-school dependencies; no hardware build or publication."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'post-school-content'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((SOURCE/'3ds_port/build/post-school/manifest.json').read_text())
assert m['build']=='post-school-content-src-d9f536f248445526'
assert m['scope']=='INTERNAL_ELF_NOT_HARDWARE_CANDIDATE' and not m['published']
assert sha(SOURCE/'3ds_port/build/post-school/post-school-content.elf')==m['elf_sha256']
for name in ('3ds_port/build','3ds_port/build-game','pc_port/PsyCross','assets','asm'):
    source=SOURCE/name
    if source.exists():
        shutil.copytree(source,ROOT/name,dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.git','__pycache__','*.3dsx'))
data=ROOT/'sh1_data'
if not data.exists():data.symlink_to(SOURCE/'sh1_data',target_is_directory=True)
print('Prepared immutable offline dependencies; no hardware candidate')
