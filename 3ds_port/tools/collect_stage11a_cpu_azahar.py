"""Boot/Title evidence only. NDSP is unavailable here as in the preserved F1 run."""
import hashlib,json,shutil
from pathlib import Path
PORT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
run=read(PORT/'build/azahar/last-run.json');assert run['build_identity']=='stage11a-cpu-B-src-8c51d74ee1feb7e0'
(PORT/'reports/stage11a-cpu-B-azahar-run.json').write_text(json.dumps(run,indent=2)+'\n')
shutil.copyfile(Path(run['launched']).parent/'stage4_status.txt',PORT/'reports/stage11a-cpu-B-azahar-status.txt')
baseline=PORT/'build/azahar/runs/20261028-031704-876/stage4_status.txt'
shutil.copyfile(baseline,PORT/'reports/stage11a-cpu-azahar-baseline-F1.txt')
def status(p):return dict(line.split('=',1) for line in p.read_text(encoding='utf-8-sig').splitlines() if '=' in line)
previous=status(baseline);proof=[]
for label in ('A','B'):
 run=read(PORT/('reports/stage11a-cpu-'+label+'-azahar-run.json'))
 file=PORT/('reports/stage11a-cpu-'+label+'-azahar-status.txt');data=status(file)
 candidate=read(PORT/('build/stage11a-cpu-'+label+'/manifest.json'))
 assert run['build_identity']==candidate['build'] and run['build_sha256']==candidate['sha256'] and run['result']=='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'
 assert data['build']==candidate['build'] and data['first_failure']=='0' and data['report_complete']=='1'
 assert data['audio_ndsp_result']==previous['audio_ndsp_result']=='-662657030' and data['audio_started']=='0'
 proof.append(dict(label=label,run=run,report_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),first_failure=0,
  report_complete=True,audio_started=False,ndsp_result=int(data['audio_ndsp_result'])))
result=dict(status='BOOT_TITLE_REPORT_PASS_AUDIO_UNAVAILABLE',scope=__doc__,candidates=proof,
 previous_F1_report_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),previous_F1_ndsp_result=int(previous['audio_ndsp_result']),
 audio_validated=False,affinity_exercised=False,visual_acceptance=False,hardware_accepted=False)
(PORT/'reports/stage11a-cpu-azahar.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],affinity_exercised=False,hardware_accepted=False)))
