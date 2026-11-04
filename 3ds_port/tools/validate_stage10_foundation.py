"""Run bounded Stage 10 foundation and accepted baseline CPU regressions."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
p=Path(__file__).resolve().parents[1];results=[]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--retry-failed',action='store_true')
ap.add_argument('--rerun',action='append',default=[]);args=ap.parse_args()
elfsha=hashlib.sha256((p/'silenthill_game.elf').read_bytes()).hexdigest()
previous={}
if args.retry_failed:
    prior=json.loads((p/'reports/stage10-foundation-regressions.json').read_text())
    assert prior['elf_sha256']==elfsha,'Cannot reuse checks from a different ELF'
    previous={r['test']:r for r in prior['tests'] if r['status']=='PASS' and r['test'] not in args.rerun}
tests=[('test_stage10_host_profile.py',False),('test_stage10_cache.py',False),
    ('test_stage10_r6_readback.py',False),('test_stage10_r6_decode.py',False),('test_stage10_r6_feedback_decode.py',False),
    ('test_stage10_renderer_host.py',False),('test_stage10_status_arm.py',True),
    ('test_stage10_polyline_arm.py',True),('test_stage10_packet_arm.py',True),('test_stage10_lens_arm.py',True),('audit_stage10_status_sampling.py',False),('audit_stage10_weapon_table.py',True),
    ('test_stage10_modern_arm.py',True),('test_stage10_settings.py',False),
    ('audit_stage10_air_state.py',True),('audit_stage10_status_glyphs.py',True),
    ('test_stage10_transition_arm.py',True),('test_stage10_particle_arm.py',True),
    ('test_stage10_boot_warning_arm.py',True),('test_stage10_pause_stress.py',True),
    ('test_stage10_original_pause_arm.py',True),
    ('test_stage8_r2_gpu_arm.py',True),('test_stage8_warmboot_arm.py',True),
    ('test_stage8_combat_arm.py',True),('test_stage7_tmd_arm.py',True),
    ('test_stage6_death.py',True),
    ('test_stage7_save_arm.py',True),('test_stage7_card.py',False),
    ('test_stage9_audio_arm.py',False),('test_stage10_gate_audio_arm.py',False),
    ('test_stage10_profile_pcm_arm.py',False),('test_stage9_ndsp_arm.py',False),
    ('test_stage9_r6_xa_arm.py',False),('test_stage9_r6_diagnostics_arm.py',False)]
for name,isolate_audio in tests:
    if name in previous:
        results.append(previous[name]);continue
    begin=time.monotonic();env=dict(os.environ)
    if isolate_audio:env['SH_STAGE9_REGRESSION']='1'
    else:env.pop('SH_STAGE9_REGRESSION',None)
    log=p/'reports'/('stage10-regression-'+name.removesuffix('.py')+'.log')
    with log.open('w') as out:
        run=subprocess.run([sys.executable,str(p/'tools'/name)],stdout=out,stderr=subprocess.STDOUT,env=env)
    row=dict(test=name,status='PASS' if run.returncode==0 else 'FAIL',
        seconds=round(time.monotonic()-begin,2),log=log.name)
    results.append(row);print(json.dumps(row),flush=True)
report=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',tests=results,
    elf_sha256=elfsha,hardware_accepted=False)
assert elfsha==hashlib.sha256((p/'silenthill_game.elf').read_bytes()).hexdigest(),'ELF changed during validation'
(p/'reports/stage10-foundation-regressions.json').write_text(json.dumps(report,indent=2)+'\n')
sys.exit(report['status']!='PASS')
