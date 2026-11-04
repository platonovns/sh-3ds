"""Compile the real MAP2_S00 closure separately before enabling resident dispatch."""
import json,os,shlex,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent;dest=p/'build/stage10-map2-audit';dest.mkdir(exist_ok=True)
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])+['-DMAP2_S00','-DSH_MAP_NAME=map2_s00']
sources=[root/'src/maps/map2_s00'/s for s in ('player.c','map2_s00.c','map2_s00_anim_info.c',
    'map2_s00_events_data.c','map2_s00_header.c','Chara_AirScreamer.c','Chara_Groaner.c','particle.c')]
sources.append(root/'pc_port/build_gen/extracted_data/map2_s00_extracted_data.c')
objects=[];results=[]
for source in sources:
    obj=dest/(source.stem+'.o');log=dest/(source.stem+'.log')
    with log.open('w') as out:run=subprocess.run([prefix+'gcc',*flags,'-c',str(source),'-o',str(obj)],stdout=out,stderr=subprocess.STDOUT)
    results.append(dict(source=str(source.relative_to(root)),status=run.returncode,log=str(log.relative_to(p))))
    if run.returncode:print(json.dumps(results[-1]),flush=True)
    else:objects.append(str(obj))
if len(objects)==len(sources):
    combined=dest/'map2_s00.native.o'
    subprocess.run([prefix+'g++','-r','-nostdlib',*shlex.split('-march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft'),*objects,'-o',str(combined)],check=True)
    run=subprocess.run(['python3',str(p/'tools/native_overlay.py'),'--object',str(combined),'--map','map2_s00'],capture_output=True,text=True)
    print(run.stdout+run.stderr,flush=True)
    if not run.returncode:
        listing=subprocess.check_output([prefix+'nm','-g',str(combined)],text=True)
        unresolved=[s[1] for line in listing.splitlines() if len(s:=line.split())==2 and s[0]=='U']
        base=subprocess.check_output([prefix+'nm','-g',str(p/'silenthill_game.elf')],text=True)
        provided={s[2] for line in base.splitlines() if len(s:=line.split())==3}
        aliases={line.split()[0] for line in combined.with_suffix('.ld').read_text().splitlines() if ' = ' in line}
        missing=sorted(set(unresolved)-provided-aliases)
        print(json.dumps(dict(unresolved=len(unresolved),missing=missing),indent=2))
        (dest/'missing.json').write_text(json.dumps(missing,indent=2)+'\n')
(p/'reports/stage10-map2-compile-audit.json').write_text(json.dumps(results,indent=2)+'\n')
