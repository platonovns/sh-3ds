"""Set the unsigned homebrew CIA's TMD version to 0.9.1 (145)."""
from pathlib import Path
import struct
import sys
p=Path(sys.argv[1]); b=bytearray(p.read_bytes())
align=lambda n:(n+63)&~63
header, _, _, cert, ticket, tmdsize, _, _ = struct.unpack_from('<IHHIIIIQ',b)
tmd=align(align(align(header)+cert)+ticket)
assert tmdsize>=0x1e0 and struct.unpack_from('>I',b,tmd)[0]==0x10004
assert struct.unpack_from('>Q',b,tmd+0x140+0x4c)[0]==0x000400000f53d190
struct.pack_into('>H',b,tmd+0x140+0x9c,145)
p.write_bytes(b)
