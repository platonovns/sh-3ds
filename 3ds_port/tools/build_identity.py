#!/usr/bin/env python3
"""Bounded source identity, independent of build timestamps and game data."""
from pathlib import Path
import hashlib

port = Path(__file__).resolve().parents[1]
paths = [p for directory in ('source', 'include', 'shaders', 'patches')
         for p in (port / directory).rglob('*') if p.is_file()]
paths += [port / n for n in ('Makefile', 'engine_sources.mk')]
paths += [port / 'Makefile.game'] if (port / 'Makefile.game').exists() else []
paths += [p for directory in ('include', 'src/bodyprog', 'src/screens', 'pc_port/include')
          for p in (port.parent / directory).rglob('*') if p.is_file() and p.suffix in ('.h', '.c')]
paths += [port.parent / 'src/main/main.c']
paths += [p for directory in ('src/maps/map0_s00', 'src/maps/map0_s01', 'src/maps/map0_s02', 'src/maps/map1_s00', 'src/maps/map2_s00', 'src/maps/characters', 'include/maps')
          for p in (port.parent / directory).rglob('*') if p.is_file()]
paths += [port.parent / 'src/maps' / n for n in ('particle.c', 'particle_glass.c', 'chara_util.c')]
paths += [port.parent / 'pc_port/src' / n for n in ('math_impl.c', 'psx_memory.c')]
paths += [port.parent / 'pc_port/build_gen/extracted_data/map0_s00_extracted_data.c',
          port / 'tools/extract_native_data.py', port / 'tools/extract_native_items.py',
          port / 'tools/build_identity.py',port/'native_map_data.ld',port/'native_map_data.json',port/'native_body_data.json']
paths += [port.parent/'pc_port/src'/n for n in ('cheryl_anim_info.c','groaner_anim_infos.c')]
paths += [port.parent / 'src/main' / n for n in ('fsqueue_1.c', 'fsqueue_2.c', 'fsqueue_3.c', 'fileinfo.c', 'fsmem.c')]
paths += [port/'tools/prepare_psycross.py',port/'tools/prepare_tmd_emit.py',port.parent/'pc_port/src/stubs/libgs_stub.c']
paths += [port/'tools/native_overlay.py',port.parent/'configs/USA/maps/sym.map0_s01.txt',
          port.parent/'pc_port/build_gen/extracted_data/map0_s01_extracted_data.c']
paths += [port.parent/'configs/USA/maps/sym.map2_s00.txt',
          port.parent/'pc_port/build_gen/extracted_data/map2_s00_extracted_data.c']
for overlay in ('map0_s02','map1_s00','map1_s01','map1_s02','map1_s03','map1_s04','map1_s05','map1_s06'):
    paths += [port.parent/'configs/USA/maps'/('sym.'+overlay+'.txt'),
              port.parent/'pc_port/build_gen/extracted_data'/(overlay+'_extracted_data.c')]
    paths += [p for p in (port.parent/'src/maps'/overlay).rglob('*') if p.is_file()]
paths += [port/'school_sources.mk']
for overlay in ('map2_s01','map2_s02','map2_s04'):
    paths += [port.parent/'configs/USA/maps'/('sym.'+overlay+'.txt'),
              port.parent/'pc_port/build_gen/extracted_data'/(overlay+'_extracted_data.c')]
    paths += [p for p in (port.parent/'src/maps'/overlay).rglob('*') if p.is_file()]
paths += [port/'post_school_sources.mk',port.parent/'pc_port/src/dahlia_anim_infos.c',
          port.parent/'pc_port/src/romper_anim_infos.c']
paths += [port.parent/'pc_port/src'/n for n in
          ('cat_anim_infos.c','creeper_anim_infos.c','split_head_anim_infos.c','locker_dead_body_anim_infos.c','pc_timing.c')]
