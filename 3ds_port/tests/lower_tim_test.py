#!/usr/bin/env python3
"""Validate the original US paper-map and marking TIM resources in a local disc."""
import struct, sys
from pathlib import Path

with Path(sys.argv[1]).open('rb') as f:
    def read(lba, off, count):
        out = bytearray()
        while count:
            lba2, pos = lba + off // 2048, off % 2048
            take = min(count, 2048 - pos)
            f.seek(lba2 * 2352 + 24 + pos)
            b = f.read(take)
            if len(b) != take: raise ValueError('short sector')
            out.extend(b); off += take; count -= take
        return bytes(out)
    for file_id in list(range(1896, 1910)) + list(range(1910, 1915)):
        entry = read(24, 47388 + 12*file_id, 12)
        word, = struct.unpack_from('<I',entry)
        lba, size = word & 0x7ffff, ((word >> 19) & 0xfff) * 256
        data = read(lba,0,size)
        magic, flags = struct.unpack_from('<II',data)
        assert magic == 16 and flags & ~15 == 0 and flags & 7 <= 2, (file_id, magic, flags)
        mode = flags & 7
        off=8
        if flags & 8:
            length,x,y,w,h=struct.unpack_from('<IHHHH',data,off)
            assert length == 12+w*h*2 and off+length <= len(data)
            assert x+w<=1024 and y+h<=512 and w%(16 if mode==0 else 256)==0
            clut_rect=(x,y,w,h); off+=length
        length,x,y,w,h=struct.unpack_from('<IHHHH',data,off)
        assert length==12+w*h*2 and off+length<=len(data)
        assert x+w<=1024 and y+h<=512
        width=w*(4>>mode)
        print(file_id, width,h,'mode',mode, 'image',(x,y,w,h),'clut',clut_rect)
        if file_id < 1910: assert width>=320 and h>=480
print('PASS: original map and atlas TIM bounds')
