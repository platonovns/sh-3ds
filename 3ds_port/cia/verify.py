"""Validate release CIA structure, DSP permissions and executable contents."""
import hashlib
from pathlib import Path
import struct
import sys
import wave

cia = Path(sys.argv[1]).read_bytes()
elf = Path(sys.argv[2]).read_bytes()
banner = Path(sys.argv[3]).read_bytes()
icon = Path(sys.argv[4]).read_bytes()
le32 = lambda b, o: struct.unpack_from('<I', b, o)[0]
align = lambda n: (n + 63) & ~63
h, _, _, cert, ticket, tmdlen, _, contentsize = struct.unpack_from('<IHHIIIIQ', cia)
tmdpos = align(align(align(h) + cert) + ticket)
tmd = cia[tmdpos:tmdpos+tmdlen]
ncchpos = align(tmdpos+tmdlen)
ncch = cia[ncchpos:ncchpos+contentsize]
assert ncch[0x100:0x104] == b'NCCH'
assert tmd[0x140+0x9c4+16:0x140+0x9c4+48] == hashlib.sha256(ncch).digest()
assert int.from_bytes(tmd[0x140+0x9c:0x140+0x9e], 'big') == 145
assert ncch[0x1b0:0x1b8] == bytes(8), 'Unexpected RomFS'
exheader = ncch[0x200:0x600]
assert ncch[0x160:0x180] == hashlib.sha256(exheader).digest()
assert b'dsp::DSP' in exheader and b'mcu::HWC' in exheader
caps = struct.unpack_from('<28I', ncch, 0x570)
assert 0xff81ff00 in caps and 0xff81ff80 in caps, 'Missing DSP static mapping'
base = le32(ncch, 0x1a0) * 512
exefs = ncch[base:]
files = {}
for i in range(10):
    name = exefs[i*16:i*16+8].rstrip(b'\0').decode('ascii')
    if not name:
        continue
    offset, size = struct.unpack_from('<II', exefs, i*16+8)
    data = exefs[512+offset:512+offset+size]
    assert len(data)==size and hashlib.sha256(data).digest()==exefs[0x1e0-i*32:0x200-i*32]
    files[name] = data
assert set(files)=={'.code', 'icon', 'banner'}
assert files['icon']==icon and files['banner']==banner
assert icon[:4] == b'SMDH'
for locale in range(16):
    title = 8 + locale * 0x200
    assert icon[title:title+0x80].decode('utf-16le').split('\0')[0] == 'SH-3DS'
    assert icon[title+0x80:title+0x180].decode('utf-16le').split('\0')[0] == 'SH-3DS'
# Nintendo BLZ is decoded from the end of the compressed .code segment.
data = files['.code']; footer, extra = struct.unpack_from('<II', data, len(data)-8)
start = len(data)-(footer&0xffffff); cur = len(data)-(footer>>24)
out = bytearray(data)+bytearray(extra); dst = len(out)
while cur > start:
    cur -= 1; flags = data[cur]
    for bit in range(7,-1,-1):
        if cur <= start: break
        if flags & (1<<bit):
            cur -= 2; high, low = data[cur+1], data[cur]
            length = (high>>4)+3; distance = ((high&15)<<8|low)+3
            for _ in range(length):
                dst -= 1; out[dst] = out[dst+distance]
        else:
            cur -= 1; dst -= 1; out[dst] = data[cur]
assert dst==start
phoff=le32(elf,28); entsize, count=struct.unpack_from('<HH',elf,42)
for i in range(count):
    typ, offset, addr, _, size = struct.unpack_from('<IIIII',elf,phoff+i*entsize)
    if typ==1:
        assert out[addr-0x100000:addr-0x100000+size]==elf[offset:offset+size], 'ELF load segment mismatch'
assert files['banner'][:4]==b'CBMD'
audio_offset=le32(files['banner'],0x84); cwav=files['banner'][audio_offset:]
assert cwav[:4]==b'CWAV'
info=le32(cwav,0x18); datab=le32(cwav,0x24)
assert cwav[info+8]==1 and le32(cwav,info+28)==1
frames=le32(cwav,info+20); ch=info+28+le32(cwav,info+36); begin=datab+8+le32(cwav,ch+4)
with wave.open(sys.argv[5], 'rb') as wav:
    assert wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 32000
    samples = wav.readframes(wav.getnframes())
assert frames > 0 and any(samples), 'Banner audio is silent'
assert frames * 2 == len(samples) and cwav[begin:begin+frames*2] == samples, 'Banner audio differs from converted source'
print('PASS: title, TMD, ExeFS, ELF segments, DSP services, no RomFS, banner audio')
