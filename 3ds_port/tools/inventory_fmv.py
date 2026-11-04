"""Metadata only: inspect all movie sectors in the user's original disc."""
import argparse, collections, hashlib, json, re, struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def inventory(bin_path):
    entries=[]
    table=(ROOT/'src/main/filetable.c.USA.inc').read_text()
    with open(bin_path,'rb') as f:
        exe=b''.join((f.seek(i*2352+24),f.read(2048))[1] for i in range(24,64))
        for match in re.finditer(r'/\*\s*(\d+)\s*\*/\s*\{\s*(0x[0-9a-f]+),\s*(\d+).*?// XA/([CMZ][^\s]+)',table):
            idx,base,limit,name=match.groups(); idx=int(idx);base=int(base,16)
            # The actual executable table is the authority, not the PC names.
            word=struct.unpack_from('<I',exe,47388+idx*12)[0]
            assert word&0x7ffff==base and (word>>19)&0xfff==int(limit),(name,word)
            sectors=int(name.split('_')[1]);frames=[];audio=collections.Counter();kinds=collections.Counter()
            positions=[];chunks=[];previous=0;variants=set();max_bytes=0;last_no=0
            f.seek(base*2352)
            for rel in range(sectors):
                raw=f.read(2352); assert len(raw)==2352
                assert raw[16:20]==raw[20:24]
                if raw[18]&4:
                    audio[(raw[16],raw[17],raw[19])]+=1;positions.append(rel);kinds['audio']+=1
                elif raw[24:28]==b'\x60\x01\x01\x80':
                    chunk,n,frame,size,w,h=struct.unpack_from('<HHIIHH',raw,28)
                    kinds['video']+=1
                    if chunk==0:
                        q,v=struct.unpack_from('<HH',raw,60)
                        frames.append((frame,rel,n,size,w,h,q,v));variants.add((w,h,v));max_bytes=max(max_bytes,size)
                        last_no=frame
                    chunks.append(chunk)
                else:kinds['padding']+=1
            assert frames
            # 150 sectors/s: observed slope avoids confusing 15fps with NTSC fields.
            slope=(frames[-1][1]-frames[0][1])/(frames[-1][0]-frames[0][0])
            entries.append(dict(id=idx,name=name,lba=base,sectors=sectors,limit=int(limit),
                dimensions_versions=sorted(variants),frames=len(frames),first_frame=frames[0][0],last_frame=last_no,
                sector_per_frame=slope,fps=round(150/slope,6),duration_seconds=round(len(frames)/15,4),
                kinds=dict(kinds),audio=[dict(file=k[0],channel=k[1],coding=k[2],sectors=v) for k,v in audio.items()],
                audio_sector_gaps=dict(collections.Counter(b-a for a,b in zip(positions,positions[1:]))),
                frame_sectors=sorted(set(x[2] for x in frames)),max_header_size=max_bytes,
                first_frames=frames[:4],last_frames=frames[-2:]))
    for e in entries:e['invocations']=[]
    by_id={e['id']:e for e in entries}
    for path in (ROOT/'src/maps').rglob('*events_data.c'):
        for block in path.read_text().split('},'):
            if '.sysState' not in block or 'SysState_Fmv' not in block:continue
            param=re.search(r'\.eventParam\s*=\s*(-?\d+)',block)
            value=int(param[1]) if param else 0
            idx=2072-value
            if idx in by_id:by_id[idx]['invocations'].append(dict(source=path.relative_to(ROOT).as_posix(),event_param=value))
    by_id[2053]['invocations'] += [dict(source='src/screens/stream/stream.c',call='MovieIntro/default'),dict(source='src/screens/stream/stream.c',call='MovieIntroAlternate',limit=2060)]
    by_id[2054]['invocations'].append(dict(source='src/screens/stream/stream.c',call='MovieIntro/extra option'))
    by_id[2055]['invocations'].append(dict(source='src/screens/stream/stream.c',call='MovieOpening/New Game'))
    return entries

def main():
    ap=argparse.ArgumentParser();ap.add_argument('bin');ap.add_argument('--out',default=str(ROOT/'3ds_port/reports/fmv-inventory.json'));args=ap.parse_args()
    entries=inventory(args.bin);p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(entries,indent=2)+'\n')
    for e in entries: print(e['name'],e['frames'],e['dimensions_versions'],e['fps'],e['audio'],e['frame_sectors'],e['max_header_size'])
if __name__=='__main__':main()
