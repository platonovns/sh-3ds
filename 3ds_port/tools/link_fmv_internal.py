"""Read-only accepted-object closure check. Never creates a 3DSX or publishes."""
import hashlib,json,shlex,subprocess,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'3ds_port';O=R.parent/'silent-hill-decomp';B=P/'build/fmv-arm'
sdkroot=R.parent/'.toolchain/rootfs/opt/devkitpro'
manifest=json.loads((O/'3ds_port/build/stage11a-cpu-B/manifest.json').read_text())['source_provenance']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=B/'accepted-objects';base.mkdir(exist_ok=True)
archive=O/'3ds_port/baselines/stage11a-cpu-freeze-candidate-8c51d74ee1feb7e0.zip'
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        if name.startswith('3ds_port/build/stage11a-cpu-B/') and name.endswith('.o'):
            (base/Path(name).name).write_bytes(z.read(name))
linked=[];evidence={}
for name,expected in manifest['base_objects'].items():
    p=Path(name);assert sha(p)==expected,'Accepted base object changed: '+name
    candidate=base/p.name
    if candidate.exists():p=candidate
    if p.stem in ('main_game','game_audio_ndsp','stream','psx_disc'):p=B/p.name
    linked.append(p);evidence[str(p)]=sha(p)
for name in ['game_cpu_recorder','stage11a_perf','stage11a_lifetime','stage11a_alloc','stage11a_pitch_trace']:
    p=base/(name+'.o');assert p.exists();linked.append(p);evidence[str(p)]=sha(p)
for name in ['game_fmv','fmv_stream','fmv_mdec']:
    p=B/(name+'.o');linked.append(p);evidence[str(p)]=sha(p)
ld=shlex.split(manifest['flags'][2]);ld=[v.replace(str(O/'3ds_port/silenthill_game.map'),str(B/'integration-internal.map')) for v in ld]
wrappers=['malloc','calloc','realloc','free','memalign','linearAlloc','linearMemAlign','linearFree','vramAlloc','vramAllocAt','vramMemAlign','vramMemAlignAt','vramFree']
ld+=['-Wl,'+','.join('--wrap='+w for w in wrappers)]
elf=B/'integration-internal.elf'
cmd=[str(sdkroot/'devkitARM/bin/arm-none-eabi-g++'),*ld,*map(str,linked),'-L'+str(sdkroot/'libctru/lib'),'-lcitro3d','-lctru','-lm','-o',str(elf)]
r=subprocess.run(cmd,capture_output=True,text=True);(B/'link.log').write_text(r.stdout+r.stderr)
if r.returncode:print(r.stdout+r.stderr);r.check_returncode()
nm=subprocess.check_output([str(sdkroot/'devkitARM/bin/arm-none-eabi-nm'),'-u',str(elf)],text=True)
assert not any(line.split()[0] not in ('w','v') for line in nm.splitlines() if line.strip()),nm
report=dict(status='PASS',scope=__doc__,hardware_candidate=False,published=False,elf_sha256=sha(elf),objects=evidence)
(P/'reports/fmv-internal-link.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: complete internal ELF link; no 3DSX and no publication')
