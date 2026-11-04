"""Recorder input guards, bounded cache churn, disposable cross-process card writes."""
import json,subprocess
from pathlib import Path
PORT=Path(__file__).resolve().parents[1]
fixture=PORT/'tools/test_stage11a_tracefix_host.py'
source=fixture.read_text().split("bench=DEST/'bench.cpp'")[0]
source=source.replace('build/stage11a-tracefix-host','build/stage11a-cpu-host-controls')
source=source.replace("'-DSH_STAGE11A_TRACEFIX=1'","'-DSH_STAGE11A_TRACEFIX=1','-DSH_STAGE11A_CPU=1'")
ns={'__file__':str(fixture),'__name__':'cpu_input_safety'};exec(compile(source,str(fixture),'exec'),ns)
input_result=ns['run'].stdout.strip()
folder=PORT/'build/stage11a-cpu-host';exe=folder/'cache'
subprocess.run(['gcc','-std=c11','-O2','-fsanitize=address,undefined','-DSH_STAGE11A_LIFETIME=1','-DSH_CPU_AUDIT_RECORDER=1','-I'+str(PORT/'include'),
 str(PORT/'tests/game_texture_cache_test.c'),str(PORT/'source/game_texture_cache.c'),'-o',str(exe)],check=True)
run=subprocess.run([str(exe)],capture_output=True,text=True,check=True);assert not run.stderr and 'PASS' in run.stdout
card=PORT/'tools/test_stage7_card.py';source=card.read_text().replace('stage7-card-tests.json','stage11a-cpu-card.json')
exec(compile(source,str(card),'exec'),{'__file__':str(card),'__name__':'cpu_card_safety'})
report=dict(status='PASS',scope=__doc__,input=input_result,cache=run.stdout.strip(),card_report='stage11a-cpu-card.json')
(PORT/'reports/stage11a-cpu-safety.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
