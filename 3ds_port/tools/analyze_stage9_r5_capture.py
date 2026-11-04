"""Compare observed DSP waveform time positions with the continuous ARM WAV."""
from pathlib import Path
import wave,json,sys
import numpy as np
p=Path(__file__).resolve().parents[1];label=sys.argv[1] if len(sys.argv)>1 else 'observe'
dest=p/f'reports/stage9-r5-{label}-azahar'
def load(file):
    with wave.open(str(file),'rb') as w:return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).astype(float),w.getframerate()
template,src_rate=load(p/'build/stage9-r4-analysis/entry13-corrected-arm-spu.wav')
actual,rate=load(dest/'dsp-output.wav')
rate=268111856/8192
reference=np.interp(np.arange(int(len(template)/src_rate*rate))*src_rate/rate,np.arange(len(template)),template[:,0])
x=actual[:,0];rows=[];nfft=1<<int(np.ceil(np.log2(len(x)+8192)))
for position in np.arange(.12,2.85,.12):
    start=int(position*rate);y=reference[start:start+int(.09*rate)]
    if len(y)<int(.09*rate):continue
    energy=np.sqrt(np.sum(y*y))
    if energy<1000:continue
    dot=np.fft.irfft(np.fft.rfft(x,nfft)*np.conj(np.fft.rfft(y,nfft)),nfft)[:len(x)-len(y)+1]
    sums=np.r_[0,np.cumsum(x*x)];norm=np.sqrt(np.maximum(1,sums[len(y):]-sums[:-len(y)]))*energy
    corr=dot/norm;at=int(np.argmax(corr));score=float(corr[at])
    rows.append(dict(source_seconds=float(position),observed_seconds=at/rate,offset_seconds=at/rate-position,correlation=score))
report=dict(scope=__doc__,reference_sample_rate=src_rate,dsp_sample_rate=rate,windows=rows)
(dest/'waveform-alignment.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
