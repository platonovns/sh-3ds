"""Copy only immutable/offline dependencies from the School checkpoint.

Run once in the existing project workspace. Never copies live Stage 11B sources,
never writes game data or memory cards, and never invokes a hardware build.
"""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'school-completion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((SOURCE/'3ds_port/build/school-completion/manifest.json').read_text())
assert manifest['build']=='school-content-src-aca939610f4f292b'
assert manifest['scope']=='INTERNAL_ELF_NOT_HARDWARE_CANDIDATE'
assert sha(SOURCE/'3ds_port/build/school-completion/school-content.elf')==manifest['elf_sha256']
for name in ('3ds_port/build','3ds_port/build-game','pc_port/PsyCross','assets','asm'):
    source=SOURCE/name
    if source.exists():
        shutil.copytree(source,ROOT/name,dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.git','__pycache__','*.3dsx'))
data=ROOT/'sh1_data'
if not data.exists():data.symlink_to(SOURCE/'sh1_data',target_is_directory=True)
print('Prepared private offline objects and read-only test disc reference; no game candidate')
