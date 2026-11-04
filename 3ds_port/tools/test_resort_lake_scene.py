"""Run Lakefront callback through its original skip path and confirm control and transition flags."""
from pathlib import Path
import os,struct,json,sys,hashlib
port=Path(__file__).resolve().parents[1]
os.environ['SH_BLOCK3_ELF']=str(port/'build/resort-probe/resort-probe.elf')
exec((port/'tools/test_block3_runtime.py').read_text().split('\ncases = [',1)[0])
class Lake(Entry):
 def __init__(self):
  super().__init__(33,'map5_s01',24,(350,352,193,355,358),require_control=False)
  self.seen=[];self.skip=False;self.stable=0;self.last_message=None;self.message_phase=0
  if '--mock-dialogue' in sys.argv:self.bridge('Gfx_MapMsg_Draw',self.dialogue)
  self.uc.hook_add(UC_HOOK_CODE,self.scene,begin=game.symbols['map6_s00_func_800EB11C'],end=game.symbols['map6_s00_func_800EB11C'])
 def dialogue(self,index,*_):
  key=(index,struct.unpack('<I',self.uc.mem_read(game.symbols['g_SysWork']+12,4))[0])
  if key!=self.last_message:self.last_message=key;self.message_phase=0
  self.message_phase+=1;self.ret(0xffffffff if self.message_phase==1 else 1)
 def place(self,uc,*_):
  if not self.placed:self.placed=True;uc.reg_write(UC_ARM_REG_R0,game.symbols['map5_s01_MAP_POINTS']+24*12)
 def scene(self,uc,*_):
  step=struct.unpack('<I',uc.mem_read(game.symbols['g_SysWork']+12,4))[0]
  if step not in self.seen:self.seen.append(step)
  self.skip=2<=step<19
 def tick(self,uc,*_):
  if self.map!=33:return
  self.ticks+=1
  save=struct.unpack('<I',uc.mem_read(game.symbols['g_SavegamePtr'],4))[0]
  def flag(n):return bool(struct.unpack('<I',uc.mem_read(save+0x168+4*(n//32),4))[0]&(1<<(n%32)))
  if flag(402) and flag(403) and not uc.mem_read(game.symbols['g_Player_DisableControl'],1)[0] and struct.unpack('<I',uc.mem_read(game.symbols['g_SysWork']+8,4))[0]==0:self.stable+=1
  else:self.stable=0
  if self.stable>=21:self.stopped=True;uc.emu_stop()
 def read_pad(self,*_):
  if self.skip:self.skip=False;self.ret(1<<3)
  else:super().read_pad()
r=Lake();result=game.run(r,seconds=600)
report=dict(result=result,steps=r.seen,stable=r.stable,ticks=r.ticks,elf_sha256=hashlib.sha256((port/'build/resort-probe/resort-probe.elf').read_bytes()).hexdigest())
(port/'build/resort-probe/lake-skip.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
if result['failure'] or result['invalid'] or result['exception'] or r.stable<21 or 0 not in r.seen or not any(s>=2 for s in r.seen):raise SystemExit(1)
