#!/usr/bin/env python3
"""Independent Python oracle. Reads the user's BIN, writes metadata only."""
from pathlib import Path
import json
import struct
import zlib

PORT = Path(__file__).resolve().parents[1]
ROOT = PORT.parent


def inspect():
    vram = bytearray(1024 * 512 * 2)
    resources = []
    with (ROOT / 'sh1_data/sh1.bin').open('rb') as disc:
        def read(lba, size):
            out = bytearray()
            for sector in range((size + 2047) // 2048):
                disc.seek((lba + sector) * 2352 + 24)
                out += disc.read(2048)
            return out[:size]
        for file_id, name, lba, size, crc, iy, cy in (
                (0, '2ZANKO80.TIM', 64, 77568, 0x9fff51af, 0, 480),
                (6, 'FONT16.TIM', 647, 8448, 0x42714ea6, 256, 481)):
            data = read(lba, size)
            assert zlib.crc32(data) == crc
            magic, flags = struct.unpack_from('<II', data)
            assert magic == 16 and flags in (8, 9)
            mode = flags & 7
            offset = 8
            blocks = []
            for _ in range(2):
                length, x, y, w, h = struct.unpack_from('<I4H', data, offset)
                assert length == 12 + w * h * 2 and x + w <= 1024 and y + h <= 512
                blocks.append({'rect': [x, y, w, h], 'offset': offset + 12, 'bytes': length - 12})
                offset += length
            clut, image = blocks
            # Same explicit relocations as Fs_QueuePostLoadTim descriptor contract.
            for b, dx, dy in ((image, 640, iy), (clut, 0, cy)):
                _, _, w, h = b['rect']
                for row in range(h):
                    start = ((dy + row) * 1024 + dx) * 2
                    source = b['offset'] + row * w * 2
                    vram[start:start + w * 2] = data[source:source + w * 2]
            width, height = image['rect'][2] * (4 >> mode), image['rect'][3]
            rgba = bytearray()
            stp = transparent = 0
            for y in range(height):
                for x in range(width):
                    word = struct.unpack_from('<H', vram, ((iy + y) * 1024 + 640 + x // (4 >> mode)) * 2)[0]
                    bits = 4 << mode
                    index = (word >> ((x % (4 >> mode)) * bits)) & ((1 << bits) - 1)
                    color = struct.unpack_from('<H', vram, (cy * 1024 + index) * 2)[0]
                    rgba += bytes([((color >> shift & 31) << 3) | ((color >> shift & 31) >> 2)
                                   for shift in (0, 5, 10)] + [255 if color else 0])
                    stp += color >> 15
                    transparent += color == 0
            resources.append(dict(file_id=file_id, name=name, lba=lba, bytes=size, crc=crc,
                                  flags=flags, mode=mode, image=image, clut=clut,
                                  logical=[width, height], image_destination=[640, iy],
                                  clut_destination=[0, cy], consumed=offset, trailing_bytes=size-offset,
                                  trailing_nonzero=sum(c != 0 for c in data[offset:]),
                                  vram_crc=zlib.crc32(vram), decoded_crc=zlib.crc32(rgba),
                                  stp_texels=stp, transparent_texels=transparent))
        anm = read(802, 60160)
        assert zlib.crc32(anm) == 0x6da30665
        offset, rotations, translations, stride, bones, _, mask, size, frames, scale, root = struct.unpack_from('<HBBHBBIIHBB', anm)
        assert offset + stride * frames == size <= len(anm)
        assert 20 + bones * 6 <= offset and stride == rotations * 9 + translations * 3
        for b in range(bones):
            parent, rot, trans = struct.unpack_from('<3b', anm, 20 + b * 6)
            assert -1 <= parent < bones and -1 <= rot < rotations and -1 <= trans < translations
        audit = dict(file_id=19, name='AR.ANM', bytes=len(anm), crc=zlib.crc32(anm),
                     data_offset=offset, rotation_bones=rotations, translation_bones=translations,
                     stride=stride, bones=bones, active_mask=mask, declared_bytes=size,
                     frames=frames, scale=scale, root_y=root, bind_pose_bytes=bones*6,
                     pointers='No serialized pointers; offsets relative to header; consumer not executed')
    return dict(resources=resources, anm=audit)


if __name__ == '__main__':
    result = inspect()
    (PORT / 'reports/tim-reference.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['/* Independent inspect_tim.py oracle; metadata/checksums only. */',
             '#ifndef SH_TIM_REFERENCE_H', '#define SH_TIM_REFERENCE_H',
             'static const uint32_t tim_reference[2][4] = {']
    for r in result['resources']:
        lines.append('    {' + ', '.join(f'0x{r[k]:08x}u' for k in ('crc', 'vram_crc', 'decoded_crc', 'stp_texels')) + '},')
    lines += ['};', '#endif', '']
    (PORT / 'include/tim_reference.h').write_text('\n'.join(lines))
    print(json.dumps(result, indent=2))
