"""Local retail MIPS reference for bounded native-contract comparisons.
Original code/data come from the user's USA image; cached RAM stays in build/.
This is a component oracle, not a full PS1 emulator or visual acceptance.
"""
import hashlib,json,re,struct
from pathlib import Path
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
from unicorn.mips_const import UC_MIPS_REG_0,UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3,UC_MIPS_REG_V0,UC_MIPS_REG_PC,UC_MIPS_REG_RA,UC_MIPS_REG_SP
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
def symbols():
    out={}
    for path in (ROOT/'configs/USA/sym.main.txt',ROOT/'configs/USA/sym.bodyprog.txt'):
        for name,address in re.findall(r'^(\w+)\s*=\s*(0x[0-9A-Fa-f]+)',path.read_text(),re.M):out[name]=int(address,16)
    return out
SYMBOLS=symbols()

def iso_file(path):
    with (ROOT/'sh1_data/sh1.bin').open('rb') as f:
        def read(lba,n):
            out=bytearray()
            for i in range((n+2047)//2048):
                f.seek((lba+i)*2352+24);out.extend(f.read(2048))
            return bytes(out[:n])
        pvd=read(16,2048);directory=read(struct.unpack_from('<I',pvd,158)[0],struct.unpack_from('<I',pvd,166)[0])
        parts=path.upper().split('/')
        for part in parts:
            offset=0;names=[]
            while offset<len(directory):
                length=directory[offset]
                if not length:offset=(offset//2048+1)*2048;continue
                row=directory[offset:offset+length];offset+=length
                name=row[33:33+row[32]].decode('ascii',errors='replace').split(';')[0].rstrip('.');names.append(name)
                if name==part:
                    directory=read(struct.unpack_from('<I',row,2)[0],struct.unpack_from('<I',row,10)[0]);break
            else:raise AssertionError(('ISO file missing',path,part,names))
        return directory
def exe_image():
    with (ROOT/'sh1_data/sh1.bin').open('rb') as f:
        def read(lba,n):
            out=bytearray()
            for i in range((n+2047)//2048):
                f.seek((lba+i)*2352+24);out.extend(f.read(2048))
            return bytes(out[:n])
        pvd=read(16,2048);lba=struct.unpack_from('<I',pvd,158)[0];n=struct.unpack_from('<I',pvd,166)[0]
        directory=read(lba,n);offset=0
        while offset<len(directory):
            size=directory[offset]
            if not size:offset=(offset//2048+1)*2048;continue
            record=directory[offset:offset+size];offset+=size
            if record[33:33+record[32]]==b'SLUS_007.07;1':
                exe=read(struct.unpack_from('<I',record,2)[0],struct.unpack_from('<I',record,10)[0]);break
        else:raise AssertionError('USA executable missing')
    expected=re.search(r'sha1:\s*(\w+)',(ROOT/'configs/USA/main.yaml').read_text())[1].lower()
    assert hashlib.sha1(exe).hexdigest()==expected
    return exe
def initial_ram():
    cache=PORT/'build/stage10-retail-initial-ram.bin'
    if not cache.exists():
        import run_arm_game as game
        class Boot(game.GameRunner):
            def vblank(self,*_):
                self.frames+=1
                if self.state==7:self.stopped=True;self.uc.emu_stop()
                self.ret(0)
        r=Boot();result=game.run(r,seconds=120)
        assert r.state==7 and not any(result[k] for k in ('failure','invalid','exception')),result
        image=bytes(r.uc.mem_read(game.symbols['g_PsxRam'],0x300000))
        cache.write_bytes(image)
    image=bytearray(cache.read_bytes());assert len(image)==0x300000
    exe=exe_image();address,length=struct.unpack_from('<2I',exe,0x18)
    image[address&0x1fffffff:(address&0x1fffffff)+length]=exe[0x800:0x800+length]
    return bytes(image)
class Retail:
    def __init__(self,image=None):
        self.uc=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
        self.uc.mem_map(0,0x301000);self.uc.mem_write(0,initial_ram() if image is None else image)
        self.calls=[];self.hooks=[];self.regs=(UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3)
        self.gte_control=[0]*32;self.gte_data=[0]*32
        # libgs initialization uses only COP2 register transfers. Emulate that
        # hardware boundary; fail explicitly if an actual GTE command is reached.
        def cop2(u,address,size,unused):
            word=struct.unpack('<I',u.mem_read(address&0x1fffffff,4))[0]
            if word>>26!=0x12:return
            operation=(word>>21)&31;reg=(word>>16)&31;slot=(word>>11)&31
            assert operation in (0,2,4,6),('GTE command requires a dedicated oracle',hex(address),hex(word))
            bank=self.gte_control if operation in (2,6) else self.gte_data
            if operation in (4,6):
                bank[slot]=u.reg_read(UC_MIPS_REG_0+reg)
                if operation==4 and slot==30:
                    # GTE LZCS/LZCR, used by the retail integer square root.
                    value=bank[slot]&0xffffffff
                    if value&0x80000000:value^=0xffffffff
                    bank[31]=32-value.bit_length()
            elif reg:u.reg_write(UC_MIPS_REG_0+reg,bank[slot])
            u.reg_write(UC_MIPS_REG_PC,address+4)
        self.hooks.append(self.uc.hook_add(UC_HOOK_CODE,cop2,begin=0x80000000,end=0x80300000))
    def ret(self,value=0):
        self.uc.reg_write(UC_MIPS_REG_V0,value&0xffffffff)
        self.uc.reg_write(UC_MIPS_REG_PC,self.uc.reg_read(UC_MIPS_REG_RA))
    def hook(self,name,fn):
        address=SYMBOLS[name]
        self.hooks.append(self.uc.hook_add(UC_HOOK_CODE,lambda u,a,s,c:fn(*(u.reg_read(r) for r in self.regs)),begin=address,end=address))
    def call(self,name,*args):
        u=self.uc;u.reg_write(UC_MIPS_REG_SP,0x801ff000);u.reg_write(UC_MIPS_REG_RA,0x300000)
        for reg,value in zip(self.regs,args):u.reg_write(reg,value&0xffffffff)
        for i,value in enumerate(args[4:]):u.mem_write(0x1ff010+i*4,struct.pack('<I',value&0xffffffff))
        try:u.emu_start(SYMBOLS[name],0x300000,count=500000)
        except Exception as error:
            pc=u.reg_read(UC_MIPS_REG_PC)
            raise AssertionError((name,hex(pc),bytes(u.mem_read(pc&0x1fffffff,4)).hex(),str(error))) from error
        assert u.reg_read(UC_MIPS_REG_PC)==0x300000,(name,hex(u.reg_read(UC_MIPS_REG_PC)))
        return u.reg_read(UC_MIPS_REG_V0)
