#!/usr/bin/env python3
"""Private native overlay symbols and original data-RAM aliases (never PSX code).

Like the PC static overlay pipeline, rename every defined external. Also rename
undefined map-local data so it cannot accidentally resolve to another overlay.
The source symbol configuration supplies the actual per-overlay PSX addresses.
Native pointer/function tables provided elsewhere are explicit exclusions.
"""
import argparse, json, os, re, subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--object', type=Path, required=True)
p.add_argument('--map', required=True)
a = p.parse_args()
port = Path(__file__).resolve().parents[1]
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
config = port.parent / 'configs/USA/maps' / ('sym.' + a.map + '.txt')
text = config.read_text()
entries = {m[1]: (int(m[2], 16), 'type:func' in m[3]) for m in re.finditer(
    r'^(\w+)\s*=\s*(0x[0-9A-Fa-f]+);([^\n]*)', text, re.M)}
listing = subprocess.check_output([prefix+'nm', '-g', str(a.object)], text=True)
defined, undefined = set(), set()
for line in listing.splitlines():
    s = line.split()
    if len(s) == 3:
        defined.add(s[2])
    elif len(s) == 2 and s[0] == 'U':
        undefined.add(s[1])
external_native = {'STALKER_M5S02_ANIM_INFOS', 'KAUFMANN_M5S02_ANIM_INFOS', 'DAHLIA_M6S01_ANIM_INFOS', 'CYBIL_M6S01_ANIM_INFOS', 'GROANER_M6S00_ANIM_INFOS', 'CYBIL_ANIM_INFOS', 'sharedData_800CAA98_0_s01', 'GROANER_ANIM_INFOS',
                   'CAT_ANIM_INFOS', 'CREEPER_ANIM_INFOS', 'SPLIT_HEAD_ANIM_INFOS',
                   'LOCKER_DEAD_BODY_ANIM_INFOS', 'DAHLIA_ANIM_INFOS', 'ROMPER_ANIM_INFOS', 'KAUFMANN_ANIM_INFOS', 'LISA_ANIM_INFOS',
                   'ALESSA_ANIM_INFOS', 'BLOODSUCKER_ANIM_INFOS', 'DAHLIA_M3S06_ANIM_INFOS',
                   'TWINFEELER_ANIM_INFOS', 'FLOATSTINGER_ANIM_INFOS', 'GROANER_M4S02_ANIM_INFOS', 'GROANER_M5S01_ANIM_INFOS', 'HANGED_SCRATCHER_ANIM_INFOS', 'sharedData_800D5710_3_s03',
                   'sharedData_800D5A8C_3_s03'}
if a.map == 'map6_s04':
    external_native.update({'MONSTER_CYBIL_ANIM_INFOS', 'PARASITE_ANIM_INFOS',
                            'FLAUROS_ANIM_INFOS', 'LARVAL_STALKER_ANIM_INFOS',
                            'D_800C3868', 'D_800C39A0', 'D_800C4606'})
    external_native.discard('DAHLIA_ANIM_INFOS')
if a.map in ('map6_s02', 'map6_s03', 'map6_s04'):
    # These are resident bodyprog globals, not data owned by the map overlay.
    # In particular the UFO callback and credits share D_800C48F0.
    external_native.update({'D_800C4414', 'D_800C457C', 'D_800C4588',
                            'D_800C4590', 'D_800C48F0'})
if a.map in ('map7_s00', 'map7_s01', 'map7_s02', 'map7_s03'):
    external_native.update({'D_800C39A0', 'D_800C457C', 'D_800C4588', 'D_800C4590', 'D_800C4606', 'D_800C48F0'})
    external_native.difference_update({'LISA_ANIM_INFOS', 'DAHLIA_ANIM_INFOS',
                                       'KAUFMANN_ANIM_INFOS', 'BLOODSUCKER_ANIM_INFOS'})
if a.map == 'map7_s03':
    external_native.difference_update({'CYBIL_ANIM_INFOS', 'ALESSA_ANIM_INFOS'})
aliases = {}
for name in sorted(undefined - external_native):
    if name in entries:
        address, function = entries[name]
        if function:
            raise SystemExit('Unimplemented native overlay function: '+name)
        aliases[name] = address
    elif re.fullmatch(r'D_800[CDEF][0-9A-F]{4}', name):
        # Unnamed decomp data retains its own address in this overlay.
        aliases[name] = int(name[2:], 16)
renames = {s: a.map+'_'+s for s in sorted(defined | aliases.keys())}
rename_file = a.object.with_suffix('.renames')
rename_file.write_text(''.join(f'{s} {v}\n' for s,v in renames.items()))
subprocess.run([prefix+'objcopy', '--redefine-syms='+str(rename_file), str(a.object)], check=True)
ld = a.object.with_suffix('.ld')
ld.write_text('/* Original overlay DATA only. Native functions stay compiled. */\n'+
              ''.join(f'{renames[s]} = g_PsxRam + 0x{v & 0x1fffff:X};\n' for s,v in aliases.items()))
reports = port / 'build/reports'
reports.mkdir(parents=True, exist_ok=True)
(reports/('stage6-'+a.map+'-symbols.json')).write_text(json.dumps({
    'config':config.relative_to(port.parent).as_posix(), 'defined':sorted(defined),
    'aliases':{s:hex(v) for s,v in aliases.items()},
    'external_native_tables':sorted(external_native)}, indent=2)+'\n')
print(f'{a.map}: {len(defined)} private definitions, {len(aliases)} data-RAM aliases')


