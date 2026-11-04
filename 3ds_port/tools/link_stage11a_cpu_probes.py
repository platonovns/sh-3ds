"""Internal nearby-scene ELF only: final CPU backend plus preserved scene-entry objects."""
import hashlib,json,os,re,shlex,subprocess
from pathlib import Path
PORT=Path(__file__).resolve().parents[1]
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
raw=subprocess.check_output(['make','-C',str(PORT),'-f','Makefile.game','-pn'],text=True,stderr=subprocess.DEVNULL)
objects=dict(re.findall(r'^(\w+) := (.*)$',raw,re.M))['OFILES'].split()
cpu=PORT/'build/stage11a-cpu-A'
flags=(PORT/'build-game/flags').read_text().splitlines();sdk=shlex.split(flags[1])
ctrulib=Path(next(v[2:] for v in sdk if v.startswith('-I') and v.endswith('/libctru/include'))).parent
records=[]
for scene in (1,3):
    old=PORT/('build/stage10-dev-scene-'+str(scene));dest=PORT/('build/stage11a-cpu-probe-'+str(scene));dest.mkdir(exist_ok=True)
    replacements={str(PORT/'build-game'/p.name):p for p in cpu.glob('*.o')}
    for name in ('bodyprog_8005E0DC','game_boot','game_main','game_sys_states','title'):
        for obj in objects:
            if Path(obj).name==name+'.o' and (old/(name+'.o')).exists():replacements[obj]=old/(name+'.o')
    linked=[str(replacements.get(n,n)) for n in objects]+[str(cpu/(name+'.o')) for name in
        ('game_cpu_recorder','stage11a_perf','stage11a_lifetime','stage11a_alloc','stage11a_pitch_trace')]+[str(old/'game_diagnostics.o')]
    ld=[v.replace(str(PORT/'silenthill_game.map'),str(dest/'probe.map')) for v in shlex.split(flags[2])]
    wrappers=('malloc','calloc','realloc','free','memalign','linearAlloc','linearMemAlign','linearFree','vramAlloc','vramAllocAt','vramMemAlign','vramMemAlignAt','vramFree')
    ld+=['-Wl,'+','.join('--wrap='+w for w in wrappers)]
    elf=dest/'probe.elf';subprocess.run([prefix+'g++',*ld,*linked,'-L'+str(ctrulib/'lib'),'-lcitro3d','-lctru','-lm','-o',str(elf)],check=True)
    assert 'Game3ds_DevEnter' in subprocess.check_output([prefix+'nm',str(elf)],text=True),'Scene entry was garbage-collected: wrong object replacement'
    record=dict(scope='INTERNAL_NEARBY_SCENE_PROBE_NEVER_HARDWARE_BUILD',scene=scene,
        elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),objects={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in linked})
    (dest/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');records.append({k:v for k,v in record.items() if k!='objects'})
print(json.dumps(records,indent=2))
