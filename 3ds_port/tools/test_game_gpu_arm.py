#!/usr/bin/env python3
"""Run linked original boot primitive producers and bounded OT decoder on ARM.

Only the SDK submission/fence boundary is replaced with a recorder. No GPU or
hardware acceptance is inferred. This catches native packet stride corruption.
"""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_CPU_ARM_1176)

port = Path(__file__).resolve().parents[1]
elf_path = Path(os.environ.get('SH_GAME_ELF',str(port / 'silenthill_game.elf')))
elf = elf_path.read_bytes()
nm = subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-nm'), '-n', str(elf_path)], text=True)
symbols = {s[2]: int(s[0],16) for line in nm.splitlines() if len(s:=line.split()) == 3 and s[0] != 'w'}
regs = (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)

class Machine:
    def __init__(self):
        self.uc = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_1176)
        u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000); u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
        u.mem_map(0x100000,0xF00000); u.mem_map(0x10000000,0x20000); u.mem_map(0x30000000,0x1000)
        off = struct.unpack_from('<I',elf,28)[0]
        size,count = struct.unpack_from('<HH',elf,42)
        for n in range(count):
            typ,offset,addr,_,length,_,_,_ = struct.unpack_from('<8I',elf,off+n*size)
            if typ == 1: u.mem_write(addr,elf[offset:offset+length])
        self.draws=[]; self.failure=None
        self.hook('game3ds_gpu_rect',self.draw)
        self.hook('game3ds_gpu_sync',lambda *_:self.ret())
        if 'game3ds_feedback_capture' in symbols:self.hook('game3ds_feedback_capture',lambda *_:self.ret())
        self.hook('game3ds_ticks',lambda *_:self.ret())
        self.hook('game3ds_vblank_clock',lambda *_:self.ret())
        self.hook('game3ds_hblank_clock',lambda *_:self.ret())
        if 'game3ds_q12_clock' in symbols:
            self.hook('game3ds_q12_clock',lambda *_:(u.reg_write(UC_ARM_REG_R0,0),self.ret()))
        self.hook('game3ds_primitive_ticks',lambda *_:self.ret())
        if 'game3ds_status_begin' in symbols:self.hook('game3ds_status_begin',lambda *_:self.ret())
        self.hook('game3ds_halt',self.halt)
        if 'game3ds_read_analog' in symbols:
            self.hook('game3ds_read_analog',lambda *args:([u.mem_write(a,b'\0'*4) for a in args],self.ret()))
        if os.environ.get('SH_STAGE9_REGRESSION')=='1':
            for name in ('SD_Init','SD_Call','Sd_TaskPoolExecute','Sd_PlaySfx','SpuInit','game_audio_pause'):
                if name in symbols:self.hook(name,lambda *_:self.ret())
        # This existing GPU/KCET fixture models an unavailable host card.
        # SD persistence is covered separately by Stage 7 card tests/Azahar.
        if 'game_card_mount' in symbols:
            self.hook('game_card_mount',lambda *_:(u.reg_write(UC_ARM_REG_R0,0),self.ret()))

    def hook(self,name,fn):
        self.uc.hook_add(UC_HOOK_CODE,lambda u,a,s,c:fn(*(u.reg_read(r) for r in regs)),
                         begin=symbols[name],end=symbols[name])
    def ret(self): self.uc.reg_write(UC_ARM_REG_PC,self.uc.reg_read(UC_ARM_REG_LR))
    def draw(self,ptr,count,page,clut):
        textured,blend=struct.unpack('<2I',self.uc.mem_read(self.uc.reg_read(UC_ARM_REG_SP),8))
        self.draws.append({'vertices':struct.unpack('<'+'f'*(count*9),self.uc.mem_read(ptr,count*36)),
                           'count':count,'page':page,'clut':clut,'textured':textured,'blend':blend})
        self.ret()
    def halt(self,code,operation,detail,_):
        self.failure=(code,detail); self.uc.emu_stop()
    def call(self,name,*args,expected_failure=None):
        u=self.uc; self.failure=None
        u.reg_write(UC_ARM_REG_SP,0x1001ffc0)
        for r,a in zip(regs,args): u.reg_write(r,a)
        if len(args)>4:u.mem_write(0x1001ffc0,struct.pack('<'+'I'*(len(args)-4),*args[4:]))
        u.reg_write(UC_ARM_REG_LR,0x30000000)
        u.emu_start(symbols[name],0x30000000,timeout=10_000_000,count=5_000_000)
        if expected_failure is None:
            assert not self.failure,(name,self.failure)
            assert u.reg_read(UC_ARM_REG_PC)==0x30000000,name
        else: assert self.failure and self.failure[0]==expected_failure,(name,self.failure)
        return u.reg_read(UC_ARM_REG_R0)
    def word(self,name,value): self.uc.mem_write(symbols[name],struct.pack('<I',value))
    def get_word(self,name):return struct.unpack('<I',self.uc.mem_read(symbols[name],4))[0]

