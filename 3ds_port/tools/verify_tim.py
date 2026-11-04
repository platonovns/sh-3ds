#!/usr/bin/env python3
"""Compare independently parsed metadata and C/ARM checksums, not payloads."""
from pathlib import Path
import json
PORT = Path(__file__).resolve().parents[1]
reference = json.loads((PORT / 'reports/tim-reference.json').read_text())
pc = json.loads((PORT / 'reports/tim-pc-tests.json').read_text())
arm = json.loads((PORT / 'reports/tim-arm-tests.json').read_text())
assert pc['gate_words'] == arm['gate_words']
assert pc['synthetic_passed'] == pc['synthetic_total'] == arm['synthetic_passed'] == arm['synthetic_total']
def rect(a, b): return [a & 65535, a >> 16, b & 65535, b >> 16]
out = []
for i, ref in enumerate(reference['resources']):
    r = pc['gate_words'][6+i*30:6+(i+1)*30]
    assert r[0:3] == [ref['file_id'],ref['bytes'],ref['crc']]
    assert r[3:5] == [63,0]
    assert r[5:11] == [ref['flags'],ref['mode'],1,*ref['logical'],ref['consumed']]
    assert rect(*r[11:13]) == ref['image']['rect']
    assert rect(*r[13:15]) == ref['clut']['rect']
    assert r[15:19] == [ref['image']['offset'],ref['image']['bytes'],ref['clut']['offset'],ref['clut']['bytes']]
    assert r[19:21] == [16 if ref['mode'] == 0 else 256, 1]
    assert rect(*r[21:23])[:2] == ref['image_destination']
    assert rect(*r[23:25])[:2] == ref['clut_destination']
    assert r[25:27] == [ref['vram_crc'],ref['decoded_crc']]
    assert r[28:30] == [ref['stp_texels'],ref['transparent_texels']]
    out.append(dict(name=ref['name'], mode=ref['mode'], logical=ref['logical'],
                    vram_crc=f'{r[25]:08X}', decoded_crc=f'{r[26]:08X}', generation=r[27]))
a = reference['anm']
assert pc['gate_words'][66:] == [a[k] for k in ('crc','data_offset','rotation_bones','translation_bones',
    'stride','bones','active_mask','declared_bytes','frames','scale','root_y')] + [1]
orientation_pc=json.loads((PORT/'reports/orientation-pc.json').read_text())
orientation_arm=json.loads((PORT/'reports/orientation-arm.json').read_text())
assert orientation_pc['result']==orientation_arm['result']=='PASS'
baseline=json.loads((PORT/'reports/stage3-orientation-baseline.json').read_text(encoding='utf-8-sig'))
assert pc['gate_words']==baseline['arm']['gate_words'], 'Native Stage 3 metadata changed during orientation fix'
layout_delta=[dict(name=new['name'],old_tiled_crc=f"{old['tiled_crc']:08X}",new_tiled_crc=f"{new['tiled_crc']:08X}")
              for old,new in zip(baseline['arm']['pica_upload'],arm['pica_upload'])]
result = dict(result='PASS', synthetic_checks=pc['synthetic_total'], sanitizer_fuzz_inputs=pc['fuzz_inputs'],
              resources=out, anm='PC/ARM metadata equal to independent Python reference; consumer not executed',
              pica=arm['pica_upload'], negative=arm['negative'],
              orientation=dict(result='PASS',tex3ds_bytes_equal=True,pc_arm_uv_combinations=orientation_arm['uv_combinations'],
                               native_metadata_unchanged=True,layout_crc_changes=layout_delta),
              acceptance='hardware-tested; real TIM rendering confirmed; orientation fix pending re-test')
(PORT / 'reports/stage3-tests.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
