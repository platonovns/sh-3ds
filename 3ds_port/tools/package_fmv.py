"""Identify and package the isolated FMV delta, without game/data binaries."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'3ds_port';BASE='518c44a9e'
def git(*args):return subprocess.check_output(['git','-C',str(R),*args])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(p):return p.read_bytes().replace(b'\r\n',b'\n')
def text_sha(p):return hashlib.sha256(canonical(p)).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def identify():
    names=set(git('diff','--name-only',BASE).decode().splitlines())
    names.update(git('ls-files','--others','--exclude-standard').decode().splitlines())
    deps=['pc_port/src/fmv/mdec.c','pc_port/src/fmv/fmv_player.cpp','pc_port/src/xa_player_software.c','src/main/filetable.c.USA.inc']
    names.update(deps)
    sources={n:dict(bytes=len(canonical(R/n)),sha256=text_sha(R/n)) for n in sorted(names)
        if not n.startswith(('docs/','3ds_port/reports/')) and (R/n).is_file()}
    digest=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    reports={x.name:text_sha(x) for x in sorted((P/'reports').glob('fmv-*')) if x.is_file() and x.name!='fmv-source-manifest.json'}
    mem=json.loads((P/'reports/fmv-arm-compile.json').read_text())['memory_budget']
    value=dict(source_id='native-fmv-src-'+digest[:16],source_sha256=digest,text_hash_policy='UTF-8 bytes with CRLF normalized to LF',context_base=git('rev-parse',BASE).decode().strip(),
        accepted_context='stage11a-cpu-B-src-8c51d74ee1feb7e0',hardware_candidate=False,published=False,sources=sources,reports=reports,
        memory=mem,total_movie_bytes=sum(mem[x] for x in ('movie_heap','linear_pcm','disc_cache','worker_stack')))
    write(P/'reports/fmv-source-manifest.json',value)
    inventory=json.loads((P/'reports/fmv-inventory.json').read_text())
    lines=['# Инвентарь FMV SLUS-00707 v1.1','',
        'Для всех: 320×208, MDEC v2, 15 fps; XA 4-bit stereo 37800 Hz, file/channel 1/1.',
        'Кадры/секунды — полный физический поток; cap — исходный open_main(id, 0).',
        'In-game SysState_Fmv передаёт blockCount без вычитания 7. LBA end не включён.','',
        '| ID / имя | LBA start–end | Кадры / сек | blockCount / cap | Аудиосекторы | Статический вызов |',
        '|---|---:|---:|---:|---:|---|']
    for e in inventory:
        calls=[]
        for x in e['invocations']:
            if 'event_param' in x:calls.append(Path(x['source']).parent.name+': param '+str(x['event_param']))
            else:calls.append(x['call'])
        lines.append(f"| {e['id']} / {e['name']} | {e['lba']}–{e['lba']+e['sectors']} | {e['frames']} / {e['duration_seconds']:.3f} | {e['limit']} / {e['limit']-7} | {sum(x['sectors'] for x in e['audio'])} | {'; '.join(calls) or 'Обычный вызов не найден'} |")
    lines+=['','Источник: [полный sector inventory](../3ds_port/reports/fmv-inventory.json).',
        'ZZ доступен по прямому developer API, но обычная ссылка в исходниках не обнаружена.',
        'Нулевой eventParam ZC выводится из C zero-initialization. Списки 8/9-sector frames, coding, padding и interleave gaps сохранены в JSON.']
    (R/'docs/3ds-fmv-inventory.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(value['source_id'],value['total_movie_bytes'])
def verify():
    m=json.loads((P/'reports/fmv-source-manifest.json').read_text())
    for n,v in m['sources'].items():assert text_sha(R/n)==v['sha256'],n
    for n,v in m['reports'].items():assert text_sha(P/'reports'/n)==v,n
    tests=(P/'reports/fmv-lifecycle.txt').read_text().splitlines();assert len(tests)==13 and all(x.endswith('PASS') for x in tests)
    rows=(P/'reports/fmv-offline.txt').read_text().splitlines();assert len(rows)==22 and all('compared=3' in x for x in rows[:21])
    assert rows[-1]=='malformed_vlc=1000 PASS'
    for n in ('fmv-internal-link.json','fmv-arm-codec.json'):assert json.loads((P/'reports'/n).read_text())['status']=='PASS'
    return m
def package():
    m=verify();assert not git('status','--porcelain').strip(),'Commit the isolated delta before packaging'
    dest=R.parent/'fmv-checkpoints';dest.mkdir(exist_ok=True)
    commit=git('rev-parse','HEAD').decode().strip();name=m['source_id']
    patch=dest/(name+'.patch');patch.write_bytes(git('diff','--binary',BASE,commit))
    receipt=dict(commit=commit,branch='codex/fmv-native',source_id=name,source_sha256=m['source_sha256'],context_base=m['context_base'],
        patch=patch.name,patch_sha256=sha(patch),hardware_candidate=False,published=False)
    archive=dest/(name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(patch,patch.name)
        z.writestr('receipt.json',json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        for n in ('docs/3ds-fmv-checkpoint.md','docs/3ds-fmv-inventory.md','docs/fmv-baseline.json'):z.write(R/n,n)
        for p in sorted((P/'reports').glob('fmv-*')):
            if p.is_file():z.write(p,p.relative_to(R).as_posix())
    receipt.update(archive=archive.name,archive_sha256=sha(archive))
    write(dest/(name+'.json'),receipt)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',action='store_true');ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.package:package()
    elif a.verify:print('PASS',verify()['source_id'])
    else:identify()
