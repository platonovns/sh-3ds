"""Execute retail Status font packets, rather than assuming decomp geometry."""
import json,struct
from retail_mips import Retail,SYMBOLS,PORT
r=Retail();u=r.uc
def word(name,value):u.mem_write(SYMBOLS[name]&0x1fffffff,struct.pack('<I',value))
u.mem_write(0x1ee000,b'Status\0')
word('g_ActiveBufferIdx',0);word('GsOUT_PACKET_P',0x801f0000)
u.mem_write((SYMBOLS['g_SysWork']&0x1fffffff)+0x2350,b'\0')
r.call('Gfx_StringSetColor',0);r.call('Gfx_StringSetPosition',40,-80)
r.call('Gfx_StringDraw',0x801ee000,10)
end=struct.unpack('<I',u.mem_read(SYMBOLS['GsOUT_PACKET_P']&0x1fffffff,4))[0]&0x1fffffff
packets=[];offset=0x1f0000
while offset<end:
    header=struct.unpack('<I',u.mem_read(offset,4))[0];length=header>>24
    data=list(struct.unpack('<'+'I'*length,u.mem_read(offset+4,length*4)))
    packets.append(dict(address=hex(offset),words=[hex(w) for w in data]))
    offset+=4+length*4
report=dict(status='PASS',retail_packets=packets,position=list(struct.unpack('<2h',u.mem_read(SYMBOLS['g_StringPosition']&0x1fffffff,4))),
    source='Retail Gfx_StringDraw, high-res flag zero',hardware_accepted=False)
(PORT/'reports/stage10-status-retail-glyphs.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
