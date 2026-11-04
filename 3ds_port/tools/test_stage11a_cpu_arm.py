"""Final ARM ELF: retail SFX/NDSP and pitch writer/decoder state in F0/F1."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
ELF=PORT/'build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf'
os.environ['SH_GAME_ELF']=str(ELF)
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))


def state_trial(mode):
    fixture=PORT/'tools/test_stage9_audio_arm.py'
    source=fixture.read_text().split('for command in (160,162,163,170):')[0]
    ns={'__file__':str(fixture),'__name__':'trace_writer_arm'}
    exec(compile(source,str(fixture),'exec'),ns)
    r,g=ns['r'],ns['game']
    from unicorn.arm_const import UC_ARM_REG_LR
    def symbol(suffix):return next(addr for name,addr in g.symbols.items() if name.endswith(suffix))
    def name_at(pc):return max((a,n) for n,a in g.symbols.items() if a<=(pc&~1)-1)[1]
    r.call('control_change',0,1,0)
    count=struct.unpack('<I',r.uc.mem_read(symbol('pitch_countE'),4))[0]
    assert count==24,count
    base=symbol('pitch_eventsE')
    events=[list(struct.unpack('<Q27I',r.uc.mem_read(base+i*120,116))) for i in range(count)]
    for i,e in enumerate(events):
        assert e[2]==i and e[4:6]==[0,4096] and e[7:9]==[0,0],e
        assert e[13:17]==[1,0,1,0] and e[18]==0,e
        assert name_at(e[1])=='pitch_calc',(e,name_at(e[1]))
    scratch=0x24800000
    r.uc.mem_write(scratch,bytes(60));r.call('stage11a_pitch_midi_snapshot',3,scratch)
    scope=list(struct.unpack('<15I',r.uc.mem_read(scratch,60)))
    assert scope[:4]==[0,0,0,0] and scope[14]==0,scope
    if r.call('game_spu_silent_fast_enabled')!=mode:assert r.call('game_spu_silent_fast_toggle')==mode
    assert r.call('game_spu_silent_fast_enabled')==mode
    for _ in range(4):r.call('game_spu_render',scratch,512)
    pcm=bytes(r.uc.mem_read(scratch,2048));assert not any(pcm)
    stats=list(struct.unpack('<13I',r.uc.mem_read(symbol('fast_statsE'),52)))
    assert stats[1]==24 and stats[2]==(24 if mode else 0) and stats[10]==(23 if mode else 0),stats
    # Canonical snapshots already cover field semantics on the host. The exact
    # linked ARM image must also have the identical WHOLE native core object,
    # including decoder/RAM state, in both modes with deterministic allocations.
    nm=subprocess.check_output([os.environ['DEVKITARM']+'/bin/arm-none-eabi-nm','-S',str(ELF)],text=True)
    sym=next(line.split() for line in nm.splitlines() if line.split()[-1].endswith('3spuE'))
    core=bytes(r.uc.mem_read(int(sym[0],16),int(sym[1],16)))
    assert not r.failure and not r.invalid,(r.failure,r.invalid)
    for handle in r.handles.values():handle.close()
    return dict(mode=mode,core_sha256=hashlib.sha256(core).hexdigest(),core_bytes=len(core),trace_count=count,
                writer='pitch_calc',scope='control_change(0,1,0)',port_status=events[3][18],
                scope_cleanup=True,fast_stats=stats,pcm_sha256=hashlib.sha256(pcm).hexdigest())


if __name__=='__main__':
    if len(sys.argv)>1:
        print(json.dumps(state_trial(int(sys.argv[1]))));raise SystemExit
    modes=[json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),str(n)],text=True)) for n in (0,1)]
    assert modes[0]['core_sha256']==modes[1]['core_sha256']
    # Existing actual-ARM SFX and NDSP lifecycle fixtures. Enable F1 before retail
    # calls; do not change any old PCM acceptance report.
    fixture=PORT/'tools/test_stage11a_lifetime_arm.py'
    # Expand its inherited wrapper, then substitute just the ELF/report targets.
    wrapper=fixture.read_text()
    wrapper=wrapper.replace('build/stage11a-lifetime/silenthill_stage11a_lifetime.elf','build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf')
    wrapper=wrapper.replace('stage11a-lifetime-ndsp','stage11a-cpu-A-ndsp').replace('stage11a-lifetime-arm.json','stage11a-cpu-A-arm-fixtures.json')
    setup=wrapper.rsplit("exec(compile(source,str(fixture),'exec'),",1)[0]
    ns={'__file__':str(fixture),'__name__':'tracefix_existing_arm'}
    exec(compile(setup,str(fixture),'exec'),ns)
    source=ns['source'];needle='"""r.call(\'SD_Init\')\n'
    assert source.count(needle)==1
    source=source.replace(needle,needle+"assert r.call('game_spu_silent_fast_enabled')==1\n")
    exec(compile(source,str(PORT/'tools/test_stage11a_arm.py'),'exec'),ns)
    existing=json.loads((PORT/'reports/stage11a-cpu-A-arm-fixtures.json').read_text())
    result=dict(status='PASS',scope='LINKED_ARM_UNICORN_NOT_HARDWARE',elf_sha256=hashlib.sha256(ELF.read_bytes()).hexdigest(),
        modes=modes,whole_native_core_byte_exact=True,retail_sfx_ndsp=existing)
    (PORT/'reports/stage11a-cpu-A-arm.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
