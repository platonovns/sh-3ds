"""Execute the actual Stage 11A ARM ELF: retail SFX PCM and NDSP lifecycle.

Reuses proven fixtures with SH_GAME_ELF and separate Stage 11A report paths;
does not overwrite Stage 10 reports, binaries or memory cards.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent
sys.path.insert(0, str(ROOT.parent / '.toolchain/python-deps'))
elf = PORT / 'build/stage11a-control-profile/silenthill_stage11a_control.elf'
os.environ['SH_GAME_ELF'] = str(elf)
fixture = PORT / 'tools/test_stage9_audio_arm.py'
source = fixture.read_text().split('# Original option gain')[0]
source = source.replace("r.call('SD_Init')", """r.call('SD_Init')
r.call('game_prof_enable',16)
r.call('stage11a_perf_start')
tick=[1]
def prof_tick(*_):
    tick[0]+=100
    r.uc.reg_write(UC_ARM_REG_R1,0);r.ret(tick[0])
r.bridge('game3ds_ticks',prof_tick)
""")
from unicorn.arm_const import UC_ARM_REG_R1
ns = {'__file__': str(fixture), '__name__': 'stage11a_pcm', 'UC_ARM_REG_R1': UC_ARM_REG_R1}
exec(compile(source, str(fixture), 'exec'), ns)
accepted = json.loads((PORT / 'reports/stage9-r6-audio-arm.json').read_text())
for current, baseline in zip(ns['cases'], accepted['cases'], strict=True):
    for field in ('sfx', 'nonzero', 'peak', 'sha256'):
        assert current[field] == baseline[field], (field, current, baseline)
    if baseline['nonzero']:
        assert current['voice'] == baseline['voice']
for handle in ns['r'].handles.values():
    handle.close()
results = dict(status='PASS', scope='LINKED_ARM_UNICORN_NOT_HARDWARE',
               elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
               retail_sfx_pcm_cases=ns['cases'], detail_and_window_recording_enabled=True,
               pcm_bit_exact_to_accepted_stage9_r6=True)

fixture = PORT / 'tools/test_stage9_ndsp_arm.py'
source = fixture.read_text()
old = "str(p/'silenthill_game.elf')"
assert source.count(old) == 1
source = source.replace(old, "os.environ['SH_GAME_ELF']")
source = source.replace("(p/'silenthill_game.elf').read_bytes()", "Path(os.environ['SH_GAME_ELF']).read_bytes()")
source = source.replace('stage9-ndsp-arm.json', 'stage11a-ndsp-arm.json')
ns = {'__file__': str(fixture), '__name__': 'stage11a_ndsp'}
exec(compile(source, str(fixture), 'exec'), ns)
results['ndsp_lifecycle'] = json.loads((PORT / 'reports/stage11a-ndsp-arm.json').read_text())
fixture = PORT / 'tools/test_stage9_r4_ndsp_format_arm.py'
source = fixture.read_text().replace("str(p/'silenthill_game.elf')", "os.environ['SH_GAME_ELF']")
source = source.replace('stage9-r4-ndsp-format-arm.json', 'stage11a-ndsp-format-arm.json')
source = source.replace("m.call('audio_thread',0)", """
def thread_id(out,*_):m.uc.mem_write(out,struct.pack('<I',42));ret()
m.hook('svcGetThreadId',thread_id)
depths=[]
m.hook('stage11a_perf_queue',lambda depth,*_:(depths.append(depth),ret()))
m.call('stage11a_perf_start')
m.call('audio_thread',0)
assert depths==[1,2,3,4],depths
m.call('stage11a_perf_stop')
""")
ns = {'__file__': str(fixture), '__name__': 'stage11a_ndsp_format'}
exec(compile(source, str(fixture), 'exec'), ns)
results['ndsp_format_and_queue'] = json.loads((PORT / 'reports/stage11a-ndsp-format-arm.json').read_text())
results['post_submit_queue_depths'] = ns['depths']
(PORT / 'reports/stage11a-arm.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