results={}
# Real pad facade must update both press and release without VSync waits.
m=Machine(); raw0=0x10008000; raw1=0x10009000
m.call('PadInitDirect',raw0,raw1)
m.hook('Game3ds_Observe',lambda *_:m.ret())
pad_keys=[1<<6,0]  # libctru KEY_DUP, then release.
def read_pad(*_):
    m.uc.reg_write(UC_ARM_REG_R0,pad_keys.pop(0)); m.ret()
m.hook('game3ds_read_pad',read_pad)
m.call('Game3ds_PadPoll')
assert bytes(m.uc.mem_read(raw0,4))==bytes([0,0x41,0xef,0xff])
m.call('Game3ds_PadPoll')
assert bytes(m.uc.mem_read(raw0,4))==bytes([0,0x41,0xff,0xff])
assert not pad_keys
results['pad_without_vblank_wait']={'press_and_release':True,'explicit_waits':0}
for producer,sprites in [('BootScreen_KonamiScreenDraw',4),('BootScreen_KcetScreenDraw',2)]:
    m=Machine(); arena=symbols['g_PsxRam']+0x1a2600
    ot=symbols['g_OrderingTable2']
    m.word('g_ActiveBufferIdx',0); m.word('GsOUT_PACKET_P',arena)
    m.call('GsInitGraph2',384,448,5,1,0); m.call('GsClearOt',0,0,ot)
    m.call(producer)
    used=m.get_word('GsOUT_PACKET_P')-arena
    assert used==sprites*(24+12)+20,(producer,'native packet stride',used)
    m.call('GsDrawOt',ot)
    assert len(m.draws)==sprites+1 and sum(d['textured'] for d in m.draws)==sprites
    results[producer]={'packet_bytes':used,'draws':len(m.draws),'sprites':sprites}

m=Machine(); p=symbols['g_PsxRam']+0x100
# A valid tag with an unsupported opcode must stop; a cycle cannot hang.
m.uc.mem_write(p,struct.pack('<IHHI',symbols['prim_terminator'],1,0,0xff000000))
m.call('DrawPrim',p,expected_failure=426)
m.uc.mem_write(p,struct.pack('<IHH',p,0,0));m.call('DrawOTag',p,expected_failure=428)
m.call('DrawOTag',0x80000000,expected_failure=427)
m.uc.mem_write(p,struct.pack('<IHH3I',symbols['prim_terminator'],3,0,0x64808080,0,0))
m.call('DrawPrim',p,expected_failure=425)
results['negative_cases']={'unsupported_opcode':426,'cycle':428,'invalid_pointer':427,'bad_sprite_length':425}
m=Machine()
# Fresh mapped BSS includes zeroed PSX RAM, as after PsxMemory_Init.
m.call('MemCard_SysInit')
card_steps=[]
for _ in range(256):
    card_steps.append(m.call('GameState_KcetLogo_MemCardCheck'))
    m.call('MemCard_Update')
    if card_steps[-1]==2:break
