"""Link a hardware CPU-recorder diagnostic without rebuilding/changing normal R6."""
import hashlib,json,os,re,shlex,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1]
dest=p/'build/stage10-cpu-recorder';dest.mkdir(exist_ok=True)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
base=p/'silenthill_game.elf'
assert sha(base)=='8c41fc2a3281f71bb3583b058c7d56ce2e3e6ae59667c4a217262b96807cd981','Unexpected normal R6 base'
flags=(p/'build-game/flags').read_text().splitlines()
engine,sdk,ld=map(shlex.split,flags[:3])
assert not any('SH_CPU_AUDIT_RECORDER' in x for x in engine+sdk)
raw=subprocess.check_output(['make','-C',str(p),'-f','Makefile.game','-pn'],text=True,stderr=subprocess.DEVNULL)
variables=dict(re.findall(r'^(\w+) := (.*)$',raw,re.M))
objects=variables['OFILES'].split();original={name:sha(Path(name)) for name in objects}
sources={n:p/'source'/n for n in ('main_game.c','game_cpu_audit.c','game_native.c','game_profile.c','game_cpu_recorder.c')}
digest=hashlib.sha256(base.read_bytes())
for f in [*sources.values(),*sorted((p/'include').glob('*.h')),Path(__file__)]:
    digest.update(f.name.encode()+f.read_bytes())
identity='stage10.0-cpurec-src-'+digest.hexdigest()[:16]
(dest/'recorder_identity.h').write_text('#define SH_BUILD_ID "'+identity+'"\n')
main=sources['main_game.c'].read_text().replace('"build_identity.h"','"recorder_identity.h"')
(dest/'main_game.c').write_text(main);sources['main_game.c']=dest/'main_game.c'
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
replacements={}
for name,source in sources.items():
    ff=engine if name in ('game_native.c','game_profile.c') else sdk
    target=dest/(source.stem+'.o')
    subprocess.run([prefix+'gcc',*ff,'-DSH_CPU_AUDIT_RECORDER=1','-I'+str(dest),
                    '-c',str(source),'-o',str(target)],check=True)
    replacements[str(p/'build-game'/(source.stem+'.o'))]=str(target)
objects=[replacements.get(n,n) for n in objects]+[str(dest/'game_cpu_recorder.o')]
ld=[v.replace(str(p/'silenthill_game.map'),str(dest/'recorder.map')) for v in ld]
ctrulib=Path(next(v[2:] for v in sdk if v.startswith('-I') and v.endswith('/libctru/include'))).parent
elf=dest/'silenthill_cpu_recorder.elf'
subprocess.run([prefix+'g++',*ld,*objects,'-L'+str(ctrulib/'lib'),'-lcitro3d','-lctru','-lm','-o',str(elf)],check=True)
assert identity.encode() in elf.read_bytes()
assert all(sha(Path(n))==h for n,h in original.items()),'Normal objects changed during private link'
assert sha(base)=='8c41fc2a3281f71bb3583b058c7d56ce2e3e6ae59667c4a217262b96807cd981'
binary=dest/'silenthill_cpu_recorder.3dsx'
subprocess.run(['3dsxtool',str(elf),str(binary),'--smdh='+str(p/'silenthill_game.smdh')],check=True)
# Every successful new hardware game build is delivered immediately.
subprocess.run(['python3',str(p/'dev_server/after_build.py'),str(binary)],check=True)
record=dict(variant='CPU_AUDIT_RECORDER_ONLY',build=identity,size=binary.stat().st_size,
    sha256=sha(binary),elf_sha256=sha(elf),normal_elf_sha256=sha(base),
    normal_3dsx_sha256=sha(p/'silenthill_game.3dsx'),normal_objects_unchanged=True,
    automatic_scene_start=False,recorder_define='SH_CPU_AUDIT_RECORDER=1',hardware_accepted=False)
(dest/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
(p/'reports/stage10-cpu-recorder-candidate.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
