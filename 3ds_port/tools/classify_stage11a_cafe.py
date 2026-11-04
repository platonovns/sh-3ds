"""Offline original Cafe OT stream. Producer is packet-link caller, never guessed from appearance."""
import bisect,collections,hashlib,json,os,struct,sys
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
os.environ['SH_GAME_ELF']=str(PORT/'build/stage11a-cpu-probe-1/probe.elf')
os.environ['SH_STAGE9_REGRESSION']='1'
import run_arm_game as game
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_LR,UC_ARM_REG_SP
names=sorted((a,n) for n,a in game.symbols.items() if a<0x300000);addresses=[a for a,n in names]
def owner(pc):return names[bisect.bisect_right(addresses,(pc&~1)-1)-1][1]
class Classifier(game.GameRunner):
    def event(self,value):self.events=(self.events+[value])[-24:]
    def __init__(self):
        super().__init__();self.ticks=0;self.map=None;self.owners={};self.current=(0,'none');self.rows=[];self.stream=[]
        self.bridge('game3ds_map_observe',self.map_observe)
        self.submissions=[];self.packet_types=collections.Counter();self.last_key=None;self.batch_vertices=0;self.palettes={}
        self.batch_sizes=[];self.batch_primitives=0
        self.uc.hook_add(UC_HOOK_CODE,self.tick,begin=game.symbols['GameState_InGame_Update'],end=game.symbols['GameState_InGame_Update'])
        self.uc.hook_add(UC_HOOK_CODE,self.link,begin=game.symbols['Game3ds_PacketCheck'],end=game.symbols['Game3ds_PacketCheck'])
        self.uc.hook_add(UC_HOOK_CODE,self.addprim,begin=game.symbols['AddPrim'],end=game.symbols['AddPrim'])
        self.uc.hook_add(UC_HOOK_CODE,self.packet,begin=game.symbols['packet'],end=game.symbols['packet'])
    def link(self,*_):
        p=self.uc.reg_read(UC_ARM_REG_R0);caller=owner(self.uc.reg_read(UC_ARM_REG_LR))
        if caller!='AddPrim':self.owners[p]=caller
    def addprim(self,*_):self.owners[self.uc.reg_read(UC_ARM_REG_R1)]=owner(self.uc.reg_read(UC_ARM_REG_LR))
    def map_observe(self,map,*_):self.map=map;self.ret()
    def packet(self,*_):
        p=self.uc.reg_read(UC_ARM_REG_R0);code=bytes(self.uc.mem_read(p+11,1))[0]
        self.current=(code,self.owners.get(p,'unattributed_static_packet'));self.packet_types[hex(code)]+=1
    def tick(self,*_):
        self.ticks+=1
        if self.ticks>60:self.stopped=True;self.uc.emu_stop()
    def vblank(self,*_):
        self.frames+=1;self.title_age=self.title_age+1 if self.state==7 else 0;self.ret()
    def draw(self,ptr,count,page,clut):
        if self.ticks:
            textured,blend=struct.unpack('<2I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),8))
            mask=struct.unpack('<I',self.uc.mem_read(game.symbols['game3ds_gpu_mask_bits'],4))[0]
            clip=list(struct.unpack('<4h',self.uc.mem_read(game.symbols['draw'],8)))
            code,producer=self.current
            stp='untextured'
            if textured:
                mode=(page>>7)&3;stp='16bit-conservative-mixed'
                if mode<2:
                    palette_key=(mode,clut)
                    if palette_key not in self.palettes:
                        cx=(clut&63)*16;cy=(clut>>6)&511;size=256 if mode else 16
                        words=[struct.unpack('<H',self.uc.mem_read(game.symbols['vram']+2*(cy*1024+((cx+i)&1023)),2))[0] for i in range(size)]
                        self.palettes[palette_key]='/'.join(label for label,present in
                            [('zero',any(w==0 for w in words)),('STP',any(w&0x8000 for w in words)),('opaque',any(w and not(w&0x8000) for w in words))] if present)
                    stp=self.palettes[palette_key]
            key=(page,clut,textured,blend,mask,*clip)
            reasons=['submission'] if self.last_key is None else [label for label,a,b in zip(('page','clut','textured','ABR','mask','clip_x','clip_y','clip_w','clip_h'),self.last_key,key) if a!=b]
            if self.batch_vertices+count>18432:reasons.append('vertex_capacity')
            if reasons:
                if self.batch_primitives:self.batch_sizes.append(self.batch_primitives)
                self.batch_vertices=0;self.batch_primitives=0
            self.batch_primitives+=1
            self.batch_vertices+=count;self.last_key=key
            kind={0x20:'F3',0x24:'FT3',0x28:'F4',0x2c:'FT4',0x30:'G3',0x34:'GT3',0x38:'G4',0x3c:'GT4'}.get(code&0xfc,'rect_line_other')
            row=dict(tick=self.ticks,producer=producer,primitive=kind,code=code,vertices=count,page=page,clut=clut,textured=textured,
                ABR=blend-1 if blend else None,renderer_blend=blend,STP=stp,mask=mask,scissor=clip,
                effect_fog='named' if any(s in producer.lower() for s in ('fog','effect','flare')) else 'unresolved',batch_break=reasons)
            self.stream.append(row)
        super().draw(ptr,count,page,clut)
    def sync(self,*_):
        if self.stream:
            if self.batch_primitives:self.batch_sizes.append(self.batch_primitives)
            self.submissions.append(dict(tick=self.ticks,primitives=len(self.stream),keys=len({(x['page'],x['clut']) for x in self.stream if x['textured']}),
                batches=sum(bool(x['batch_break']) for x in self.stream)))
            self.rows.extend(self.stream);self.stream=[]
        self.last_key=None;self.batch_vertices=0;self.batch_primitives=0;self.palettes.clear();super().sync()
r=Classifier();run=game.run(r,seconds=240)
assert r.ticks>60 and r.map==1 and not any(run[k] for k in ('failure','invalid','exception')),(r.map,run)
summary={name:collections.Counter(str(x[name]) for x in r.rows).most_common() for name in ('producer','primitive','ABR','renderer_blend','STP','mask','effect_fog')}
breaks=collections.Counter(reason for x in r.rows for reason in x['batch_break'])
report=dict(status='PASS',scope=__doc__,map=r.map,elf_sha256=hashlib.sha256(game.game_elf.read_bytes()).hexdigest(),run=run,
    ABR_schema='None=opaque;0=average;1=add;2=subtract;3=add-quarter;renderer_blend=0 or 1+ABR',
    summary=summary,batch_breaks=breaks,batch_primitive_histogram=collections.Counter(r.batch_sizes),submissions=r.submissions,commands=r.rows,
    limits='Verified map 1 nearby Cafe start, first 60 updates. STP hint covers full live palette, not per-texel raster footprint; unnamed effects unresolved. Not full dialogue/hardware timing.',
    hardware_accepted=False)
(PORT/'reports/stage11a-cafe-classification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='commands'},indent=2))
