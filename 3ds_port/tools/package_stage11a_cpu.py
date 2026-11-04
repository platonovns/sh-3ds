"""Immutable A/B evidence checkpoint after publication; preserves the inherited Git tree."""
import hashlib,json,zipfile
from pathlib import Path
from stage11a_baseline import verify
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def local(p):
 s=str(p)
 return Path(s[5].upper()+':/'+s[7:]) if s.startswith('/mnt/') else Path(s)
verify();files=set();candidates=[]
for label in ('A','B'):
 folder=PORT/('build/stage11a-cpu-'+label);manifest=read(folder/'manifest.json');candidates.append(manifest)
 assert manifest['stage11a_accepted'] is False and manifest['silent_candidate_default']==1
 binary=folder/('silenthill_stage11a_cpu_'+label+'.3dsx');elf=binary.with_suffix('.elf')
 assert sha(binary)==manifest['sha256'] and binary.stat().st_size==manifest['size'] and sha(elf)==manifest['elf_sha256']
 assert manifest['build'].encode() in binary.read_bytes()
 for name,h in manifest['source_provenance']['sources'].items():
  file=ROOT/name;assert sha(file)==h,name;files.add(file)
 assert all(sha(local(p))==h for p,h in manifest['source_provenance']['base_objects'].items())
 files.update((binary,elf,folder/'manifest.json',folder/'symbols.txt',folder/'tracefix.map'))
 files.update(folder.glob('*.compile.log'))
http=read(PORT/'reports/stage11a-cpu-http.json');assert http['default']=='A' and all(x['verified'] for x in http['candidates'])
for r,p in zip(candidates,http['candidates']):assert r['sha256']==p['manifest']['sha256']
reg=read(PORT/'reports/stage11a-cpu-regression.json');assert len(reg['cases'])==17 and all(c['status']=='PASS' for c in reg['cases']) and reg['golden_card_unchanged']
files.update((PORT/'build/stage11a-cpu/checkpoints').glob('*'))
files.update((PORT/'tools').glob('*stage11a_cpu*'))
files.update((PORT/'tools').glob('*stage11a_gte*'))
files.update((PORT/'tools').glob('classify_stage11a_cafe.py'))
files.update((PORT/'tests').glob('stage11a_*'))
files.update((PORT/'reports').glob('stage11a-cpu*.json'))
files.update((PORT/'reports').glob('stage11a-cpu*-azahar*.txt'))
files.add(PORT/'reports/stage11a-cpu-azahar-baseline-F1.txt')
files.update((PORT/'reports/stage11a-cpu-regression').glob('*'))
files.update([PORT/'reports/stage11a-cafe-classification.json',PORT/'reports/STAGE11A-CPU-MORNING-RU.md',
 ROOT/'docs/3ds-stage11a-cpu-overnight.md',ROOT/'docs/3ds-stage11a-overnight-request.md',
 ROOT/'docs/3ds-stage11a-handoff.md',ROOT/'docs/3ds-stage11b-cpu-handoff.md',PORT/'tools/analyze_stage11a_lifetime.py',PORT/'tools/analyze_stage11a_tracefix.py',PORT/'tools/run_azahar.ps1'])
files={p for p in files if p.is_file() and p.suffix!='.pyc' and p.name!='stage11a-cpu-package.json'}
inventory={p.relative_to(ROOT).as_posix():dict(size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)}
identity='-'.join(r['build'].rsplit('-',1)[1] for r in candidates)
archive=PORT/('baselines/stage11a-cpu-'+identity+'.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
 z.writestr('cpu-package-inventory.json',json.dumps(inventory,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,entry in inventory.items():assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256']
record=dict(archive=archive.relative_to(ROOT).as_posix(),size=archive.stat().st_size,sha256=sha(archive),files=len(inventory),
 candidates=[dict(build=r['build'],sha256=r['sha256'],size=r['size']) for r in candidates],stage10_preserved=True,golden_card_sha256=sha(ROOT/'sh1_data/memcard.mcr'),hardware_accepted=False)
(PORT/'reports/stage11a-cpu-package.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
