#!/usr/bin/env python3
"""Actual linked ARM cache, host read-only transport/malloc; no hardware timing."""
import json,os,struct,subprocess
from pathlib import Path
import run_arm_tim as runtime
from unicorn.arm_const import UC_ARM_REG_R1
p=runtime.PORT;elf=p/'silenthill_game.elf';runtime.ELF=elf.read_bytes()
nm=subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-nm'),'-n',str(elf)],text=True)
runtime.SYMBOLS={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3 and s[0]!='w'}
runtime.PHOFF=struct.unpack_from('<I',runtime.ELF,28)[0];runtime.PHSIZE,runtime.PHCOUNT=struct.unpack_from('<HH',runtime.ELF,42)
class Cache(runtime.Runner):
    def __init__(self,kind='supported'):
        self.reads=0;self.fail_read=False;self.next_cache=0x24000000
        super().__init__(kind);self.uc.mem_map(0x24000000,16*1024*1024)
        self.bridge('malloc',self.malloc)
        self.bridge('game3ds_ticks',lambda *_:(self.uc.reg_write(UC_ARM_REG_R1,0),self.ret(0)))
    def malloc(self,size,*_):
        if self.kind=='malloc_fail':self.ret(0);return
        assert size+sum(self.allocations.values())<=16*1024*1024
        ptr=self.next_cache;self.next_cache+=(size+4095)&~4095
        assert self.next_cache<=0x25000000
        self.allocations[ptr]=size;self.ret(ptr)
    def fread(self,dst,size,count,h):
        self.reads+=1
        if self.fail_read:self.fail_read=False;self.ret(0);return
        super().fread(dst,size,count,h)
results={}
for kind in ('supported','malloc_fail','short'):
    r=Cache(kind);d=0x20000000;out=0x20004000
    assert r.call('PsxDisc_Open',d,0x20001000,0x20002000)==0
    r.fail_read=kind=='short';previous=r.reads
    status=r.call('PsxDisc_CacheRange',d,17845,5020)
    if kind=='supported':
        assert status==0 and r.reads-previous==157
        assert list(r.allocations.values())==[11807040]
        before=r.reads
        with (runtime.ROOT/'sh1_data/sh1.bin').open('rb') as source:
            for i in (0,1,31,32,100,512,2500,5019,1,0):
                assert r.call('PsxDisc_ReadDataSector',d,17845+i,out)==0
                source.seek((17845+i)*2352+24);assert bytes(r.uc.mem_read(out,2048))==source.read(2048)
        assert r.reads==before
        before=r.reads;assert r.call('PsxDisc_CacheExtraRange',d,39321,38)==0
        assert r.reads-before==2 and sum(r.allocations.values())==11896416
        before=r.reads
        with (runtime.ROOT/'sh1_data/sh1.bin').open('rb') as source:
            for i in (0,1,37):
                assert r.call('PsxDisc_ReadDataSector',d,39321+i,out)==0
                source.seek((39321+i)*2352+24);assert bytes(r.uc.mem_read(out,2048))==source.read(2048)
        assert r.reads==before
        byte=bytes(r.uc.mem_read(0x24000000+12,1));r.uc.mem_write(0x24000000+12,bytes([byte[0]^1]))
        assert r.call('PsxDisc_ReadRawSector',d,17845,out)==0xfffffffd
        r.uc.mem_write(0x24000000+12,byte)
    else:
        assert status==0xfffffffe and not r.allocations
        assert r.call('PsxDisc_ReadDataSector',d,16,out)==0
    r.call('PsxDisc_Close',d);assert not r.allocations and not r.handles and not r.invalid
    results[kind]={'passed':True,'host_transport_reads':r.reads,'ordinary_cache_limit':16777216}
print(json.dumps({'execution':'linked ARM1176 cache and raw validation; host stdio/malloc only','results':results},indent=2))
