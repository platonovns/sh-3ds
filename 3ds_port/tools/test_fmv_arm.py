"""Execute linked ARM codec instructions; SDK and gameplay are absent."""
import ctypes,hashlib,json,os,struct,subprocess,sys,time,zlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'3ds_port';B=P/'build/fmv-arm';B.mkdir(exist_ok=True)
sys.path.insert(0,str(R.parent/'.toolchain/python-deps'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import *
prefix=str(R.parent/'.toolchain/rootfs/opt/devkitpro/devkitARM/bin/arm-none-eabi-')
def run(args):return subprocess.check_output([str(a) for a in args],text=True)
flags=['-O2','-march=armv6k','-mtune=mpcore','-mfloat-abi=hard','-mtp=soft','-I'+str(P/'include')]
for src,name in [(P/'source/fmv_mdec.c','codec'),(P/'build/audio/xa_decode.c','xa'),(P/'tests/fmv_arm_codec_fixture.c','fixture')]:
    run([prefix+'gcc',*flags,'-fno-builtin','-c',src,'-o',B/(name+'.o')])
elf_path=B/'fmv-codec-only.elf'
run([prefix+'gcc',*flags,'-nostdlib','-Wl,-Ttext=0x100000,-e,mdec_init',B/'codec.o',B/'xa.o',B/'fixture.o','-lgcc','-o',elf_path])
assert not run([prefix+'nm','-u',elf_path]).strip()
run(['gcc','-O2','-fPIC','-shared','-I'+str(P/'include'),P/'source/fmv_mdec.c',P/'build/audio/xa_decode.c','-o',B/'host-codec.so'])
lib=ctypes.CDLL(str(B/'host-codec.so'));lib.mdec_decode_frame.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p]
elf=elf_path.read_bytes();symbols={v[2]:int(v[0],16) for row in run([prefix+'nm','-n',elf_path]).splitlines() if len(v:=row.split())==3}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_1176)
u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
u.mem_map(0x100000,0x100000);u.mem_map(0x20000000,0x100000);u.mem_map(0x30000000,0x1000)
phoff=struct.unpack_from('<I',elf,28)[0];size,count=struct.unpack_from('<HH',elf,42)
for i in range(count):
    typ,off,addr,_,n,mem,_,_=struct.unpack_from('<8I',elf,phoff+i*size)
    if typ==1:u.mem_write(addr,elf[off:off+n])
regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
def call(name,*args):
    u.reg_write(UC_ARM_REG_SP,0x200ff000);u.reg_write(UC_ARM_REG_LR,0x30000000)
    for reg,arg in zip(regs,args):u.reg_write(reg,arg)
    u.emu_start(symbols[name],0x30000000,count=100000000,timeout=50000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x30000000,name
    return ctypes.c_int32(u.reg_read(UC_ARM_REG_R0)).value
entries=json.loads((P/'reports/fmv-inventory.json').read_text())
disc=R.parent/'silent-hill-decomp/sh1_data/sh1.bin';results=[]
with disc.open('rb') as f:
    for movie,frame in [('C1_20670',1000),('M2_01190',60),('M7_01536',75),('Z1_16180',800)]:
        e=next(x for x in entries if x['name']==movie);chunks=[];size=0
        f.seek((e['lba']+(frame-1)*10)*2352)
        while True:
            raw=f.read(2352)
            if raw[24:28]==b'\x60\x01\x01\x80':
                index,total,no,size=struct.unpack_from('<HHII',raw,28);assert no==frame
                chunks.append(raw[56:2072])
                if index+1==total:break
        bs=b''.join(chunks)[:size];ctx=0x20000000;inp=0x20001000;out=0x20010000
        u.mem_write(inp,bs);call('mdec_init',ctx,320,208)
        t=time.monotonic();assert call('mdec_decode_frame',ctx,inp,len(bs),out)==260;elapsed=time.monotonic()-t
        arm=bytes(u.mem_read(out,320*208*3));hctx=ctypes.create_string_buffer(12);hrgb=ctypes.create_string_buffer(len(arm))
        lib.mdec_init(hctx,320,208);assert lib.mdec_decode_frame(hctx,ctypes.c_char_p(bs),len(bs),hrgb)==260
        assert arm==hrgb.raw
        results.append(dict(movie=movie,frame=frame,rgb_sha256=hashlib.sha256(arm).hexdigest(),unicorn_wall_seconds=elapsed))
    # Two audio sectors with continuous predictor history, byte-identical ARM/host PCM.
    entry=entries[0];history=0x20050000;u.mem_write(history,bytes(16));hstate=ctypes.create_string_buffer(16)
    for rel in [7,15]:
        f.seek((entry['lba']+rel)*2352+16);sector=f.read(2336);u.mem_write(inp,sector)
        assert call('game_xa_decode',inp,out,history)==4032
        host=ctypes.create_string_buffer(8064);assert lib.game_xa_decode(ctypes.c_char_p(sector),host,hstate)==4032
        assert bytes(u.mem_read(out,8064))==host.raw
        assert bytes(u.mem_read(history,16))==hstate.raw
report=dict(status='PASS',scope=__doc__,elf_sha256=hashlib.sha256(elf).hexdigest(),frames=results,audio_sectors_compared=2,
    performance_warning='Unicorn wall time is host emulator time, not ARM11 hardware throughput')
(P/'reports/fmv-arm-codec.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
