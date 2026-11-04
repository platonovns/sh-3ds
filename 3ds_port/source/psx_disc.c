#include "psx_disc.h"
#include <errno.h>
#include <limits.h>
#include <string.h>
#include <stdlib.h>
#ifdef SH_3DS_GAME
#include "game_profile.h"
#include "game_io.h"
#include "game3ds.h"
#endif

static unsigned bcd(unsigned n) { return (n / 10u) * 16u + n % 10u; }
static int unbcd(unsigned n) { return (n & 15u) > 9u || (n >> 4) > 9u ? -1 : (int)((n >> 4) * 10u + (n & 15u)); }

int PsxDisc_LbaToMsf(int32_t lba, PsxMsf *out)
{
    if (!out || lba < -150 || lba > 449849) return PD_RANGE;
    unsigned n = (unsigned)(lba + 150);
    out->minute = (uint8_t)bcd(n / 4500u);
    out->second = (uint8_t)bcd(n / 75u % 60u);
    out->frame = (uint8_t)bcd(n % 75u);
    return PD_OK;
}

int PsxDisc_MsfToLba(const PsxMsf *p, int32_t *out)
{
    if (!p || !out) return PD_RANGE;
    int m = unbcd(p->minute), s = unbcd(p->second), f = unbcd(p->frame);
    if (m < 0 || s < 0 || s >= 60 || f < 0 || f >= 75) return PD_RANGE;
    *out = (m * 60 + s) * 75 + f - 150;
    return PD_OK;
}