paths += [port.parent/'pc_port/src'/n for n in ('cybil_anim_info.c','as_rodata_reformat.c','stubs/data_stubs.c')]
paths += [port/'tools/prepare_audio.py']
paths += list((port.parent/'src/bodyprog/libsd').glob('*'))
paths += list((port.parent/'src/bodyprog/sound').glob('*'))
paths += [port.parent/'pc_port/PsyCross/src/audio'/n for n in
          ('PsyX_SPUCore.cpp','PsyX_SPUCore.h','PsyX_SPUReverb.cpp','PsyX_SPUReverb.h',
           'PsyX_IdealReverb.h','PsyX_ReferenceReverb.h','PsyX_ReferenceResampler.h',
           'PsyX_XAStream.cpp','PsyX_XAStream.h')]
paths += [port.parent/'pc_port/src/xa_player_software.c']
for overlay in ('map3_s00','map3_s01','map3_s02','map3_s03','map3_s04','map3_s05','map3_s06'):
    paths += [port.parent/'configs/USA/maps'/('sym.'+overlay+'.txt'),
              port.parent/'pc_port/build_gen/extracted_data'/(overlay+'_extracted_data.c')]
    paths += [p for p in (port.parent/'src/maps'/overlay).rglob('*') if p.is_file()]
paths += [port/'alchemilla_sources.mk']
paths += [port.parent/'pc_port/src'/n for n in ('kaufmann_anim_infos.c','lisa_anim_infos.c','alessa_anim_infos.c','bloodsucker_anim_infos.c','puppet_nurse_data.c','dahlia_m3s06_anim_infos.c')]
for overlay in ('map4_s01','map4_s02','map4_s03','map4_s04','map4_s05'):
    paths += [port.parent/'configs/USA/maps'/('sym.'+overlay+'.txt'),
              port.parent/'pc_port/build_gen/extracted_data'/(overlay+'_extracted_data.c')]
    paths += [p for p in (port.parent/'src/maps'/overlay).rglob('*') if p.is_file()]
paths += [port/'block3_sources.mk']
paths += [port.parent/'pc_port/src'/n for n in ('twinfeeler_anim_infos.c','floatstinger_anim_infos.c','groaner_m4s02_anim_infos.c')]
for overlay in ('map5_s00','map5_s01','map5_s02','map5_s03','map6_s00','map6_s01','map6_s02','map6_s03','map6_s04','map7_s00','map7_s01','map7_s02','map7_s03'):
    paths += [port.parent/'configs/USA/maps'/('sym.'+overlay+'.txt'),
              port.parent/'pc_port/build_gen/extracted_data'/(overlay+'_extracted_data.c')]
    paths += [p for p in (port.parent/'src/maps'/overlay).rglob('*') if p.is_file()]
paths += [port/n for n in ('Makefile.fmv','sewer1_sources.mk','resort_sources.mk')]
paths += [p for p in (port/'stage11a_b').glob('*') if p.is_file()]
paths += [port.parent/'pc_port/src'/n for n in ('hanged_scratcher_anim_infos.c','groaner_m5s01_anim_infos.c','resort_anim_infos.c','stalker_m5s02_anim_infos.c')]
paths += [port.parent/'pc_port/src'/n for n in ('monster_cybil_anim_infos.c','parasite_anim_infos.c','flauros_anim_infos.c','larval_stalker_anim_infos.c')]
digest = hashlib.sha256()
for path in sorted(set(paths)):
    digest.update(path.relative_to(port.parent).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
identity = 'SH1-New3DS-v0.9.0-src-' + digest.hexdigest()[:11]
out = port / 'build/build_identity.h'
text = '#ifndef SH_BUILD_IDENTITY_H\n#define SH_BUILD_IDENTITY_H\n#define SH_BUILD_ID "'+identity+'"\n#endif\n'
out.parent.mkdir(exist_ok=True)
if not out.exists() or out.read_text() != text:
    out.write_text(text)
print(identity)


