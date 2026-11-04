#!/usr/bin/env python3
"""Run linked Stage 1A upload and orientation page, sample actual submitted UVs."""
import json
import struct
import zlib
from run_arm_tim import Runner, SYMBOLS, PORT, sample_draw
from test_orientation import transforms, render

r = Runner()
r.uc.mem_write(SYMBOLS['renderer']+4,b'\1')  # Render3dsStats.ready
r.uc.mem_write(SYMBOLS['renderer']+80,b'\1') # active; sizeof(Render3dsStats)=80 on ARM EABI (includes timing counters)
r.bridge('C3D_FrameBegin',lambda *_:r.ret(0)) # Wait-idle allocation path: no live queue
r.bridge('C3D_FrameEnd',lambda *_:r.ret())
assert r.call('render_tests_init') == 1
assert len(r.texture_snapshots) == 2
checker, pattern = r.texture_snapshots
tex,pw,ph,tiled = pattern
raw = (PORT/'build/orientation-reference.tiled').read_bytes()
if len(raw)==4100: raw=raw[4:]
assert tiled==raw, 'Linked ARM row upload differs from installed tex3ds'
ppm=(PORT/'build/orientation-pattern.ppm').read_bytes().split(b'\n',3)[3]
original=b''.join(ppm[i:i+3]+b'\xff' for i in range(0,len(ppm),3))
variants=transforms(original,32)
r.capture_draws()
r.bridge('render3ds_begin_frame',lambda *_:r.ret(1))
r.bridge('render3ds_end_frame',lambda *_:r.ret())
assert r.call('render_orientation_draw') == 1
assert len(r.draws)==4
combinations={}
for i,(handle,blend,vertices) in enumerate(r.draws):
    assert handle==tex and blend==0
    actual=sample_draw(tiled,pw,ph,vertices,32,32)
    name=next(k for k,v in variants.items() if actual==v)
    combinations[f'U{i&1}V{i>>1}']=name
assert list(combinations.values())==['identity','mirror_x','mirror_y','rotate_180']
# Existing Stage 1A checker upload and its quad path: preserve all six cases,
# and verify the native top red/left green/bottom-right blue source markers.
r.draws.clear()
r.bridge('render3ds_set_scissor',lambda *_:r.ret(1))
assert r.call('render_tests_draw',0)==1
assert len(r.draws)==13
_,cw,ch,checker_data=checker
checker_draw=next(d for d in r.draws if d[0]==checker[0])
sampled=sample_draw(checker_data,cw,ch,checker_draw[2],32,32)
for x,y,color in ((8,0,(255,0,0,255)),(0,8,(0,255,0,255)),(31,31,(0,0,255,255))):
    assert sampled[(y*32+x)*4:(y*32+x+1)*4]==bytes(color)
# Projection uses screen coordinates only. Verify actual SDK OrthoTilt's axis
# permutation cancels the physical display orientation; it never transforms UV.
r.floats(0,400,240,0,1,-1)
r.call('Mtx_OrthoTilt',0x20000000,1)
stored=struct.unpack('<16f',r.uc.mem_read(0x20000000,64))
rows=[stored[i:i+4][::-1] for i in range(0,16,4)]
for x,y in ((0,0),(400,0),(0,240),(400,240),(123,87)):
    pos=(x,y,0,1)
    clip=[sum(a*b for a,b in zip(row,pos)) for row in rows]
    physical_x=(clip[0]+1)*120;physical_y=(clip[1]+1)*200
    assert abs((400-physical_y)-x)<0.001 and abs((240-physical_x)-y)<0.001
result=dict(result='PASS',execution='linked ARM1176 upload + quad UV generation; independent PICA nearest sampler; no hardware GPU',
            tex3ds_bytes_equal=True,uv_combinations=combinations,eight_transforms_distinct=len(set(variants.values()))==8,
            stage1a='six cases retained; 13 draws; checker source corners sampled correctly',projection='OrthoTilt axis mapping verified',
            tiled_crc=f'{zlib.crc32(tiled):08X}',sampled_crc=f'{zlib.crc32(original):08X}',
            allocation=dict(normal_descriptors=sum(r.allocations.values()),linear_textures=cw*ch*4+pw*ph*4))
(PORT/'reports/orientation-arm.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