uint32_t PsxDisc_Crc32(uint32_t previous, const void *data, uint32_t bytes)
{
    uint32_t crc = ~previous;
    const uint8_t *p = data;
    while (bytes--) {
        crc ^= *p++;
        for (unsigned i = 0; i < 8; ++i)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

static char *space(char *p)
{
    while (*p == ' ' || *p == '\t') ++p;
    return p;
}

static int number(char **p, unsigned max, unsigned *out)
{
    char *s = *p;
    if (*s < '0' || *s > '9') return 0;
    unsigned n = 0;
    do {
        n = n * 10 + (unsigned)(*s++ - '0');
        if (n > max) return 0;
    } while (*s >= '0' && *s <= '9');
    *p = s; *out = n;
    return 1;
}

static int zero_time(char *p)
{
    unsigned m, s, f;
    if (!number(&p, 99, &m) || *p++ != ':' || !number(&p, 59, &s) ||
        *p++ != ':' || !number(&p, 74, &f)) return 0;
    return !*space(p) && !m && !s && !f;
}

static int cue_parse(PsxDisc *d, const char *path)
{
    FILE *f = path ? fopen(path, "r") : NULL;
    if (!f) return PD_FORMAT;
    char line[512];
    unsigned files = 0, tracks = 0, indexes = 0, index00 = 0, gaps = 0;
    int result = PD_FORMAT;
    while (fgets(line, sizeof(line), f)) {
        size_t n = strlen(line);
        if (n == sizeof(line) - 1 && line[n - 1] != '\n') goto done;
        char *p = space(line);
        n = strlen(p);
        while (n && (p[n-1] == '\n' || p[n-1] == '\r' || p[n-1] == ' ' || p[n-1] == '\t')) p[--n] = 0;
        if (!*p || strncmp(p, "REM ", 4) == 0) continue;
        if (strncmp(p, "FILE \"", 6) == 0) {
            char *end = strchr(p + 6, '"');
            if (files || tracks || !end || end == p + 6 || strcmp(end + 1, " BINARY")) goto done;
            ++files;
        } else if (!strncmp(p, "TRACK", 5) && (p[5] == ' ' || p[5] == '\t')) {
            unsigned track;
            p = space(p + 5);
            if (!number(&p, 99, &track) || track != 1 || (*p != ' ' && *p != '\t') ||
                strcmp(space(p), "MODE2/2352") || files != 1 || tracks++) goto done;
        } else {
            unsigned idx;
            if (!strncmp(p, "INDEX", 5) && (p[5] == ' ' || p[5] == '\t')) {
                p = space(p + 5);
                if (!number(&p, 99, &idx) || (*p != ' ' && *p != '\t') ||
                    !zero_time(space(p)) || tracks != 1) goto done;
                if (idx == 0 && !indexes && !index00) ++index00;
                else if (idx == 1 && !indexes) ++indexes;
                else goto done;
            } else if (!strncmp(p, "PREGAP", 6) && (p[6] == ' ' || p[6] == '\t')) {
                if (!zero_time(space(p + 6)) || tracks != 1 || indexes || gaps++) goto done;
            } else goto done;
        }
    }
    if (!ferror(f) && files == 1 && tracks == 1 && indexes == 1) {
        d->track = (PsxTrackInfo){1, 1, 2, PSX_RAW_BYTES, 0, 0};
        d->cue_parsed = 1;
        result = PD_OK;
    }
done:
    if (fclose(f) != 0) result = PD_IO;
    return result;
}

int PsxDisc_Open(PsxDisc *d, const char *bin, const char *cue)
{ return PsxDisc_OpenBuffered(d,bin,cue,NULL,0); }

int PsxDisc_OpenBuffered(PsxDisc *d,const char *bin,const char *cue,void *buffer,uint32_t bytes)
{
    if (!d) return PD_RANGE;
    memset(d, 0, sizeof(*d));
    if (!bin || (!!buffer != !!bytes)) return PD_RANGE;
    d->file = fopen(bin, "rb");
    if (!d->file) return errno == ENOENT ? PD_NOT_FOUND : PD_IO;
    if(buffer && setvbuf(d->file,buffer,_IOFBF,bytes)) {
        PsxDisc_Close(d);return PD_IO;
    }
    int result = cue_parse(d, cue);
    if (result != PD_OK) goto fail;
    if (fseek(d->file, 0, SEEK_END)) { result = PD_IO; goto fail; }
    long size = ftell(d->file);
    if (size <= 0 || (uint64_t)size > INT32_MAX || (unsigned long)size % PSX_RAW_BYTES) {
        result = PD_FORMAT; goto fail;
    }
    d->image_bytes = (uint32_t)size;
    d->sectors = d->image_bytes / PSX_RAW_BYTES;
    result = PsxDisc_ReadRawSector(d, 0, d->scratch);
    if (result == PD_OK) return PD_OK;
fail:
    PsxDisc_Close(d);
    return result;
}

void PsxDisc_Close(PsxDisc *d)
{
    if (d) {
        if (d->file) fclose(d->file);
        d->file = NULL;
        d->sequential_position_valid=0;
        free(d->raw_cache);d->raw_cache=NULL;d->cache_bytes=d->cache_sectors=0;
        free(d->extra_cache);d->extra_cache=NULL;d->extra_bytes=d->extra_sectors=0;
    }
}

int PsxDisc_GetTrackInfo(const PsxDisc *d, PsxTrackInfo *out)
{
    if (!d || !d->file || !out) return PD_RANGE;
    *out = d->track;
    return PD_OK;
}

static int raw_valid(uint32_t lba,const uint8_t *s)
{
    static const uint8_t sync[12] = {0,255,255,255,255,255,255,255,255,255,255,0};
    PsxMsf msf;
    if(PsxDisc_LbaToMsf((int32_t)lba,&msf)!=PD_OK || memcmp(s,sync,12) ||
       s[12]!=msf.minute || s[13]!=msf.second || s[14]!=msf.frame || s[15]!=2 || memcmp(s+16,s+20,4))return PD_FORMAT;
    return PD_OK;
}
int PsxDisc_CacheRange(PsxDisc *d,uint32_t lba,uint32_t sectors)
{
    if(!d || !d->file || !sectors || lba>=d->sectors || sectors>d->sectors-lba ||
       sectors>(16u*1024*1024)/PSX_RAW_BYTES)return PD_RANGE;
    if(d->raw_cache && d->cache_lba==lba && d->cache_sectors==sectors)return PD_OK;
    free(d->raw_cache);d->raw_cache=NULL;d->cache_bytes=d->cache_sectors=0;
    free(d->extra_cache);d->extra_cache=NULL;d->extra_bytes=d->extra_sectors=0;
    uint8_t *data=malloc((size_t)sectors*PSX_RAW_BYTES);
    if(!data)return PD_IO;
    if(sectors*PSX_RAW_BYTES>d->cache_peak_bytes)d->cache_peak_bytes=sectors*PSX_RAW_BYTES;
#ifdef SH_3DS_GAME
    uint64_t start=game3ds_ticks();
#endif
    int status=PD_OK;d->preload_reads=0;d->preload_seeks=1;d->sequential_position_valid=0;
    if(fseek(d->file,(long)((uint64_t)lba*PSX_RAW_BYTES),SEEK_SET))status=PD_IO;
    for(uint32_t i=0;status==PD_OK && i<sectors;) {
        uint32_t n=sectors-i;if(n>32)n=32;
        size_t bytes=(size_t)n*PSX_RAW_BYTES;
        d->preload_reads++;
        if(fread(data+(size_t)i*PSX_RAW_BYTES,1,bytes,d->file)!=bytes){status=PD_IO;break;}
        for(unsigned j=0;j<n;j++)if((status=raw_valid(lba+i+j,data+(size_t)(i+j)*PSX_RAW_BYTES))!=PD_OK)break;
        i+=n;
    }
#ifdef SH_3DS_GAME
    d->preload_ticks=game3ds_ticks()-start;
#endif
    if(status!=PD_OK){free(data);return status;}
    d->raw_cache=data;d->cache_lba=lba;d->cache_sectors=sectors;d->cache_bytes=sectors*PSX_RAW_BYTES;
    return PD_OK;
}
int PsxDisc_CacheExtraRange(PsxDisc *d,uint32_t lba,uint32_t sectors)
{
    if(!d || !d->file || !d->raw_cache || !sectors || lba>=d->sectors || sectors>d->sectors-lba ||
       sectors>(16u*1024*1024-d->cache_bytes)/PSX_RAW_BYTES)return PD_RANGE;
    if(lba<d->cache_lba+d->cache_sectors && d->cache_lba<lba+sectors)return PD_RANGE;
    if(d->extra_cache && d->extra_lba==lba && d->extra_sectors==sectors)return PD_OK;
    free(d->extra_cache);d->extra_cache=NULL;d->extra_bytes=d->extra_sectors=0;
    /* Reuse the exact validated batch reader with a private descriptor view.
     * The FILE transport is shared; its physical position is invalidated below.
     * Neither view owns/frees the other view's data. No third range is kept. */
    PsxDisc view=*d;view.raw_cache=NULL;view.cache_bytes=view.cache_sectors=0;
    view.extra_cache=NULL;view.extra_bytes=view.extra_sectors=0;view.cache_peak_bytes=0;
    view.preload_reads=view.preload_seeks=0;view.preload_ticks=0;
    d->sequential_position_valid=0;
    int status=PsxDisc_CacheRange(&view,lba,sectors);
    d->preload_reads+=view.preload_reads;d->preload_seeks+=view.preload_seeks;d->preload_ticks+=view.preload_ticks;
    if(d->cache_bytes+view.cache_peak_bytes>d->cache_peak_bytes)d->cache_peak_bytes=d->cache_bytes+view.cache_peak_bytes;
    if(status!=PD_OK)return status;
    d->extra_cache=view.raw_cache;d->extra_lba=lba;d->extra_sectors=sectors;d->extra_bytes=view.cache_bytes;
    return PD_OK;
}
int PsxDisc_ReadRawSector(PsxDisc *d, uint32_t lba, void *out)
{
    if (!d || !d->file || !out || lba >= d->sectors) return PD_RANGE;
    if(d->raw_cache && lba>=d->cache_lba && lba-d->cache_lba<d->cache_sectors) {
        memmove(out,d->raw_cache+(size_t)(lba-d->cache_lba)*PSX_RAW_BYTES,PSX_RAW_BYTES);
        d->cache_hits++;return raw_valid(lba,out);
    }
    if(d->extra_cache && lba>=d->extra_lba && lba-d->extra_lba<d->extra_sectors) {
        memmove(out,d->extra_cache+(size_t)(lba-d->extra_lba)*PSX_RAW_BYTES,PSX_RAW_BYTES);
        d->cache_hits++;return raw_valid(lba,out);
    }
    d->cache_misses++;
#ifdef SH_3DS_GAME
    uint64_t profile=game_prof_begin(),io_start=game3ds_ticks();
#endif
    /* Keep stdio's read-ahead for adjacent sectors. Random access still seeks;
     * only this module owns the BIN stream position. Validate every sector. */
    unsigned seek=!d->sequential_position_valid || lba!=d->next_raw_lba;
    if(seek) {
#ifdef SH_3DS_GAME
        game_prof_count(GC_RAW_SEEKS,1);
#endif
        if(fseek(d->file,(long)((uint64_t)lba*PSX_RAW_BYTES),SEEK_SET)) {
            d->sequential_position_valid=0;return PD_IO;
        }
    }
    uint8_t *s = out;
    size_t read=fread(s, 1, PSX_RAW_BYTES, d->file);
#ifdef SH_3DS_GAME
    game_io_raw(lba,PSX_RAW_BYTES,read,seek,game3ds_ticks()-io_start);
    game_prof_end(GP_IO,profile);game_prof_count(GC_RAW_READS,1);game_prof_count(GC_RAW_BYTES,read);
#endif
    d->sequential_position_valid=read==PSX_RAW_BYTES;
    d->next_raw_lba=lba+1;
    if (read != PSX_RAW_BYTES) return PD_IO;
    return raw_valid(lba,s);
}

int PsxDisc_ReadDataSector(PsxDisc *d, uint32_t lba, void *out)
{
    if (!d || !out) return PD_RANGE;
    int result = PsxDisc_ReadRawSector(d, lba, d->scratch);
    if (result != PD_OK) return result;
    if (d->scratch[18] & 0x20) return PD_FORM2;
    memmove(out, d->scratch + 24, PSX_DATA_BYTES);
    return PD_OK;
}