assert card_steps[-1] == 2, ('original KCET no-card transition did not settle',card_steps)
results['original_kcet_no_card']={'calls':len(card_steps),'settled_step':card_steps[-1]}
m=Machine(); arena=symbols['g_PsxRam']+0x1a2600; ot=symbols['g_OrderingTable2']
m.word('g_ActiveBufferIdx',0); m.word('GsOUT_PACKET_P',arena)
m.call('GsInitGraph2',320,448,5,1,0); m.call('GsClearOt',0,0,ot)
# Same zeroed fog workspace assigned by the inlined original initializer.
m.word('D_800BCDE0',symbols['g_PsxRam']+0x1e2432)
m.call('MainMenu_FogDraw'); m.call('GsDrawOt',ot)
assert len(m.draws)==220, ('original title fog primitive count',len(m.draws))
assert not any(d['textured'] for d in m.draws)
results['original_title_fog']={'draws':len(m.draws),'packet_bytes':m.get_word('GsOUT_PACKET_P')-arena}
polygon_results=[]
for kind in (0x20,0x24,0x28,0x2c,0x30,0x34,0x38,0x3c):
    m=Machine();p=symbols['g_PsxRam']+0x100
    points=4 if kind&8 else 3; textured=bool(kind&4);gouraud=bool(kind&16)
    code=kind|2;page=0xe4;clut=0x7800
    words=[(code<<24)|0x1e140a]
    for i in range(points):
        if i and gouraud:words.append((30+i)<<16|(20+i)<<8|(10+i))
        x,y=(-10+20*i,-20+40*i)
        words.append((x&65535)|((y&65535)<<16))
        if textured:words.append((1+10*i)|((2+10*i)<<8)|((clut if i==0 else page if i==1 else 0)<<16))
    m.uc.mem_write(p,struct.pack('<IHH'+'I'*len(words),symbols['prim_terminator'],len(words),0,*words))
    m.call('DrawPrim',p)
    d=m.draws[-1];count=6 if points==4 else 3
    assert d['count']==count and d['textured']==textured
    assert d['blend']==(4 if textured else 1)
    if textured:assert (d['page'],d['clut'])==(page,clut)
    for j,i in enumerate((0,1,2,1,3,2)[:count]):
        v=d['vertices'][j*9:j*9+9]
        expected=(-10+20*i+.5,-20+40*i+.5)
        assert v[:2]==expected,(kind,v,expected)
        ci=i if gouraud else 0;scale=128 if textured else 255
        for actual,wanted in zip(v[5:8],((10+ci)/scale,(20+ci)/scale,(30+ci)/scale)):
            assert math.isclose(actual,wanted,abs_tol=1e-6),(kind,actual,wanted)
        if textured:
            assert math.isclose(v[3],(1.5+10*i)/256,abs_tol=1e-6)
            assert math.isclose(v[4],1-(2.5+10*i)/256,abs_tol=1e-6)
    polygon_results.append({'opcode':hex(code),'words':len(words),'vertices':count})
results['polygon_contracts']=polygon_results
size_cases=[
    ('limit_x',[(0,0),(1023,0),(0,1)],3),
    ('oversize_x',[(0,0),(1024,0),(0,1)],0),
    ('limit_y',[(0,0),(1,0),(0,511)],3),
    ('oversize_y',[(0,0),(1,0),(0,512)],0),
    ('negative_y',[(-10,-300),(10,0),(0,300)],0),
    ('valid_negative_y',[(-10,-100),(10,0),(0,400)],3),
    ('quad_first_only',[(0,0),(20,0),(0,20),(20,700)],3),
    ('quad_second_only',[(0,-700),(20,0),(0,20),(20,20)],3),
    ('quad_both',[(0,0),(20,0),(0,20),(20,20)],6),
    ('quad_neither',[(0,-700),(20,0),(0,20),(20,700)],0),
]
size_results=[]
for label,xy,expected in size_cases:
    for kind in ((0x20,0x24,0x30,0x34) if len(xy)==3 else (0x28,0x2c,0x38,0x3c)):
        m=Machine();p=symbols['g_PsxRam']+0x100;words=[kind<<24|0x808080]
        for i,(x,y) in enumerate(xy):
            if i and kind&16:words.append(0x808080)
            words.append((x&65535)|((y&65535)<<16))
            if kind&4:words.append((0x100 if i==0 else 0xe4 if i==1 else 0)<<16)
        m.uc.mem_write(p,struct.pack('<IHH'+'I'*len(words),symbols['prim_terminator'],len(words),0,*words))
        m.call('DrawPrim',p)
        assert sum(d['count'] for d in m.draws)==expected,(label,hex(kind),expected,m.draws)
        if expected and label=='quad_second_only':
            assert m.draws[0]['vertices'][:2]==(20.5,.5),'Surviving quad half/order changed'
        if kind&4:assert m.get_word('page')==0xe4,'Rejected polygon must still set texture page'
    size_results.append({'case':label,'submitted_vertices':expected,'opcode_variants':4})
results['psx_triangle_size_contracts']=size_results
priority=json.loads((port/'reports/retail-priority-contract.json').read_text())
for case in priority['cases']:
    m=Machine();p=symbols['g_PsxRam']+0x100
    m.uc.mem_write(p,bytes([0xa5])*32)
    m.call('SetPriority',p,case['a'],case['b'])
    data=bytes(m.uc.mem_read(p,32))
    assert struct.unpack_from('<H',data,4)[0]==case['length']
    assert [hex(v) for v in struct.unpack_from('<2I',data,8)]==case['commands']
    assert data[16:]==bytes([0xa5])*16,'native SetPriority overflow'
    m.call('DrawPrim',p)
    assert not m.draws
results['retail_priority_contract']={'cases':4,'native_bytes':16,'guard_bytes':16,
    'raster_mask':'PICA_STENCIL_FRAMEBUFFER; separately verified by GPU pixel probe'}
print(json.dumps({'execution':'linked ARM1176; SDK recorder, not visual/hardware acceptance','results':results},indent=2))
