"""Reproduce the movie-only decoder fork; desktop source stays unchanged."""
from pathlib import Path
import hashlib
R=Path(__file__).resolve().parents[2]
src=R/'pc_port/src/fmv/mdec.c'
s=src.read_text().replace('#include "mdec.h"','#include "fmv_mdec.h"')
s=s.replace('#define MDEC_TRACE 2','#define MDEC_TRACE 0')
s=s.replace('static vlc_lut_entry_t s_vlc_lut[65536];','static vlc_lut_entry_t s_vlc_lut[512];')
s=s.replace('65536; i++','512; i++').replace('int prefix    = code << (16 - bits);','if (bits > 9) continue;\n        int prefix = code << (9 - bits);').replace('(1 << (16 - bits))','(1 << (9 - bits))')
# Trace-only diagnostic lookups are not compiled, but remove stale large indices.
start=s.index('    /* Sanity dump')
end=s.index('\n}',start)
s=s[:start]+s[end:]
s=s.replace('    int            cache_bits;','    int            cache_bits;\n    int            error;')
s=s.replace('    br->cache_bits = 0;','    br->cache_bits = 0;\n    br->error = 0;')
s=s.replace('br->data[br->byte_pos++]','br->data[(br->byte_pos++) ^ 1u]')
s=s.replace('static void br_fill_cache(bitreader_t* br) {','static void br_fill_cache(bitreader_t* br) {\n    if (br->error) return;')
s=s.replace('static void br_skip(bitreader_t* br, int n) {','static void br_skip(bitreader_t* br, int n) {\n    if (n > br->cache_bits) { br->error = 1; return; }')
s=s.replace('    uint32_t v = (n == 32)', '    if (n > br->cache_bits) { br->error = 1; return 0; }\n    uint32_t v = (n == 32)')
s=s.replace('        vlc_lut_entry_t e = s_vlc_lut[peek];','''        vlc_lut_entry_t e = s_vlc_lut[peek >> 7];
        if (e.flags & 0x80) {
            for (int i=0;i<MPEG12_RL_NB_ELEMS;i++) {
                int bits=s_vlc_code[i][1];
                if (bits>9 && (peek>>(16-bits))==s_vlc_code[i][0]) {
                    e=(vlc_lut_entry_t){s_vlc_run[i],s_vlc_level[i],(uint8_t)bits,0};break;
                }
            }
        }''')
s=s.replace('        ac_count++;','        if (br->error) return -1;\n        ac_count++;')
s=s.replace('            break;\n        }\n        if (br->error)', '            return -1;\n        }\n        if (br->error)')
s=s.replace('            break;\n        }\n\n        int j = s_zigzag[coef];','            return -1;\n        }\n\n        int j = s_zigzag[coef];')
s=s.replace('    return 0;\n}\n\n/* Separable IDCT','    return br->error ? -1 : 0;\n}\n\n/* Separable IDCT')
s=s.replace('    int ac_count = 0;', '    int ac_count = 0; (void)ac_count;')
s=s.replace('v = (v << 23) >> 23;', 'v = (int32_t)((uint32_t)v << 23) >> 23;')
s=s.replace('    int64_t temp[64];','''    /* Coefficients are saturated to 11 bits: the first pass is bounded
     * by 8*1024*32768 = 268435456. Keep only the second pass 64-bit. */
    int32_t temp[64];
    int ac=0;
    for(int i=1;i<64;i++)ac|=blk[i];
    if(!ac) {
        int64_t sum=(int64_t)blk[0]*23170*23170;
        int32_t v=(int32_t)((sum>>32)+((sum>>31)&1));
        v=(int32_t)((uint32_t)v<<23)>>23;
        int16_t value=(int16_t)clampi(v,-128,127);
        for(int i=0;i<64;i++)blk[i]=value;
        return;
    }''')
s=s.replace('sum += temp[u + y * 8] *', 'sum += (int64_t)temp[u + y * 8] *')
start=s.index('    /* The bitstream is stored', s.index('int mdec_decode_frame'))
end=s.index('    int mb_w =',start)
s=s[:start]+'''    if (ctx->width != 320 || ctx->height != 208 || n_bytes & 1) return -1;
    int qscale = bytes[4] | bytes[5]<<8;
    int version = bytes[6] | bytes[7]<<8;
    if (bytes[2]!=0 || bytes[3]!=0x38 || qscale<1 || qscale>63 || version!=2) return -1;
    bitreader_t br;
    br_init(&br, bytes+8, n_bytes-8);

'''+s[end:]
s=s.replace('                    free(swap);','').replace('    free(swap);','')
s=s.replace('    build_vlc_lut();\n\n    if (ctx->width','    build_vlc_lut();\n\n    if (ctx->width')
s='/* Movie-only fork of pc_port/src/fmv/mdec.c; input SHA256 '+hashlib.sha256(src.read_bytes()).hexdigest()+'\n * Bounded native halfword reader, small VLC prefix table, strict errors. */\n'+s
# Remove unused desktop chroma experiment and keep the fork's documentation exact.
start=s.index('/* MPEG-1 default CHROMA')
end=s.index('/* IDCT cosine matrix',start)
s=s[:start]+s[end:]
s=s.replace('VLC lookup table — built lazily once, 16-bit window','VLC lookup table — 9-bit prefix plus rare long-code search')
s=s.replace(' *  Index = next 16 bits of stream (MSB first). Result encodes either:', ' *  Index = next 9 bits of stream (MSB first). Result encodes either:')
s=s.replace(' * incoming bytes to big-endian halfwords once, then read bits MSB-first.', ' * incoming bytes virtually (pair-index XOR 1), then read bits MSB-first.')
s=s.replace(' * form, byte order is { byte1, byte0, byte3, byte2, ... }. We pre-swap\n *  the bytes once at frame open so we can read MSB-first sequentially.', ' * form, byte order is { byte1, byte0, byte3, byte2, ... }. Pair-index XOR\n *  reads this ordering directly without a temporary allocation.')
(R/'3ds_port/source/fmv_mdec.c').write_text(s)
(R/'3ds_port/include/fmv_mdec.h').write_text('''/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SH_FMV_MDEC_H
#define SH_FMV_MDEC_H
#include <stdint.h>
#include <stddef.h>
/* Movie-only fork, fixed 320x208 MDEC v2, RGB24 output. Single decode owner.
 * API is retained for byte comparison against the unmodified PC decoder. */
typedef struct {int width,height,output_signed;} mdec_ctx_t;
void mdec_init(mdec_ctx_t *,int width,int height);
/* Returns 260 macroblocks on success; negative on malformed/truncated VLC. */
int mdec_decode_frame(mdec_ctx_t *,const uint8_t *,size_t,uint8_t *rgb);
#endif
''')
print('Generated bounded decoder fork')
