#!/usr/bin/env python3
"""Independent tex3ds bytes + PICA sampler, not an inverse of our uploader.

PICA Texture2D nearest/clamp: s=floor(U*W), t=H-1-floor(V*H),
then raw tile lookup. See Azahar sw_rasterizer.cpp TextureColor and tex3ds.
No emulation of triangle coverage/TEV/display hardware is claimed.
"""
from pathlib import Path
import json
import importlib.util
import math
import subprocess
import sys
import zlib

PORT = Path(__file__).resolve().parents[1]
BUILD = PORT / 'build'

def offset(w, x, y):
    # Independent deinterleave table, rather than production bit loop.
    spread = (0,1,4,5,16,17,20,21)
    return (((y//8)*(w//8)+x//8)*64 + spread[x%8]+2*spread[y%8])*4

def sample(tiled,w,h,u,v):
    x = max(0,min(w-1,math.floor(u*w)))
    y = h-1-max(0,min(h-1,math.floor(v*h)))
    start = offset(w,x,y)
    return tiled[start:start+4][::-1]

def render(tiled,w,h,lw,lh,flip_u=False,flip_v=False):
    result = bytearray()
    for y in range(lh):
        for x in range(lw):
            sx = lw-(x+0.5) if flip_u else x+0.5
            sy = lh-(y+0.5) if flip_v else y+0.5
            result += sample(tiled,w,h,sx/w,1-sy/h)
    return bytes(result)

def transforms(image,n):
    mappings = {
        'identity': lambda x,y:(x,y), 'mirror_x':lambda x,y:(n-1-x,y),
        'mirror_y':lambda x,y:(x,n-1-y), 'rotate_180':lambda x,y:(n-1-x,n-1-y),
        'transpose':lambda x,y:(y,x), 'rotate_90':lambda x,y:(y,n-1-x),
        'rotate_270':lambda x,y:(n-1-y,x), 'anti_transpose':lambda x,y:(n-1-y,n-1-x)}
    return {name:b''.join(image[(sy*n+sx)*4:(sy*n+sx)*4+4]
                          for y in range(n) for x in range(n) for sx,sy in [fn(x,y)])
            for name,fn in mappings.items()}

def main():
    old = '--expect-old' in sys.argv
    BUILD.mkdir(exist_ok=True)
    exe = BUILD / 'orientation_dump'
    subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I'+str(PORT/'include'),str(PORT/'tests/orientation_dump.c'),'-o',str(exe)],check=True)
    ppm = BUILD / 'orientation-pattern.ppm'
    actual = subprocess.check_output([str(exe),str(ppm)])
    raw = BUILD / 'orientation-reference.tiled'
    subprocess.run(['tex3ds','-r','-z','none','-f','rgba8','-o',str(raw),str(ppm)],check=True)
    tex3ds = raw.read_bytes()
    # raw output still has the documented four-byte fake compression header.
    if len(tex3ds) == len(actual)+4:
        assert tex3ds[0] == 0 and int.from_bytes(tex3ds[1:4],'little') == len(actual)
        tex3ds = tex3ds[4:]
    assert len(tex3ds) == len(actual) == 4096
    rgb = ppm.read_bytes().split(b'\n',3)[3]
    original = b''.join(rgb[i:i+3]+b'\xff' for i in range(0,len(rgb),3))
    variants = transforms(original,32)
    assert len(set(variants.values())) == 8, 'Pattern must distinguish the full dihedral group'
    combinations = {}
    for fu,fv in ((False,False),(True,False),(False,True),(True,True)):
        display = render(actual,32,32,32,32,fu,fv)
        matches = [name for name,image in variants.items() if image == display]
        assert len(matches) == 1, matches
        combinations[f'U{int(fu)}V{int(fv)}'] = matches[0]
    assert render(tex3ds,32,32,32,32) == original
    # Existing desktop TIM decoder is another independent check of native
    # row direction/index ordering. Payloads stay in memory, never exported.
    spec=importlib.util.spec_from_file_location('desktop_tim',PORT.parent/'pc_port/tools/tim2png.py')
    desktop=importlib.util.module_from_spec(spec);spec.loader.exec_module(desktop)
    native=[]
    reference=json.loads((PORT/'reports/tim-reference.json').read_text())
    with (PORT.parent/'sh1_data/sh1.bin').open('rb') as disc:
        for meta in reference['resources']:
            data=bytearray()
            for sector in range((meta['bytes']+2047)//2048):
                disc.seek((meta['lba']+sector)*2352+24);data+=disc.read(2048)
            rgba,w,h,_=desktop.decode_tim(data[:meta['bytes']])
            assert [w,h]==meta['logical'] and zlib.crc32(rgba)==meta['decoded_crc']
            native.append(dict(name=meta['name'],desktop_decoded_crc=f'{zlib.crc32(rgba):08X}'))
    if old:
        assert actual != tex3ds and combinations['U0V0'] == 'mirror_y'
    else:
        assert actual == tex3ds, 'Uploader differs from official tex3ds'
        assert list(combinations.values()) == ['identity','mirror_x','mirror_y','rotate_180']
    result = dict(result='old bug reproduced' if old else 'PASS', reference='installed devkitPro tex3ds RGBA8',
                  tex3ds_bytes_equal=actual==tex3ds, pattern_crc=f'{zlib.crc32(original):08X}',
                  tiled_crc=f'{zlib.crc32(actual):08X}', uv_combinations=combinations,
                  eight_distinct_transforms=list(variants), native_tim_reference=native,
                  pattern='TL red/TR green/BL blue/BR yellow, glyphs, arrow, notches')
    name = 'orientation-before.json' if old else 'orientation-pc.json'
    (PORT/'reports'/name).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__ == '__main__': main()
