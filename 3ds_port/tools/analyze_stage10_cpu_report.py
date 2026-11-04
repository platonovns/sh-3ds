"""Symbolize a CPU audit report; never infer scheduled utilization from elapsed scopes."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('status',type=Path)
ap.add_argument('--elf',type=Path)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();p=Path(__file__).resolve().parents[1]
elf=a.elf or p/'silenthill_game.elf'
values=dict(line.split('=',1) for line in a.status.read_text().splitlines() if '=' in line)
assert values.get('report_complete')=='1' and values.get('cpu_audit_schema')=='2'
assert values['build'].encode() in elf.read_bytes(),'Use the exact report ELF for symbolization'
raw=subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-readelf'),'-sW',str(elf)],text=True)
by_address={};owner=None
for line in raw.splitlines():
    fields=line.split()
    if len(fields)<8:continue
    if fields[3]=='FILE':owner=fields[-1]
    elif fields[3]=='FUNC' and fields[6]!='UND':
        by_address[int(fields[1],16)]=dict(function=fields[-1],source=owner)
threads=[]
for i in range(17):
    key=f'cpu_thread_{i}_create';row=dict(index=i)
    if key in values:
        h,tid,entry,stack,priority,core,detached,rc=values[key].split(',')
        row.update(handle=int(h,0),creation_thread_id=int(tid),entry=int(entry,0),
                   stack_bytes=int(stack),requested_priority=int(priority),
                   requested_core=int(core),detached=bool(int(detached)),kernel_result=rc)
        row['symbol']=by_address.get(int(entry,0),dict(function='UNKNOWN'))
    elif i:continue
    else:row['symbol']=dict(function='main',source='main_game.c')
    runtime=values.get(f'cpu_thread_{i}_runtime')
    if runtime:
        valid,ir,tid,pr,priority=runtime.split(',')
        row.update(handle_identity_valid=bool(int(valid)),thread_id=int(tid),
                   priority=int(priority) if int(pr,0)==0 else None,id_result=ir,priority_result=pr)
    threads.append(row)
observed={}
for name in ('main','spu','xa','ndsp'):
    tid,mask=values[f'cpu_observed_{name}'].split(',')
    known=values['cpu_core_reader']=='LUMA_MPIDR_OPT_IN'
    observed[name]=dict(thread_id=int(tid),sampled_core_mask=int(mask,0) if known else None,
                        source=values['cpu_core_reader'],allowed_affinity_mask=None)
scopes={}
for name in ('spu_block','spu_wait','xa_step','xa_wait','flashlight_setup','resolve'):
    calls,elapsed,peak=values[f'cpu_scope_{name}'].split(',')
    valid=values[f'cpu_scope_{name}_valid']=='1';n=int(calls)
    scopes[name]=dict(snapshot_valid=valid,calls=n,elapsed_ms=float(elapsed) if valid else None,
        mean_elapsed_ms=float(elapsed)/n if valid and n else None,
        peak_elapsed_us=int(peak) if valid else None,scheduled_cpu_ms=None)
rc,count=values['cpu_process_thread_count'].split(',');count=int(count)
count_valid=int(rc,0)==0 and 1<=count<=256
kext=int(values['cpu_kext_detect_result'],0)==1
clocks={}
for name,index in (('current_mhz',0),('higher_mhz',1),('l2_enabled',2)):
    parts=values.get(f'cpu_luma_n3ds_{index}','').split(',')
    clocks[name]=int(parts[1]) if kext and len(parts)==2 and int(parts[0],0)==0 else None
record=dict(status='ANALYZED',build=values['build'],report_sha256=hashlib.sha256(a.status.read_bytes()).hexdigest(),
    elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),threads=threads,
    live_tracked_threads=sum(t.get('handle_identity_valid',False) for t in threads),
    process_thread_count=count if count_valid else None,process_thread_count_raw=count,
    process_thread_count_valid=count_valid,observed=observed,scopes=scopes,clocks=clocks,
    apt_budget_percent=int(values['cpu_apt_budget_percent']) if int(values['cpu_apt_budget_result'],0)==0 else None,
    scope_basis=values['cpu_timing_basis'],scheduled_utilization_percent=None,core_idle_percent=None,
    limitation='Elapsed scopes include preemption/blocking. Missing or implausible SDK counters are UNKNOWN. No hardware acceptance inferred.')
a.output.parent.mkdir(exist_ok=True,parents=True)
a.output.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(build=record['build'],live_tracked_threads=record['live_tracked_threads'],
    process_thread_count=record['process_thread_count'],scopes=scopes),indent=2))
