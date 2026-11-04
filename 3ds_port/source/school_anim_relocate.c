/* Relocate PS1 animation callbacks after each school overlay read. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "main/fsqueue.h"
#include "game3ds.h"
#include <stdint.h>
#include <string.h>

bool __real_Fs_QueueUpdateRead(s_FsQueueEntry *entry);
bool __wrap_Fs_QueueUpdateRead(s_FsQueueEntry *entry)
{
    bool done = __real_Fs_QueueUpdateRead(entry);
    unsigned offsets[10], counts[10], tables = 0;
    if (!done || entry->data != (u8 *)g_OvlDynamic) return done;
    if (entry->info == &g_FileTable[FILE_VIN_MAP1_S00_BIN]) {
        offsets[0]=0xda6c8-0xc9578; counts[0]=38; offsets[1]=0xdb048-0xc9578; counts[1]=96; tables=2;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP1_S01_BIN]) {
        offsets[0]=0xda3d8-0xc9578; counts[0]=38; offsets[1]=0xdad58-0xc9578; counts[1]=96; tables=2;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP1_S02_BIN]) {
        offsets[0]=0xdf16c-0xc9578; counts[0]=96; tables=1;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP1_S03_BIN]) {
        offsets[0]=0xdf3ac-0xc9578; counts[0]=96; tables=1;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP6_S04_BIN]) {
        offsets[0]=0xe8b4c-0xc9578; counts[0]=96;
        offsets[1]=0xeab38-0xc9578; counts[1]=52; tables=2;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP7_S00_BIN]) {
        offsets[0]=0xd2ca8-0xc9578; counts[0]=36; tables=1;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP7_S01_BIN]) {
        offsets[0]=0xdfc78-0xc9578; counts[0]=18;
        offsets[1]=0xdfd98-0xc9578; counts[1]=36;
        offsets[2]=0xdffd8-0xc9578; counts[2]=4; tables=3;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP7_S02_BIN]) {
        offsets[0]=0xe5b3c-0xc9578; counts[0]=96;
        offsets[1]=0xe7708-0xc9578; counts[1]=36;
        offsets[2]=0xe7948-0xc9578; counts[2]=4;
        offsets[3]=0xe7988-0xc9578; counts[3]=30;
        offsets[4]=0xe7b68-0xc9578; counts[4]=52;
        offsets[5]=0xe7ea8-0xc9578; counts[5]=18;
        offsets[6]=0xe7fc8-0xc9578; counts[6]=46;
        offsets[7]=0xe82a8-0xc9578; counts[7]=4; tables=8;
    } else if (entry->info == &g_FileTable[FILE_VIN_MAP7_S03_BIN]) {
        offsets[0]=0xea1e0-0xc9578; counts[0]=64;
        offsets[1]=0xea5e0-0xc9578; counts[1]=52;
        offsets[2]=0xea920-0xc9578; counts[2]=22;
        offsets[3]=0xeaa80-0xc9578; counts[3]=24;
        offsets[4]=0xeac00-0xc9578; counts[4]=8;
        offsets[5]=0xeac80-0xc9578; counts[5]=46;
        offsets[6]=0xeaf60-0xc9578; counts[6]=4;
        offsets[7]=0xeafa8-0xc9578; counts[7]=6;
        offsets[8]=0xec808-0xc9578; counts[8]=12;
        offsets[9]=0xece50-0xc9578; counts[9]=12; tables=10;
    }
    size_t bytes=(size_t)entry->info->blockCount*FS_BLOCK_SIZE;
    for (unsigned t=0; t<tables; ++t) {
        if (offsets[t]+counts[t]*16u > bytes) game3ds_halt(452,"school animation size",(uint32_t)bytes);
        for (unsigned i=0; i<counts[t]; ++i) {
            uint32_t v; memcpy(&v,entry->data+offsets[t]+i*16u,4);
            if (v && v!=0x80044ca4u && v!=0x800449f0u && v!=0x80044b38u)
                game3ds_halt(452,"school animation callback",v);
        }
    }
    for (unsigned t=0; t<tables; ++t) for (unsigned i=0; i<counts[t]; ++i) {
        u8 *p=entry->data+offsets[t]+i*16u; uint32_t v; memcpy(&v,p,4);
        if (v==0x80044ca4u) v=(uint32_t)(uintptr_t)Anim_BlendLinear;
        else if (v==0x800449f0u) v=(uint32_t)(uintptr_t)Anim_PlaybackOnce;
        else if (v==0x80044b38u) v=(uint32_t)(uintptr_t)Anim_PlaybackLoop;
        memcpy(p,&v,4);
    }
    if (entry->info == &g_FileTable[FILE_VIN_MAP7_S03_BIN]) {
        void *dms[2] = { FS_BUFFER_20, FS_BUFFER_18 };
        memcpy(entry->data + (0xed230-0xc9578), dms, sizeof(dms));
    }
    return done;
}
