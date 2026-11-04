#!/usr/bin/env python3
"""Read-only, independent BIN reference. Writes metadata/checksums only."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import zlib

ROOT = Path(__file__).resolve().parents[2]


def inspect(image, cue):
    size = image.stat().st_size
    assert size % 2352 == 0
    sha = hashlib.sha256()
    modes = collections.Counter()
    bad_headers = 0
    start = time.perf_counter()
    with image.open('rb') as f:
        for lba in range(size // 2352):
            s = f.read(2352)
            sha.update(s)
            mode = s[15]
            modes[f'mode{mode}_form{2 if s[18] & 32 else 1}'] += 1
            n = lba + 150
            bcd = lambda x: (x // 10) * 16 + x % 10
            addr = bytes((bcd(n // 4500), bcd(n // 75 % 60), bcd(n % 75)))
            if s[:12] != b'\x00' + b'\xff' * 10 + b'\x00' or s[12:15] != addr or mode != 2 or s[16:20] != s[20:24]:
                bad_headers += 1
    scan_ms = (time.perf_counter() - start) * 1000
    with image.open('rb') as f:
        def raw(lba):
            f.seek(lba * 2352)
            s = f.read(2352)
            assert len(s) == 2352
            return s

        def data(lba):
            s = raw(lba)
            assert s[15] == 2 and not s[18] & 32
            return s[24:2072]

        def read(lba, count):
            # Only used for small metadata/executable (not the whole image).
            return b''.join(data(lba + i) for i in range((count + 2047) // 2048))[:count]

        pvd = data(16)
        assert pvd[:7] == b'\x01CD001\x01'
        def directory(lba, length):
            records = []
            b = read(lba, length)
            off = 0
            while off < len(b):
                n = b[off]
                if not n:
                    off = (off // 2048 + 1) * 2048
                    continue
                r = b[off:off + n]
                assert n >= 34 and len(r) == n
                name = r[33:33 + r[32]].decode('ascii')
                if name not in ('\0', '\1'):
                    records.append(dict(name=name, lba=int.from_bytes(r[2:6], 'little'), bytes=int.from_bytes(r[10:14], 'little'), flags=r[25]))
                off += n
            return records
        root_lba, root_size = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
        records = directory(root_lba, root_size)
        exe_rec = next(r for r in records if r['name'] == 'SLUS_007.07;1')
        exe = read(exe_rec['lba'], exe_rec['bytes'])
        exe_sha1 = hashlib.sha1(exe).hexdigest()
        expected_sha1 = re.search(r'sha1: (\w+)', (ROOT / 'configs/USA/main.yaml').read_text())[1].lower()
        assert exe_sha1 == expected_sha1, 'Executable differs from repository USA revision; analyze before generating tests'
        table = []
        for line in (ROOT / 'src/main/filetable.c.USA.inc').read_text().splitlines():
            m = re.search(r'/\*\s*(\d+)\s*\*/\s*\{\s*(0x\w+),\s*(\d+),\s*(\d+),\s*FN\((.*?)\),\s*(\d+)\s*\}.*// (.*)', line)
            if not m:
                continue
            idx, lba, blocks, path, chars, typ, name = m.groups()
            chars = re.findall(r"'(.)'", chars)
            packed = [sum(((ord(c) - 32) & 63) << (6 * j) for j, c in enumerate(chars[i:i + 4])) for i in (0, 4)]
            words = (int(lba, 16) | int(blocks) << 19, int(path) | packed[0] << 4, packed[1] | int(typ) << 24)
            table.append(dict(id=int(idx), lba=int(lba, 16), bytes=int(blocks)*256, name=name, words=words))
        packed_table = b''.join(struct.pack('<III', *r['words']) for r in table)
        table_off = exe.find(packed_table)
        assert table_off >= 0 and len(table) == 2074, 'Full original table must match, not guessed offsets'
        tests = []
        def add(name, kind, lba, count, file_id=-1):
            t = time.perf_counter()
            if kind == 'raw':
                payload = raw(lba)
            else:
                payload = read(lba, count)
            tests.append(dict(id=len(tests) + 1, name=name, kind=kind, lba=lba, bytes=count, file_id=file_id,
                              crc32=f'{zlib.crc32(payload):08x}', sha256=hashlib.sha256(payload).hexdigest(),
                              pc_ms=round((time.perf_counter()-t)*1000, 4)))
        for lba in (16, size // 2352 // 2, size // 2352 - 1):
            add(f'raw_{lba}', 'raw', lba, 2352)
            if not raw(lba)[18] & 32:
                add(f'data_{lba}', 'data', lba, 2048)
        # Form 1 near end of data area even if the physical tail is XA Form 2.
        end_data = size // 2352 - 1
        while raw(end_data)[18] & 32:
            end_data -= 1
        if end_data != size // 2352 - 1:
            add('data_tail_form1', 'data', end_data, 2048)
        for idx in (0, 3, 6, 19, 43):
            r = table[idx]
            add(r['name'], 'file', r['lba'], r['bytes'], idx)
        # ISO structures and complete executable/table participate in identity.
        identity = []
        for r in [dict(name='PVD', lba=16, bytes=2048), dict(name='ROOT', lba=root_lba, bytes=root_size),
                  next(r for r in records if r['name'] == 'SYSTEM.CNF;1'), exe_rec]:
            identity.append(dict(name=r['name'], lba=r['lba'], bytes=r['bytes'], crc32=f"{zlib.crc32(read(r['lba'], r['bytes'])):08x}"))
        body = table[3]
        body_sha1 = hashlib.sha1(read(body['lba'], body['bytes'])).hexdigest()
        # Config hash may exclude sector padding; report exact FS block range separately.
        report = dict(image_bytes=size, sectors=size//2352, sha256=sha.hexdigest(), cue=cue.read_text().splitlines(),
                      cue_filename_override=True, track_count=1, mode='MODE2/2352', index01=0, pregap_stored=False,
                      sector_formats=dict(modes), invalid_headers=bad_headers, scan_ms=round(scan_ms, 3),
                      executable=exe_rec, exe_sha1=exe_sha1, exe_sha256=hashlib.sha256(exe).hexdigest(),
                      revision='USA SLUS-00707 v1.1 (repository USA executable + all 2074 table entries match)',
                      table_offset=table_off, table_bytes=len(packed_table), table_crc32=f'{zlib.crc32(packed_table):08x}',
                      bodyprog_block_range_sha1=body_sha1, root=records, identity=identity, tests=tests)
    assert not bad_headers
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--image', type=Path, default=ROOT / 'sh1_data/sh1.bin')
    p.add_argument('--cue', type=Path, default=ROOT / 'sh1_data/sh1.cue')
    p.add_argument('--generate', action='store_true', help='Explicitly generate checksum-only C reference profile')
    a = p.parse_args()
    r = inspect(a.image, a.cue)
    (ROOT / '3ds_port/reports/disc-reference.json').write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps(r, indent=2))
    if a.generate:
        lines = ['/* Checksum/metadata only. Generated by inspect_disc.py --generate. */',
                 '#ifndef SH_DISC_REFERENCE_H', '#define SH_DISC_REFERENCE_H',
                 f'#define SH_DISC_BYTES {r["image_bytes"]}u', f'#define SH_DISC_SECTORS {r["sectors"]}u',
                 f'#define SH_EXE_LBA {r["executable"]["lba"]}u', f'#define SH_EXE_BYTES {r["executable"]["bytes"]}u',
                 f'#define SH_TABLE_OFFSET {r["table_offset"]}u', f'#define SH_TABLE_CRC 0x{r["table_crc32"]}u',
                 '#ifndef SH_READS_ONLY', 'static const DiscReference sh_identity[] = {']
        for t in r['identity']:
            lines.append(f'    {{"{t["name"]}", {t["lba"]}u, {t["bytes"]}u, 0x{t["crc32"]}u, -1, 0}},')
        lines += ['};', '#endif', '#ifndef SH_IDENTITY_ONLY', 'static const DiscReference sh_reads[] = {']
        for t in r['tests']:
            lines.append(f'    {{"{t["name"]}", {t["lba"]}u, {t["bytes"]}u, 0x{t["crc32"]}u, {t["file_id"]}, {int(t["kind"] == "raw")}}},')
        lines += ['};', '#endif', '#endif', '']
        (ROOT / '3ds_port/include/disc_reference.h').write_text('\n'.join(lines))
