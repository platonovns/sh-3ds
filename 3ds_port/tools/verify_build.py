#!/usr/bin/env python3
"""Audit Stage 3 packaging, ARM ABI, explicit closure and pre/post-GC memory."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

port = Path(__file__).resolve().parent.parent
prefix = str(Path(os.environ["DEVKITARM"]) / "bin" / "arm-none-eabi-")


def run(tool, *args):
    return subprocess.check_output([prefix + tool, *args], text=True)


payload = (port / "silenthill_3ds.3dsx").read_bytes()
magic, header, reloc, version, flags, code, rodata, data, bss = struct.unpack_from("<4sHH6I", payload)
assert magic == b"3DSX" and header == 44 and reloc == 8 and version == flags == 0
assert bss <= data
smdh_offset, smdh_size, romfs = struct.unpack_from("<3I", payload, 32)
assert romfs == 0, "Game data/RomFS must not be packaged"
assert smdh_size == 14016 and smdh_offset + smdh_size == len(payload)
assert payload[smdh_offset:smdh_offset + 4] == b"SMDH"
assert payload[smdh_offset:] == (port / "silenthill_3ds.smdh").read_bytes()
assert not subprocess.check_output(['git', 'ls-files', '--', 'sh1_data'], cwd=port.parent, text=True).strip()
ignored = subprocess.check_output(['git', 'check-ignore', 'sh1_data/sh1.bin', 'sh1_data/sh1.cue'],
                                  cwd=port.parent, text=True).splitlines()
assert len(ignored) == 2
synthetic_abi = port / 'build/abi-probe/values.bin'
# The emulator runtime contains its own shader caches/sysdata and a licensed
# image junction. Audit build outputs, never recurse into emulator storage.
emulator_runtime = port / 'build/azahar/user'
build_files = []
for folder, dirs, files in os.walk(port / 'build', followlinks=False):
    dirs[:] = [d for d in dirs if Path(folder) / d != emulator_runtime]
    build_files.extend(Path(folder) / f for f in files)
assert all(p == synthetic_abi and p.stat().st_size <= 1024 for p in build_files if p.suffix == '.bin')
assert not any(p.suffix == '.cue' for p in build_files)

elf = str(port / "silenthill_3ds.elf")
link_map = (port / "silenthill_3ds.map").read_text()
forbidden = (r"\b(?:SDL_[A-Za-z0-9_]*|gl[A-Z][A-Za-z0-9_]*|egl[A-Z][A-Za-z0-9_]*|"
             r"al[A-Z][A-Za-z0-9_]*|alc[A-Z][A-Za-z0-9_]*|avcodec_[A-Za-z0-9_]*|"
             r"avformat_[A-Za-z0-9_]*|sws_[A-Za-z0-9_]*|C2D_[A-Za-z0-9_]*)\b")
assert not re.search(forbidden, link_map), "Desktop graphics/audio/media or citro2d linked"
assert not re.search(r"\bMainLoop\b|map0_s00.*\.o|PsyX_GPU\.o|libapi\.o|libspu\.o|libcd\.o", link_map)
libraries = sorted(set(re.findall(r"^LOAD .*?/([^/\n]+\.a)$", link_map, re.M)))
assert set(libraries) == {"libcitro3d.a", "libctru.a", "libm.a", "libgcc.a", "libg.a", "libc.a", "libsysbase.a"}
objects = re.findall(r"^LOAD ([^/\n]+\.o)$", link_map, re.M)
expected_objects = ["main.o", "render_3ds.o", "render_tests.o", "engine_gate.o",
                    "psx_disc.o", "sh_disc.o", "psyq_file.o", "disc_gate.o",
                    "psx_vram.o", "psx_tim.o", "tim_gate.o", "tim_selftest.o", "stage4_report.o", "foundation.shbin.o",
                    "psx_memory.o", "rng.o", "memmove32.o", "fsmem.o", "PsyX_GTE.o", "libgte.o", "inline_c.o",
                    "fsqueue_1.o", "fsqueue_2.o", "fsqueue_3.o", "fileinfo.o", "stage4_fs.o"]
assert objects == expected_objects, objects
for symbol in ("C3D_Init", "C3D_DrawArrays", "C3D_TexInitWithParams", "C3D_FrameBegin", "C3D_FrameEnd"):
    assert re.search(r"\b" + symbol + r"\b", link_map), symbol
undefined = run("nm", "-u", elf).splitlines()
assert all(re.fullmatch(r"\s*w __(?:de)?register_frame_info", line) for line in undefined), undefined
dynamic = run("readelf", "-d", elf)
assert "There is no dynamic section" in dynamic
elf_header = run("readelf", "-h", elf)
assert "ELF32" in elf_header and "little endian" in elf_header
assert re.search(r"Machine:\s+ARM", elf_header) and "0x100000" in elf_header
assert "hard-float ABI" in elf_header
sections = run("size", "-A", elf)
sizes = {m[0]: int(m[1]) for m in re.findall(r"^(\.[\w.]+)\s+(\d+)\s+\d+", sections, re.M)}
symbols = run('nm', '-S', '--size-sort', elf)
static = []
for addr, size, kind, name in re.findall(r'^(\w+) (\w+) ([bBdDrR]) (.+)$', symbols, re.M):
    static.append({'symbol': name, 'bytes': int(size, 16), 'type': kind})
assert 3145728 + 1048580 <= sizes['.bss'] < 3145728 + 1048580 + 4096 + 32768, sizes['.bss']
assert {s['symbol'] for s in static if s['bytes'] > 65536} == {'g_PsxRam', 'stage3_vram'}
assert next(s['bytes'] for s in static if s['symbol'] == 'stage3_vram') == 1048580
for name in ('engine_gate_run', 'PsxMemory_Init', 'Rng_Rand32', 'Mem_Move32',
             'Fs_AllocMem', 'GTE_operator', 'RotTransPers', 'NormalClip', 'psx_tim_parse',
             'psx_tim_upload', 'psx_vram_load', 'psx_vram_decode', 'tim_gate_run', 'render3ds_texture_create_rows'):
    assert re.search(r'\b'+name+r'$', symbols, re.M), name
assert re.search(r'^\w+ 00300000 B g_PsxRam$', symbols, re.M)
assert re.search(r'^\w+ 00001000 B g_PsxScratchpad$', symbols, re.M)
for obj in expected_objects:
    listing = run('nm', '-S', str(port / 'build' / obj))
    assert not re.search(forbidden, listing), obj
    assert not re.search(r'PGXP_|g_PsxUsePgxp|g_PsyX_RtpSz|s_pgxp|s_vsFifo|s_matTwin|s_transTwin|s_vecTwin|'
                         r'WholeMap|FarQuad|\bGR_|ParsePrimitives|\bMainLoop\b', listing), obj
    # No SDK/file IO interposition by any application object (even before GC).
    assert not re.search(r'\b[TDB] (?:open|read|write|close|lseek|rename|ioctl)$', listing, re.M), obj
    if obj not in ('main.o', 'render_3ds.o', 'render_tests.o', 'foundation.shbin.o', 'psx_disc.o', 'sh_disc.o', 'psyq_file.o', 'disc_gate.o'):
        assert not re.search(r'\bU (?:open|read|write|close|lseek)$', listing, re.M), obj
report = {
    "3dsx": {"code": code, "rodata": rodata, "data_with_bss": data, "bss": bss, "romfs_offset": romfs},
    "sections": sizes, "libraries": libraries, "application_objects": objects,
    "engine_translation_units": 12,
    "largest_static_symbols": sorted(static, key=lambda s: -s['bytes'])[:20],
    "largest_code_symbols": sorted([{'symbol': name, 'bytes': int(size, 16)}
                                    for addr, size, name in re.findall(r'^(\w+) (\w+) [tT] (.+)$', symbols, re.M)],
                                   key=lambda s: -s['bytes'])[:15],
    "largest_by_section": {section: sorted([s for s in static if s['type'].lower() == kind],
                                           key=lambda s: -s['bytes'])[:8]
                           for section, kind in (('.bss', 'b'), ('.data', 'd'), ('.rodata', 'r'))},
    "stage2_explicit_allocations": {"normal": 0, "linear": 0, "stdio": "bounded FILE/buffer allocation, freed before main loop"},
    "stage3_explicit_allocations": {"static_vram": 1048580, "pica_linear": 589824,
        "texture_descriptors_normal": 56,
        "orientation_pattern_linear": 4096, "orientation_pattern_descriptor_normal": 28,
        "full_resource_or_rgba_buffers": 0,
        "decode_row_stack_max": 4096, "streaming_upload_row_stack_max": 2048,
        "runtime_peak": "sampled normal/linear minima during PICA upload in tim_test.txt; hardware values pending"},
    "shader_bytes": (port / "build" / "foundation.shbin").stat().st_size,
    "optional_weak_undefined": undefined,
    "files": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted(port.glob("silenthill_3ds.*"))},
    "runtime_memory_delta": "Read paired snapshots on hardware; cannot be measured by this build check",
}
stage3 = json.loads((port / 'reports/stage3-build.json').read_text())
report['delta_vs_stage3_accepted'] = {
    'sections': {name: sizes[name] - stage3['sections'][name] for name in ('.text', '.rodata', '.data', '.bss', '.tbss')},
    'files': {name: info['bytes'] - stage3['files'][name]['bytes'] for name, info in report['files'].items()}}
report['stage4_explicit_allocations'] = {
    'new_normal_heap': 0, 'new_linear_heap': 0, 'second_vram': 0,
    'file_staging': 'existing g_PsxRam FS_BUFFER_0, 77824 bytes maximum in this gate; no new allocation',
    'stdio': 'transient FILE/buffer allocation, closed before rendering; hardware sampled heap deltas only',
    'largest_new_statics': [s for s in static if s['symbol'] in (
        'g_FileTable', 'g_FsQueue', 'stage4_diag', 'parsed', 'image_rect', 'clut_rect')]}
baseline = json.loads((port / 'reports/stage1b-build.json').read_text())
report['delta_vs_stage1b'] = {
    'sections': {name: sizes[name] - baseline['sections'][name] for name in ('.text', '.rodata', '.data', '.bss', '.tbss')},
    'files': {name: info['bytes'] - baseline['files'][name]['bytes'] for name, info in report['files'].items()}
}
baseline2 = json.loads((port / 'reports/stage2-build.json').read_text())
report['delta_vs_stage2'] = {
    'sections': {name: sizes[name] - baseline2['sections'][name] for name in ('.text', '.rodata', '.data', '.bss', '.tbss')},
    'files': {name: info['bytes'] - baseline2['files'][name]['bytes'] for name, info in report['files'].items()}
}
orientation_baseline = port / 'reports/stage3-orientation-baseline.json'
if orientation_baseline.exists():
    before = json.loads(orientation_baseline.read_text(encoding='utf-8-sig'))['build']
    report['delta_vs_stage3_before_orientation'] = {
        'sections': {name: sizes[name]-before['sections'][name] for name in ('.text','.rodata','.data','.bss','.tbss')},
        'files': {name: info['bytes']-before['files'][name]['bytes'] for name,info in report['files'].items()},
        'explicit_allocations': {'normal':28,'linear':4096,'full_image_copies':0}}
report['backend_stack_frames'] = {p.name: p.read_text().splitlines() for p in (port / 'build').glob('*.su')}
print(json.dumps(report, indent=2))
