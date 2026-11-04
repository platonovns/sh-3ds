"""Source/data/native import closure and normal Makefile dry-run, no build."""
from pathlib import Path
import hashlib,json,os,re,subprocess
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
BUILD=PORT/'build/alchemilla';manifest=json.loads((BUILD/'manifest.json').read_text())
maps=['map3_s%02d'%i for i in range(7)]
assert manifest['status']=='PASS' and manifest['maps']==maps
assert not manifest['published'] and not manifest['hardware_accepted']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(ROOT/n)==h for n,h in manifest['sources'].items())
assert all(sha(ROOT/n)==h for n,h in manifest['linked_objects'].items())
mk=(PORT/'alchemilla_sources.mk').read_text();rows=[]
for name in maps:
    expected={p.name for p in (ROOT/'src/maps'/name).glob('*.c')}
    m=re.search(r'call SCHOOL_OVERLAY,'+name+','+name.upper()+r',([^)]*)',mk)
    assert m and set(m[1].split())==expected,(name,expected)
    data=json.loads((PORT/'reports'/('stage6-'+name+'-symbols.json')).read_text())
    config=(ROOT/data['config']).read_text()
    for symbol in data['aliases']:
        declaration=re.search(r'^'+re.escape(symbol)+r'\s*=.*$',config,re.M)
        assert not declaration or 'type:func' not in declaration[0],(name,symbol)
    assert 'g_MapEventFuncs' in data['defined']
    assert 'g_MapOverlayHeader_'+name in data['defined']
    assert all(('src/maps/'+name+'/'+s) in manifest['sources'] for s in expected)
    assert 'pc_port/build_gen/extracted_data/'+name+'_extracted_data.c' in manifest['sources']
    rows.append(dict(map=name,source_units=len(expected)+1,data_aliases=len(data['aliases']),callable_aliases=0))
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
elf=BUILD/'alchemilla-content.elf'
undefined=subprocess.check_output([prefix+'nm','--undefined-only',str(elf)],text=True)
weak=[]
for line in undefined.splitlines():
    typ,symbol=line.split()
    assert typ=='w' and symbol in ('__deregister_frame_info','__gnu_Unwind_Find_exidx',
        '__register_frame_info','__syscall_tls_create','__syscall_tls_delete',
        '__syscall_tls_get','__syscall_tls_set','userAppExit','userAppInit'),line
    weak.append(symbol)
targets=[str(PORT/'build-game'/(n+'.native.o')) for n in maps]
p=subprocess.run(['make','-f','Makefile.game','-n',*targets],cwd=PORT,capture_output=True,text=True)
(BUILD/'make-dry-run.log').write_text(p.stdout+p.stderr)
assert p.returncode==0,p.stderr
assert 'after_build.py' not in p.stdout and '3dsxtool ' not in p.stdout
for n in maps:assert '-D'+n.upper() in p.stdout and '--map '+n in p.stdout
size=subprocess.check_output([prefix+'size',str(PORT/'build/post-school/post-school-content.elf'),str(elf)],text=True)
(BUILD/'size.txt').write_text(size)
report=dict(status='PASS',maps=rows,unresolved_callable_imports=0,all_map_sources_and_extracted_data_hashed=True,
    optional_sdk_weak_symbols=weak,
    frozen_linked_object_hashes_verified=True,make_native_targets_dry_run='PASS',make_dry_run_executed_build=False,
    elf_sha256=sha(elf),size_output=size,hardware_candidate_created=False,published=False)
(PORT/'reports/alchemilla-closure.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
