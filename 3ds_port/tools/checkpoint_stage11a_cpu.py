"""Ordered reviewable source patches from the immutable F1 checkpoint; no Git tree reset."""
import difflib,hashlib,json,zipfile
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
DEST=PORT/'build/stage11a-cpu/checkpoints';DEST.mkdir(exist_ok=True)
archive=PORT/'baselines/stage11a-tracefix-c4c8ac8829ac3fac.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='306f4f0e7e845d57b1cb02289d09a2c16de751304a9f47da20dc6e443f52101a'
with zipfile.ZipFile(archive) as z:
 old={name:z.read(name).decode().replace('\r\n','\n') for name in z.namelist() if name.endswith(('.c','.cpp','.h','.py'))}
current=dict(old);records=[]
def checkpoint(name,changes):
 lines=[];proof={}
 for path,after in sorted(changes.items()):
  before=current.get(path,'');after=after.replace('\r\n','\n')
  if before==after:continue
  lines.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path if before else '/dev/null',tofile='b/'+path))
  proof[path]=dict(before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest())
  current[path]=after
 patch=DEST/(name+'.patch');patch.write_text(''.join(lines));records.append(dict(name=name,patch=patch.relative_to(ROOT).as_posix(),files=proof,sha256=hashlib.sha256(patch.read_bytes()).hexdigest()))
def read(path):return (ROOT/path).read_text()
checkpoint('02-spu-algorithm',{'3ds_port/tools/prepare_stage11a_cpu.py':read('3ds_port/tools/prepare_stage11a_cpu.py')})
main_path='3ds_port/source/main_game.c';render_path='3ds_port/source/render_3ds.c'
main=old[main_path].replace('else if (!render3ds_texture_update_rows(textures[slot],game_texture_decode_row,&decode))',
 'else if (!render3ds_texture_update_tiles(textures[slot],&decode,\n                    cache.entries[slot].tx0,cache.entries[slot].ty0,cache.entries[slot].tx1,cache.entries[slot].ty1))')
render=read(render_path);start=render.index('#ifdef SH_3DS_GAME\nbool render3ds_texture_update_tiles');end=render.index('bool render3ds_texture_update_rows(',start)
partial=old[render_path].replace('bool render3ds_texture_update_rows(',render[start:end]+'bool render3ds_texture_update_rows(')
flash={p:read(p) for p in ('3ds_port/include/game_texture_cache.h','3ds_port/source/game_texture_cache.c','3ds_port/include/game_texture_decode.h','3ds_port/source/game_texture_decode.c','3ds_port/include/render_3ds.h')}
flash.update({main_path:main,render_path:partial});checkpoint('03-flashlight-tiles',flash)
checkpoint('04-cafe-command-cpu',{main_path:read(main_path),render_path:render})
checkpoint('05-affinity-and-integration',{p:read(p) for p in ('3ds_port/source/game_audio_ndsp.c','3ds_port/source/game_spu.cpp','3ds_port/source/game_cpu_recorder.c','3ds_port/tools/build_stage11a_cpu.py','3ds_port/tools/release_stage11a_cpu.py')})
checkpoint('06-gte-clz',{'3ds_port/tools/prepare_stage11a_gte.py':read('3ds_port/tools/prepare_stage11a_gte.py')})
for p in flash:
 assert current[p]==read(p).replace('\r\n','\n'),p
result=dict(base_F1_archive=archive.relative_to(ROOT).as_posix(),base_F1_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
 git_tree_was_inherited_dirty=True,no_bulk_git_commit=True,newline_normalization='LF for review patches; raw final hashes are in source provenance',ordered_checkpoints=records,
 core3='Not implemented: no measured worthwhile post-F1 coarse job',hardware_acceptance=False)
(DEST/'index.json').write_text(json.dumps(result,indent=2)+'\n')
(PORT/'reports/stage11a-cpu-checkpoints.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps([r['name'] for r in records]))
