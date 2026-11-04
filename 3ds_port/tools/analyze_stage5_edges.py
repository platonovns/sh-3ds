#!/usr/bin/env python3
"""Audit exact submitted native PSX triangles, independent of bridge helper."""
import csv,json,sys
from pathlib import Path
groups={}
for row in csv.DictReader(Path(sys.argv[1]).open()):groups.setdefault(int(row['primitive']),[]).append(row)
rejected=[];total=0
for prim,rows in groups.items():
    assert len(rows) in (3,6)
    for i in range(0,len(rows),3):
        tri=rows[i:i+3];total+=1
        x=[float(v['x']) for v in tri];y=[float(v['y']) for v in tri]
        dx=max(x)-min(x);dy=max(y)-min(y)
        if dx>1023 or dy>511:
            rejected.append({'primitive':prim,'triangle':i//3,'page':int(tri[0]['page']),
                'clut':int(tri[0]['clut']),'textured':int(tri[0]['textured']),
                'width':dx,'height':dy,'xy':list(zip(x,y)),
                'bbox_intersects_source_view':min(x)<320 and max(x)>0 and min(y)<224 and max(y)>0})
result={'source':sys.argv[1],'triangles':total,'oversized_count':len(rejected),
        'oversized_textured_view_candidates':sum(r['textured'] and r['bbox_intersects_source_view'] for r in rejected),
        'rejected':rejected,
        'scope':'Captured polygon/rectangle triangle list; rectangle dimensions in this frame are below limits. Bbox intersection is a candidate, not a pixel-coverage proof.'}
print(json.dumps(result,indent=2))
