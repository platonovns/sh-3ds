"""Compile a complete decompiled overlay using the existing resident-map ABI.
No game dispatch is enabled until the native closure has no missing symbols.
"""
import argparse,json,os,shlex,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
ap=argparse.ArgumentParser();ap.add_argument('map');a=ap.parse_args()
assert a.map in ('map0_s02','map1_s00')
dest=p/'build'/('stage10-'+a.map+'-audit');dest.mkdir(exist_ok=True)
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])+['-D'+a.map.upper(),'-DSH_MAP_NAME='+a.map]
sources=sorted((root/'src/maps'/a.map).glob('*.c'))
sources.append(root/'pc_port/build_gen/extracted_data'/(a.map+'_extracted_data.c'))
objects=[];results=[]
for source in sources:
    obj=dest/(source.stem+'.o');log=dest/(source.stem+'.log')
    with log.open('w') as out:run=subprocess.run([prefix+'gcc',*flags,'-c',str(source),'-o',str(obj)],stdout=out,stderr=subprocess.STDOUT)
    results.append(dict(source=str(source.relative_to(root)),status=run.returncode,log=str(log.relative_to(p))))
    print(json.dumps(results[-1]),flush=True)
    if not run.returncode:objects.append(str(obj))
missing=[];native_status=None
if len(objects)==len(sources):
    combined=dest/(a.map+'.native.o')
    subprocess.run([prefix+'g++','-r','-nostdlib',*shlex.split('-march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft'),*objects,'-o',str(combined)],check=True)
    run=subprocess.run(['python3',str(p/'tools/native_overlay.py'),'--object',str(combined),'--map',a.map],capture_output=True,text=True)
    native_status=run.returncode;print(run.stdout+run.stderr,flush=True)
    if not run.returncode:
        listing=subprocess.check_output([prefix+'nm','-g',str(combined)],text=True)
        unresolved={s[1] for line in listing.splitlines() if len(s:=line.split())==2 and s[0]=='U'}
        # The normal ELF has discarded unused generic engine routines. They
        # are still present in production OFILES and become live with a new map.
        base=subprocess.check_output([prefix+'nm','-g',*[str(o) for o in (p/'build-game').rglob('*.o')]],text=True)
        provided={s[2] for line in base.splitlines() if len(s:=line.split())==3}
        aliases={line.split()[0] for line in combined.with_suffix('.ld').read_text().splitlines() if ' = ' in line}
        missing=sorted(unresolved-provided-aliases)
report=dict(map=a.map,status='PASS' if len(objects)==len(sources) and native_status==0 and not missing else 'FAIL',compile=results,missing=missing,native_status=native_status)
(p/'reports'/('stage10-r5-'+a.map+'-audit.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status=report['status'],missing=missing)),flush=True)
