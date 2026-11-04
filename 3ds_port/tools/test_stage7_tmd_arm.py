#!/usr/bin/env python3
"""Exercise every retail item TMD using the actual linked ARM GS backend."""
import json, struct
from pathlib import Path
# Share the CPU/SDK recorder without executing the unrelated GPU test body.
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
namespace={'__file__':str(fixture),'__name__':'stage7_gpu_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),namespace)
Machine=namespace['Machine'];symbols=namespace['symbols'];port=namespace['port']
m=Machine();ram=symbols['g_PsxRam'];base=ram+0x10000;ot=symbols['g_OrderingTable0'];obj=ram+0x500
m.call('GsInitGraph2',320,224,0,0,0)
matrix=struct.pack('<9h2x3i',4096,0,0,0,4096,0,0,0,4096,0,0,4096)
m.uc.mem_write(ram+0x600,matrix);m.call('GsSetLsMatrix',ram+0x600);m.call('SetGeomScreen',224)
table=bytes(m.uc.mem_read(symbols['g_FileTable'],2074*12))
results=[]
with (port.parent/'sh1_data/sh1.bin').open('rb') as disc:
    for index in range(1489,1600):
        a,b,c=struct.unpack_from('<3I',table,index*12)
        path=b&15;name=''.join(chr(((b>>4 if j<4 else c)>>((j%4)*6)&63)+32) for j in range(8)).strip()
        if path!=4 or c>>24&15!=8:continue
        lba=a&0x7ffff;size=((a>>19)&4095)*256
        if size<12 or size>0x60000:continue
        data=bytearray()
        for sector in range((size+2047)//2048):
            disc.seek((lba+sector)*2352+24);data.extend(disc.read(2048))
        data=data[:size]
        if struct.unpack_from('<I',data)[0]!=0x41:continue
        count=struct.unpack_from('<I',data,8)[0]
        if not 0<count<=64:continue
        m.uc.mem_write(base,bytes(data));m.call('GsMapModelingData',base+4)
        m.call('GsMapModelingData',base+4) # Idempotent, never double-relocate.
        primitives=0;draws=0
        for model in range(count):
            arena=ram+0x1a2600;m.word('g_ActiveBufferIdx',0);m.word('GsOUT_PACKET_P',arena)
            m.call('GsClearOt',0,0,ot);m.uc.mem_write(obj,bytes(16));m.call('GsLinkObject4',base+12+model*28,obj,0)
            m.draws=[];m.call('GsSortObject4J',obj,ot,1,ram+0x800)
            used=m.get_word('GsOUT_PACKET_P')-arena
            assert 0<=used<=32768,(name,model,used)
            m.call('GsDrawOt',ot);draws+=len(m.draws)
            primitives+=struct.unpack_from('<I',data,12+model*28+20)[0]
        results.append({'file':index,'name':name,'models':count,'source_primitives':primitives,'visible_packets':draws})
assert len(results)>=10 and sum(r['visible_packets'] for r in results)>0,results
report={'status':'PASS','execution':'actual ARM GS and retail TMD bytes; SDK recorder, no visual acceptance','files':results,'total_models':sum(r['models'] for r in results),'linear_model_cache_bytes':0}
(port/'reports/stage7-tmd-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
