"""Validate final tracefix image/proofs and preserve an exclusive evidence ZIP."""
import hashlib,json,shutil,zipfile
from pathlib import Path
from stage11a_baseline import verify
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent;DEST=PORT/'build/stage11a-tracefix'
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def sha(f):
    with f.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def local(s):return Path(s[5].upper()+':/'+s[7:]) if s.startswith('/mnt/') else Path(s)

def main():
    verify();m=read(DEST/'manifest.json')
    assert sha(DEST/'silenthill_stage11a_tracefix.3dsx')==m['sha256']
    assert sha(DEST/'silenthill_stage11a_tracefix.elf')==m['elf_sha256']
    for name,expected in m['source_provenance']['sources'].items():assert sha(ROOT/name)==expected,name
    for name,expected in m['source_provenance']['base_objects'].items():assert sha(local(name))==expected,name
    previous=read(PORT/'reports/stage11a-lifetime-package.json');assert sha(ROOT/previous['archive'])==previous['sha256']
    proofs={}
    for name in ('pcm','host','arm','xa-arm'):
        report=read(PORT/'reports'/('stage11a-tracefix-'+name+'.json'));assert report['status']=='PASS',name
        if name in ('arm','xa-arm'):assert report['elf_sha256']==m['elf_sha256']
        for f,expected in report.get('inputs',{}).items():assert sha(ROOT/f)==expected,f
        proofs[name]=report
    assert proofs['arm']['whole_native_core_byte_exact']
    assert proofs['xa-arm']['F1_enabled'] and proofs['xa-arm']['PCM_matches_preserved_XA_KDT_fixture']
    delivery=read(PORT/'reports/stage11a-tracefix-http.json')
    assert delivery['verified'] and delivery['sha256']==m['sha256'] and delivery['size']==m['size']
    assert delivery['source_build']==m['build']
    run=read(PORT/'build/azahar/last-run.json')
    assert run['build_sha256']==m['sha256'] and run['build_identity']==m['build']
    assert run['result']=='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'
    title=Path(run['launched']).parent/'stage4_status.txt'
    data=dict(line.split('=',1) for line in title.read_text().splitlines() if '=' in line)
    assert data['build']==m['build'] and data['first_failure']=='0' and data['report_complete']=='1'
    folder=PORT/'reports/stage11a-tracefix-title';folder.mkdir(exist_ok=True)
    shutil.copy2(title,folder/'status.txt');(folder/'run.json').write_text(json.dumps(run,indent=2)+'\n')
    validation=dict(status='READY_FOR_HARDWARE_TRACE_AND_F0_F1_AB',build=m['build'],sha256=m['sha256'],size=m['size'],elf_sha256=m['elf_sha256'],
        default_fix_mode=0,fix_toggle='SELECT+LEFT between recordings',record_toggle='SELECT+DOWN',
        oracle_checkpoints=1984,oracle_bytes_per_mode=1077117648,
        native_arm_core_byte_exact=True,original_xa_requests=726,retail_sfx_cases=9,
        trace_scope_synthetic_arm_verified=True,hardware_school_writer_confirmed=False,
        hardware_F1_performance_measured=False,hardware_audio_listening_pending=True,
        fix_accepted=False,baseline_stable=False,normal_control='ON_HOLD',core2='NOT_STARTED',
        pitch_writes_suppressed=False,decoder_state_skipped=False,title_reset_added=False,
        decoder_grouping='Only identical unkeyed no-override machines, representative advances at original per-sample RAM/reverb chronology',
        stage10_preserved=True,prior_control_and_lifetime_preserved=True,golden_card_unchanged=True,
        new_heap_linear_vram_allocations=0,new_threads=0,
        azahar_scope='Structured Boot/Title status only; no hardware/FPS/listening/visual acceptance',
        instructions='3ds_port/reports/STAGE11A-TRACEFIX-HARDWARE-RU.md',delivery=delivery)
    # 256 original plus 72*24 targeted checkpoints, not a claimed exhaustive proof.
    assert validation['oracle_checkpoints']==256+72*24
    assert validation['oracle_bytes_per_mode']==141168224+935949424
    report_path=PORT/'reports/stage11a-tracefix-validation.json';report_path.write_text(json.dumps(validation,indent=2)+'\n')
    paths={ROOT/f for f in m['source_provenance']['sources']}
    paths.update(f for f in DEST.rglob('*') if f.is_file() and f.suffix!='.o')
    paths.update((PORT/'tools').glob('*tracefix*'))
    paths.add(PORT/'tools/analyze_stage11a_lifetime.py')
    paths.update(f for f in (PORT/'reports').glob('stage11a-tracefix-*.json') if f.name!='stage11a-tracefix-package.json')
    paths.update((PORT/'tests').glob('*tracefix*'))
    paths.update((folder/'status.txt',folder/'run.json',ROOT/'docs/3ds-stage11a-tracefix-candidate.md',
        ROOT/'docs/3ds-stage11a-handoff.md',PORT/'reports/STAGE11A-TRACEFIX-HARDWARE-RU.md',PORT/'tools/run_azahar.ps1',
        PORT/'build/stage11a-baseline/starting-source.zip',PORT/'baselines/stage11a-lifetime-hardware-20261028-011-016.zip'))
    inventory=[dict(path=f.relative_to(ROOT).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(paths) if f.is_file()]
    archive=PORT/'baselines'/('stage11a-tracefix-'+m['build'].rsplit('-',1)[1]+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for row in inventory:z.write(ROOT/row['path'],row['path'],compress_type=zipfile.ZIP_STORED if row['path'].endswith('.zip') else zipfile.ZIP_DEFLATED)
        z.writestr('files.json',json.dumps(inventory,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        for row in inventory:
            with z.open(row['path']) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']
    result=dict(archive=archive.relative_to(ROOT).as_posix(),sha256=sha(archive),bytes=archive.stat().st_size,files=len(inventory),fix_accepted=False,baseline_stable=False)
    (PORT/'reports/stage11a-tracefix-package.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(validation,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
