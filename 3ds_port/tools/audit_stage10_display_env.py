"""Execute retail libgs to establish the real progressive/interlaced environment."""
import json,struct
from retail_mips import Retail,SYMBOLS,PORT
image=None;cases=[]
for height in (224,448):
    r=Retail(image);image=bytes(r.uc.mem_read(0,0x300000))
    boundaries=[]
    for name in ('ResetGraph','SetDispMask','DrawSync','VSync','GetVideoMode','SetVideoMode','SetRCnt','StartRCnt','ResetRCnt'):
        if name in SYMBOLS:r.hook(name,lambda *_:r.ret(0))
    for name in ('PutDrawEnv','PutDispEnv'):
        def submit(ptr,*_,name=name):
            boundaries.append(dict(call=name,pointer=hex(ptr),words=list(struct.unpack('<6h',r.uc.mem_read(ptr&0x1fffffff,12)))))
            r.ret(ptr)
        r.hook(name,submit)
    r.call('GsInitGraph2',320,height,4|(height>240),1,0)
    r.call('GsDefDispBuff2',0,32,0,32 if height>240 else 256)
    r.uc.mem_write((SYMBOLS['GsDRAWENV']&0x1fffffff)+6,struct.pack('<h',224))
    r.call('GsInit3D')
    states=[]
    for i in range(2):
        r.call('GsSwapDispBuff')
        states.append(dict(draw=list(struct.unpack('<6h',r.uc.mem_read(SYMBOLS['GsDRAWENV']&0x1fffffff,12))),
            disp=list(struct.unpack('<8h',r.uc.mem_read(SYMBOLS['GsDISPENV']&0x1fffffff,16))),active=r.call('GsGetActiveBuff')))
    cases.append(dict(height=height,states=states,boundaries=boundaries))
report=dict(scope=__doc__,cases=cases,hardware_accepted=False)
(PORT/'reports/stage10-display-retail-env.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
