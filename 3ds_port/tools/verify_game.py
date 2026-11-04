#!/usr/bin/env python3
"""Audit the separate original-MainLoop application's linked closure and budget."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

port = Path(__file__).resolve().parents[1]
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
elf = port / 'silenthill_game.elf'
def run(tool, *args):
    return subprocess.check_output([prefix + tool, *map(str,args)], text=True)

payload = (port / 'silenthill_game.3dsx').read_bytes()
magic, header, reloc, version, flags, code, rodata, data, bss = struct.unpack_from('<4sHH6I',payload)
assert (magic,header,reloc,version,flags) == (b'3DSX',44,8,0,0)
smdh_offset,smdh_size,romfs = struct.unpack_from('<3I',payload,32)
assert romfs == 0 and smdh_size == 14016 and smdh_offset+smdh_size == len(payload)
assert payload[smdh_offset:] == (port/'silenthill_game.smdh').read_bytes()
assert 4*1024*1024 < bss < 5*1024*1024, bss
assert data >= bss
symbols = run('nm','-S',elf)
required = ('Game3ds_RetailMain','MainLoop','GameState_MainMenu_Update',
            'GameState_KcetLogo_MemCardCheck','BootScreen_KonamiScreenDraw',
            'BootScreen_KcetScreenDraw','Fs_QueueUpdate','Fs_QueueStartReadTim',
            'GsDrawOt','DrawOTag','C3D_DrawArrays')
required += ('GameBoot_MapLoad','GameBoot_InGameInit','g_MapOverlayHeader_map0_s00',
             'vcInitCamera','Vw_CoordHierarchyMatrixCompute','Ipd_ChunkCheckDraw','Gfx_InGameDraw')
for name in required:
    assert re.search(r'\b'+name+r'$',symbols,re.M), name
undefined = run('nm','-u',elf).splitlines()
weak_optional = {'__cxa_begin_cleanup','__cxa_call_unexpected','__cxa_type_match',
                 '__deregister_frame_info','__register_frame_info','__gnu_Unwind_Find_exidx',
                 'userAppExit','userAppInit'}
assert all(line.split()[0]=='w' and line.split()[1] in weak_optional for line in undefined),undefined
link_map = (port/'silenthill_game.map').read_text()
forbidden = r'\b(?:SDL_\w*|gl[A-Z]\w*|egl[A-Z]\w*|avcodec_\w*|avformat_\w*|C2D_\w*)\b'
assert not re.search(forbidden,link_map), 'desktop backend linked'
assert not re.search(r'PsyX_GPU\.o|data_stubs\.o|chara_global_data\.o',link_map)
libraries = sorted(set(re.findall(r'^LOAD .*?/([^/\n]+\.a)$',link_map,re.M)))
assert set(libraries) == {'libcitro3d.a','libctru.a','libm.a','libgcc.a','libg.a','libc.a','libsysbase.a'}
objects = sorted((port/'build-game').rglob('*.o'))
aliases=json.loads((port/'native_map_data.json').read_text())+json.loads((port/'native_body_data.json').read_text())
addresses={s[2]:int(s[0],16) for line in run('nm','-n',elf).splitlines() if len(s:=line.split())==3 and s[0]!='w'}
for alias in aliases:
    assert addresses[alias['symbol']]==addresses['g_PsxRam']+(int(alias['address'],16)&0x1fffff),alias
for obj in objects:
    listing = run('nm',obj)
    assert not re.search(forbidden,listing), obj
    assert not re.search(r'\b[TDB] (?:open|read|write|close|lseek)$',listing,re.M), obj
    assert not re.search(r'PGXP_|g_PsxUsePgxp|s_pgxp|s_vsFifo|s_matTwin|s_transTwin|WholeMap|FarQuad|\bGR_',listing),obj
    for alias in aliases:
        assert not re.search(r'\b[TDBR] '+re.escape(alias['symbol'])+'$',listing,re.M),('overlay alias overrides compiled symbol',obj,alias)
identity = re.findall(rb'stage[45]\.[0-9]-src-[0-9a-f]{16}',payload)
assert len(set(identity)) == 1,identity
print(json.dumps({'context':'ORIGINAL_MAINLOOP; build audit only, hardware pending',
    'build':identity[0].decode(),'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
    'code':code,'rodata':rodata,'data_with_bss':data,'bss':bss,'romfs_offset':romfs,
    'original_symbols_verified':required,'application_object_count':len(objects),'checked_overlay_data_aliases':len(aliases),
    'largest_static_symbols':run('nm','-S','--size-sort',elf).splitlines()[-12:],
    'libraries':libraries,'desktop_dependencies':'none in pre-GC application objects or link map',
    'undefined':undefined},indent=2))
