"""Check the presentation pass explicitly rebinds the text stream and state."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]
s=(p/'source/render_3ds.c').read_text()
block=s[s.index('if(!renderer.display && counter_text[0])'):s.index('osTickCounterUpdate(&renderer.cpu_timer)')]
names=['C3D_BindProgram','C3D_FVUnifMtx4x4','C3D_GetAttrInfo','C3D_SetScissor',
       'C3D_StencilTest','C3D_AlphaTest','C3D_DepthTest','C3D_TexEnvInit','C3D_AlphaBlend',
       'BufInfo_Add(buffers,counter_vertices','C3D_SetBufInfo(buffers)','draw_arrays(0,counter_count)',
       'invalidate_draw_state()']
positions=[block.index(n) for n in names]
assert positions==sorted(positions)
assert 'invalidate_draw_state();' in s[s.index('bool render3ds_begin_frame'):s.index('uint32_t render3ds_psx_surface_bytes')]
print('PASS: counter-off guard, explicit overlay state, buffer rebind and next-frame invalidation')
