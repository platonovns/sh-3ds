"""Bind lifetime instrumentation, tests and delivery; never mark baseline stable."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from stage11a_baseline import verify
PORT=Path(__file__).resolve().parents[1]
ROOT=PORT.parent
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def local(path):
    return Path(path[5].upper()+':/'+path[7:]) if path.startswith('/mnt/') else Path(path)
def main():
    verify();d=PORT/'build/stage11a-lifetime';candidate=read(d/'manifest.json')
    assert sha(d/'silenthill_stage11a_lifetime.3dsx')==candidate['sha256']
    assert sha(d/'silenthill_stage11a_lifetime.elf')==candidate['elf_sha256']
    for name,expected in candidate['source_provenance']['sources'].items():assert sha(ROOT/name)==expected,name
    for name,expected in candidate['source_provenance']['base_objects'].items():assert sha(local(name))==expected,name
    prior=read(PORT/'reports/stage11a-0-package.json');assert sha(ROOT/prior['archive'])==prior['sha256']
    for name in ('stage11a-lifetime-host','stage11a-lifetime-pcm','stage11a-lifetime-arm','stage11a-lifetime-xa-arm','stage11a-lifetime-analysis-tests'):
        report=read(PORT/'reports'/(name+'.json'));assert report['status']=='PASS',name
        if name.endswith('-arm'):assert report['elf_sha256']==candidate['elf_sha256']
        for f,expected in report.get('inputs',{}).items():assert sha(ROOT/f)==expected,f
    delivery=read(PORT/'reports/stage11a-lifetime-http.json')
    assert delivery['verified'] and delivery['sha256']==candidate['sha256'] and delivery['source_build']==candidate['build']
    run=read(PORT/'build/azahar/last-run.json')
    assert run['build_sha256']==candidate['sha256'] and run['build_identity']==candidate['build']
    assert run['result']=='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'
    title=Path(run['launched']).parent/'stage4_status.txt'
    values=dict(line.split('=',1) for line in title.read_text().splitlines() if '=' in line)
    assert values['build']==candidate['build'] and values['first_failure']=='0' and values['report_complete']=='1'
    out=PORT/'reports/stage11a-lifetime-title';out.mkdir(exist_ok=True)
    shutil.copy2(title,out/'status.txt');(out/'run.json').write_text(json.dumps(run,indent=2)+'\n')
    for path,identity,expected in [
        ('build/hardware-stage10-r6-cpu-audit/silenthill_game.3dsx','stage10.0-src-ca390b6b8b45e70c','43462215152cf6405aa0437ab4bbee6fd0fe27cc2ee1c339dfa4cb4f3cf42bd6'),
        ('build/hardware-stage10-cpu-recorder/silenthill_cpu_recorder.3dsx','stage10.0-cpurec-src-a5ed13f76dac9640','95fe9e0030bb29fb28649287ee68989a6a050bfc5a3fc8061a7ce25e16900fd3')]:
        assert sha(PORT/path)==expected and identity.encode() in (PORT/path).read_bytes()
    size_rows=[list(map(int,line.split()[:3])) for line in candidate['elf_size'].splitlines()[1:]]
    static_delta={k:size_rows[0][i]-size_rows[1][i] for i,k in enumerate(('text','data','bss'))}
    receipt=dict(status='READY_FOR_LIFETIME_HARDWARE_INVESTIGATION',build=candidate['build'],sha256=candidate['sha256'],
        size=candidate['size'],elf_sha256=candidate['elf_sha256'],normal_control_collection='ON_HOLD',
        baseline_stability='UNRESOLVED',spu_optimization='NOT_STARTED',core2_experiment='NOT_STARTED',
        actual_hardware_owner='UNKNOWN_PENDING_FOUR_WINDOWS',hardware_reproduced_by_agent=False,
        existing_hardware_observation='User confirms degradation on prior CONTROL 3dsx-d2cd3cc: school slowdown, persistence into warm New Game, recovery after process restart',
        affected_hardware_build='stage11a.0-control-profile-src-91ca2ef7a9630b69',
        affected_hardware_sha256='d2cd3cc9054abdfdcecc2121d0d5fd0ea56707ba786ffb714991895fd8585800',
        demonstrated_host_lead='Frozen SPU silent nonzero-pitch work scales with voice population at constant object size and zero PCM',
        memory_leak_proven=False,diagnostics_exonerated=False,state_reset_or_gameplay_fix_added=False,
        new_linear_allocations=0,new_vram_allocations=0,
        elf_static_delta_vs_frozen_recorder=static_delta,
        automated_checks=['bounded observer/input ASan+UBSan','256 byte-exact PCM/state checkpoints','linked ARM SFX/NDSP','linked ARM XA allocation/queue/close','synthetic four-window analysis','Azahar Boot/Title'],
        stage10_preserved=True,prior_control_preserved=True,golden_card_unchanged=True,delivery=delivery,
        hardware_instructions='3ds_port/reports/STAGE11A-LIFETIME-HARDWARE-RU.md')
    result=PORT/'reports/stage11a-baseline-validity.json';result.write_text(json.dumps(receipt,indent=2)+'\n')
    archive=PORT/'baselines'/('stage11a-lifetime-'+candidate['build'].rsplit('-',1)[1]+'.zip')
    assert not archive.exists(),'Never overwrite preserved instrumentation evidence'
    paths={ROOT/name for name in candidate['source_provenance']['sources']}
    paths.update(f for f in (PORT/'tools').glob('*lifetime*') if f.is_file())
    paths.update(f for f in (PORT/'tests').glob('*lifetime*') if f.is_file())
    paths.add(PORT/'tests/lifetime_mock/3ds.h')
    paths.update(f for f in (PORT/'reports').glob('stage11a-lifetime-*.json') if f.is_file() and f.name!='stage11a-lifetime-package.json')
    paths.update((result,out/'status.txt',out/'run.json',PORT/'reports/STAGE11A-LIFETIME-HARDWARE-RU.md',
                  ROOT/'docs/3ds-stage11a-lifetime-investigation.md',ROOT/'docs/3ds-stage11a-handoff.md',
                  PORT/'tools/run_azahar.ps1',PORT/'build/stage11a-baseline/starting-source.zip'))
    paths.update(f for f in d.rglob('*') if f.is_file() and f.suffix!='.o')
    inventory=[dict(path=f.relative_to(ROOT).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(paths)]
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for row in inventory:z.write(ROOT/row['path'],row['path'],compress_type=zipfile.ZIP_STORED if row['path'].endswith('.zip') else zipfile.ZIP_DEFLATED)
        z.writestr('files.json',json.dumps(inventory,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        for row in inventory:
            with z.open(row['path']) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
    package=dict(archive=archive.relative_to(ROOT).as_posix(),sha256=sha(archive),bytes=archive.stat().st_size,files=len(inventory),
                 hardware_accepted=False,stage11a_frozen=False,baseline_stability_unresolved=True)
    (PORT/'reports/stage11a-lifetime-package.json').write_text(json.dumps(package,indent=2)+'\n')
    print(json.dumps(receipt,indent=2));print(json.dumps(package,indent=2))
if __name__=='__main__':main()
