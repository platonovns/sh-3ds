"""Check Block 3 source, overlay aliases and ELF import closure; never builds 3dsx."""
from pathlib import Path
import hashlib,json,os,re,subprocess
port=Path(__file__).resolve().parents[1];root=port.parent;base=root.parent/'alchemilla-content'
build=port/'build/block3';manifest=json.loads((build/'manifest.json').read_text())
maps=[f'map4_s{i:02d}' for i in range(1,6)]
assert manifest['status']=='PASS' and manifest['maps']==maps and not manifest['published']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(root/n)==h for n,h in manifest['sources'].items())
assert all(sha(base/n)==h for n,h in manifest['base_objects'].items())
assert all(sha(root/n)==h for n,h in manifest['new_objects'].items())
assert all(sha(base/n)==h for n,h in manifest['base_scripts'].items())
assert all(sha(root/n)==h for n,h in manifest['new_linker_scripts'].items())
assert sha(base/'3ds_port/build/stage11a-cpu-B/manifest.json')==manifest['cpu_manifest_sha256']
assert sha(base/'3ds_port/build/stage11a-cpu-B/main_game.c')==manifest['base_main_sha256']
mk=(port/'block3_sources.mk').read_text();rows=[]
for name in maps:
    expected={p.name for p in (root/'src/maps'/name).glob('*.c')}
    m=re.search(r'call SCHOOL_OVERLAY,'+name+','+name.upper()+r',([^)]*)',mk)
    assert m and set(m[1].split())==expected,(name,expected)
    data=json.loads((port/'reports'/('stage6-'+name+'-symbols.json')).read_text())
    cfg=(root/data['config']).read_text()
    for symbol in data['aliases']:
        declaration=re.search(r'^'+re.escape(symbol)+r'\s*=.*$',cfg,re.M)
        assert not declaration or 'type:func' not in declaration[0],(name,symbol)
    assert 'g_MapEventFuncs' in data['defined'] and 'g_MapOverlayHeader_'+name in data['defined']
    assert all('src/maps/'+name+'/'+s in manifest['sources'] for s in expected)
    assert 'pc_port/build_gen/extracted_data/'+name+'_extracted_data.c' in manifest['sources']
    rows.append(dict(map=name,source_units=len(expected)+1,data_aliases=len(data['aliases']),callable_aliases=0))
for name,forbidden in [('map4_s03','TWINFEELER_ANIM_INFOS'),('map4_s05','FLOATSTINGER_ANIM_INFOS'),
                       ('map4_s02','GROANER_M4S02_ANIM_INFOS'),('map4_s04','LISA_ANIM_INFOS')]:
    data=json.loads((port/'reports'/('stage6-'+name+'-symbols.json')).read_text())
    assert forbidden not in data['aliases']
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-');elf=build/'block3-content.elf'
assert sha(elf)==manifest['elf_sha256']
weak=[]
for line in subprocess.check_output([prefix+'nm','--undefined-only',str(elf)],text=True).splitlines():
    typ,symbol=line.split()
    assert typ=='w' and symbol in ('__deregister_frame_info','__gnu_Unwind_Find_exidx','__register_frame_info',
                                   '__syscall_tls_create','__syscall_tls_delete','__syscall_tls_get',
                                   '__syscall_tls_set','userAppExit','userAppInit'),line
    weak.append(symbol)
report=dict(status='PASS',scope='Source units and aliases only; runtime callable-table audit is separate',maps=rows,
            unresolved_strong_imports=0,optional_sdk_weak_symbols=weak,base_objects_verified=True,
            elf_sha256=sha(elf),hardware_candidate_created=False,published=False)
(build/'closure.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
