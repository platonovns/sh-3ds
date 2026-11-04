"""Local disc diagnostics; reference predictor follows FFmpeg xa_decode semantics.

WAV files are diagnostic outputs only, never runtime assets.
"""
from pathlib import Path
import ctypes as C
import subprocess, json, wave, array, math, collections

p = Path(__file__).resolve().parents[1]
root = p.parent
dest = p/'build/stage9-r4-analysis'
dest.mkdir(parents=True, exist_ok=True)
subprocess.run(['gcc','-shared','-fPIC','-O2',str(p/'build/audio/xa_decode.c'),'-o',str(dest/'decoder.so')],check=True)
lib = C.CDLL(str(dest/'decoder.so'))
lib.game_xa_decode.argtypes = [C.c_void_p,C.c_void_p,C.c_void_p]
subprocess.run(['g++','-shared','-fPIC','-O2',str(root/'pc_port/PsyCross/src/audio/PsyX_XAStream.cpp'),'-o',str(dest/'resampler.so')],check=True)
res = C.CDLL(str(dest/'resampler.so'))
res.PsyX_XAStream_Create.restype=C.c_void_p
res.PsyX_XAStream_Push.argtypes=[C.c_void_p,C.c_void_p,C.c_uint,C.c_uint,C.c_uint]
res.PsyX_XAStream_Pop44100Stereo.argtypes=[C.c_void_p,C.c_void_p,C.c_uint]
res.PsyX_XAStream_Destroy.argtypes=[C.c_void_p]

def stats(pcm):
    return dict(samples=len(pcm),peak=max(map(abs,pcm),default=0),saturated=sum(v in (-32768,32767) for v in pcm),
                rms=math.sqrt(sum(v*v for v in pcm)/max(1,len(pcm))),dc=sum(pcm)/max(1,len(pcm)))

def wav(name,pcm,rate):
    with wave.open(str(dest/(name+'.wav')),'wb') as w:
        w.setparams((2,2,rate,0,'NONE','not compressed'));w.writeframes(array.array('h',pcm).tobytes())

def reference(sector,hist,descriptors):
    out=[]
    for g in range(18):
        base=8+g*128
        for pair in range(4):
            lr=[]
            for ch in range(2):
                header=sector[base+4+pair*2+ch];descriptors[header]+=1
                shift=max(0,12-(header&15));f=header>>4
                a,b=[(0,0),(60,0),(115,-52),(98,-55),(122,-60)][f] if f<=4 else (0,0)
                block=[]
                for j in range(28):
                    nibble=(sector[base+16+pair+j*4]>>(ch*4))&15
                    if nibble>=8:nibble-=16
                    v=nibble*(1<<shift)+((hist[ch][0]*a+hist[ch][1]*b+32)>>6)
                    v=max(-32768,min(32767,v));hist[ch][1]=hist[ch][0];hist[ch][0]=v;block.append(v)
                lr.append(block)
            for l,r in zip(*lr):out.extend((l,r))
    return out

def run(idx):
    row=next(tuple(map(int,l.split())) for l in (p/'build/stage9-r2-xa-items.txt').read_text().splitlines() if int(l.split()[0])==idx)
    _,lba,ticks,file,channel=row
    hist=(C.c_int32*4)();refhist=[[0,0],[0,0]];descriptors=collections.Counter();native=[];ref=[];sectors=[]
    with (root/'sh1_data/sh1.bin').open('rb') as f:
        f.seek(lba*2352)
        while True:
            raw=f.read(2352)
            assert len(raw)==2352
            if raw[16]!=file or raw[17]!=channel or raw[18]&0x64!=0x64:continue
            assert raw[19]==1,raw[19]
            sector=raw[16:];out=(C.c_int16*4032)()
            n=lib.game_xa_decode(C.create_string_buffer(sector),out,hist)
            assert n==4032
            native.extend(out);ref.extend(reference(sector,refhist,descriptors));sectors.append(raw)
            if raw[18]&128 or len(native)//2/37800>=ticks/60:break
    outputs={}
    for name,pcm in [('r3',native),('reference',ref)]:
        wav(f'entry{idx}-{name}-decoded',pcm,37800)
        stream=res.PsyX_XAStream_Create();out=(C.c_int16*(len(pcm)*2))()
        a=(C.c_int16*len(pcm))(*pcm)
        assert res.PsyX_XAStream_Push(stream,a,len(pcm)//2,37800,2)
        count=res.PsyX_XAStream_Pop44100Stereo(stream,out,len(pcm))
        converted=list(out[:count*2]);wav(f'entry{idx}-{name}-resampled',converted,44100)
        assert count==len(pcm)//2*7//6
        assert abs(len(pcm)/2/37800-count/44100)<1e-12
        res.PsyX_XAStream_Destroy(stream)
        outputs[name]=dict(decoded=stats(pcm),resampled=stats(converted),source_frames=len(pcm)//2,output_frames=count,
                           source_seconds=len(pcm)/2/37800,output_seconds=count/44100)
    result=dict(entry=idx,lba=lba,sectors=len(sectors),authored_seconds=ticks/60,coding=1,rate=37800,channels=2,
                header_counts={hex(k):v for k,v in sorted(descriptors.items())},pcm_mismatches=sum(a!=b for a,b in zip(native,ref)),pipelines=outputs)
    assert result['pcm_mismatches']==0
    assert abs(len(native)/2/37800-ticks/60)<=1/60+1e-12
    return result

report=[run(i) for i in (13,)]
(p/'reports/stage9-r4-decode-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
