"""Linked main submission: preserve draw stream, reserve unique resident keys."""
import hashlib,json,os,struct,subprocess,sys
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
if len(sys.argv)>1:
 elf=PORT/sys.argv[1];os.environ['SH_GAME_ELF']=str(elf)
 fixture=PORT/'tools/test_game_gpu_arm.py';ns={'__file__':str(fixture),'__name__':'submit_fixture'}
 from unicorn import UC_HOOK_CODE
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP
 source=fixture.read_text().split('results={}')[0].replace("self.hook('game3ds_gpu_sync',lambda *_:self.ret())",'pass')
 source=source.replace("self.hook('game3ds_gpu_rect',self.draw)",'pass')
 ns={'__file__':str(fixture),'__name__':'submit_fixture'};exec(compile(source,str(fixture),'exec'),ns);m=ns['Machine']();uc=m.uc;g=ns['symbols']
 records=[];state=dict(clip=None,mask=0);textures=[0];counts=dict(pin=0,acquire=0,create=0,update=0)
 def ret(value=0):uc.reg_write(UC_ARM_REG_R0,value);m.ret()
 def clip(a,b,c,d):
  for ptr,v in zip((a,b,c,d),(0,0,320,240)):uc.mem_write(ptr,struct.pack('<I',v))
  ret()
 def extent(a,b,*_):uc.mem_write(a,struct.pack('<I',320));uc.mem_write(b,struct.pack('<I',240));ret()
 m.hook('game3ds_gpu_clip',clip);m.hook('game3ds_gpu_extent',extent)
 m.hook('game3ds_gpu_display',lambda *_:ret());m.hook('game3ds_gpu_frame_token',lambda *_:ret(1))
 m.hook('svcGetSystemTick',lambda *_:(uc.reg_write(UC_ARM_REG_R1,0),ret()))
 m.hook('render3ds_stats',lambda *_:ret(0x10018000))
 for name in ('render3ds_set_display','render3ds_continue_psx_frame','render3ds_begin_psx_frame','render3ds_end_psx_part','game3ds_gpu_frame_complete','render3ds_texture_psx_coverage','render3ds_texture_linear'):
  m.hook(name,lambda *_:ret(1))
 m.hook('render3ds_set_scissor',lambda a,b,c,d:(state.update(clip=[a,b,c,d]),ret(1)))
 m.hook('render3ds_set_psx_mask',lambda bits,*_:(state.update(mask=bits),ret()))
 def create(*_):textures[0]+=1;counts['create']+=1;ret(0x900000+textures[0]*256)
 m.hook('render3ds_texture_create_rows',create)
 def update(*_):counts['update']+=1;ret(1)
 m.hook('render3ds_texture_update_rows',update)
 if 'render3ds_texture_update_tiles' in g:m.hook('render3ds_texture_update_tiles',update)
 def draw(vertices,count,sizes,primitives):
  texture,blend=struct.unpack('<2I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),8))
  records.append([count,primitives,texture,blend,state.copy(),hashlib.sha256(bytes(uc.mem_read(vertices,count*36))).hexdigest(),bytes(uc.mem_read(sizes,primitives*2)).hex()]);ret(1)
 m.hook('render3ds_draw_psx_ordered',draw)
 for name in ('pin','acquire'):
  def observe(*_,name=name):counts[name]+=1
  uc.hook_add(UC_HOOK_CODE,observe,begin=g['game_texture_'+name],end=g['game_texture_'+name])
 vertices=0x10008000;uc.mem_write(vertices,struct.pack('<54f',*([10.,20.,0.,0.,0.,1.,1.,1.,1.]*6)))
 for frame in range(3):
  m.call('game3ds_gpu_begin_draw')
  for i in range(1000):
   uc.mem_write(g['game3ds_gpu_mask_bits'],struct.pack('<I',i%4))
   m.call('game3ds_gpu_rect',vertices,3 if i%3 else 6,256+(i%8),0,1,i%5)
  m.call('game3ds_gpu_sync')
 assert not m.failure
 print(json.dumps(dict(counts=counts,draws=len(records),stream_sha256=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())));raise SystemExit
result={}
for label,path in [('F1','build/stage11a-tracefix/silenthill_stage11a_tracefix.elf'),('CPU','build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf')]:
 result[label]=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),path],text=True))
assert result['F1']['stream_sha256']==result['CPU']['stream_sha256'],result
assert result['CPU']['counts']['pin']==24 and result['CPU']['counts']['acquire']==24,result
report=dict(status='PASS',scope=__doc__,results=result,not_gpu_acceptance=True)
(PORT/'reports/stage11a-cpu-submit-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
