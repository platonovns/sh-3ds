/* Resident ARM overlay dispatch, selected only by original GameBoot_MapLoad. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "psx_memory.h"
#include "bodyprog/view/structs.h"
#include "maps/shared.h"
#include "maps/particle.h"
_Static_assert(sizeof(VC_WORK)==744,"Retained PSX camera workspace ABI");
_Static_assert(sizeof(s_Particle)==32,"Retained PSX particle data ABI");
_Static_assert(sizeof(s_ParticleVectors)==44,"Retained PSX particle vector ABI");
_Static_assert(sizeof(MATRIX)==32,"Retained PSX matrix ABI");
_Static_assert(sizeof(GsCOORDINATE2)==80,"Retained PSX coordinate ABI");

extern s_MapOverlayHdr g_MapOverlayHeader_map0_s00;
extern s_MapOverlayHdr map0_s01_g_MapOverlayHeader_map0_s01;
extern s_MapOverlayHdr map2_s00_g_MapOverlayHeader_map2_s00;
extern s_MapOverlayHdr map0_s02_g_MapOverlayHeader_map0_s02;
extern s_MapOverlayHdr map1_s00_g_MapOverlayHeader_map1_s00;
extern s_MapOverlayHdr map1_s01_g_MapOverlayHeader_map1_s01;
extern s_MapOverlayHdr map1_s02_g_MapOverlayHeader_map1_s02;
extern s_MapOverlayHdr map1_s03_g_MapOverlayHeader_map1_s03;
extern s_MapOverlayHdr map1_s04_g_MapOverlayHeader_map1_s04;
extern s_MapOverlayHdr map1_s05_g_MapOverlayHeader_map1_s05;
extern s_MapOverlayHdr map1_s06_g_MapOverlayHeader_map1_s06;
extern s_MapOverlayHdr map2_s01_g_MapOverlayHeader_map2_s01;
extern s_MapOverlayHdr map2_s02_g_MapOverlayHeader_map2_s02;
extern s_MapOverlayHdr map2_s04_g_MapOverlayHeader_map2_s04;
extern s_MapOverlayHdr map3_s00_g_MapOverlayHeader_map3_s00;
extern s_MapOverlayHdr map3_s01_g_MapOverlayHeader_map3_s01;
extern s_MapOverlayHdr map3_s02_g_MapOverlayHeader_map3_s02;
extern s_MapOverlayHdr map3_s03_g_MapOverlayHeader_map3_s03;
extern s_MapOverlayHdr map3_s04_g_MapOverlayHeader_map3_s04;
extern s_MapOverlayHdr map3_s05_g_MapOverlayHeader_map3_s05;
extern s_MapOverlayHdr map3_s06_g_MapOverlayHeader_map3_s06;
extern s_MapOverlayHdr map4_s01_g_MapOverlayHeader_map4_s01;
extern s_MapOverlayHdr map4_s02_g_MapOverlayHeader_map4_s02;
extern s_MapOverlayHdr map4_s03_g_MapOverlayHeader_map4_s03;
extern s_MapOverlayHdr map4_s04_g_MapOverlayHeader_map4_s04;
extern s_MapOverlayHdr map4_s05_g_MapOverlayHeader_map4_s05;
extern s_MapOverlayHdr map5_s00_g_MapOverlayHeader_map5_s00;
extern s_MapOverlayHdr map5_s01_g_MapOverlayHeader_map5_s01;
extern s_MapOverlayHdr map5_s02_g_MapOverlayHeader_map5_s02;
extern s_MapOverlayHdr map5_s03_g_MapOverlayHeader_map5_s03;
extern s_MapOverlayHdr map6_s00_g_MapOverlayHeader_map6_s00;
extern s_MapOverlayHdr map6_s01_g_MapOverlayHeader_map6_s01;
extern s_MapOverlayHdr map6_s02_g_MapOverlayHeader_map6_s02;
extern s_MapOverlayHdr map6_s03_g_MapOverlayHeader_map6_s03;
extern s_MapOverlayHdr map6_s04_g_MapOverlayHeader_map6_s04;
extern s_MapOverlayHdr map7_s00_g_MapOverlayHeader_map7_s00;
extern s_MapOverlayHdr map7_s01_g_MapOverlayHeader_map7_s01;
extern s_MapOverlayHdr map7_s02_g_MapOverlayHeader_map7_s02;
extern s_MapOverlayHdr map7_s03_g_MapOverlayHeader_map7_s03;
void MonsterCybilAnimInfos_Init(void);
void ParasiteAnimInfos_Init(void);
void FlaurosAnimInfos_Init(void);
void LarvalStalkerAnimInfos_Init(void);
void StalkerM5S02AnimInfos_Init(void);
void ResortAnimInfos_Init(void);
void GroanerM5S01AnimInfos_Init(void);
void HangedScratcherAnimInfos_Init(void);
void CreeperAnimInfos_Init(void);
s_MapOverlayHdr *g_pMapOverlayHeader;

void Game3ds_MapBind(uint32_t map)
{
    if (g_OvlDynamic != PSX_ADDR(0x800C9578))
        game3ds_halt(452, "overlay data destination", (uintptr_t)g_OvlDynamic);
    switch(map) {
        case MapIdx_MAP0_S00:g_pMapOverlayHeader=&g_MapOverlayHeader_map0_s00;break;
        case MapIdx_MAP0_S01:g_pMapOverlayHeader=&map0_s01_g_MapOverlayHeader_map0_s01;break;
        case MapIdx_MAP2_S00:g_pMapOverlayHeader=&map2_s00_g_MapOverlayHeader_map2_s00;break;
        case MapIdx_MAP0_S02:g_pMapOverlayHeader=&map0_s02_g_MapOverlayHeader_map0_s02;break;
        case MapIdx_MAP1_S00:g_pMapOverlayHeader=&map1_s00_g_MapOverlayHeader_map1_s00;break;
        case MapIdx_MAP1_S01:g_pMapOverlayHeader=&map1_s01_g_MapOverlayHeader_map1_s01;break;
        case MapIdx_MAP1_S02:g_pMapOverlayHeader=&map1_s02_g_MapOverlayHeader_map1_s02;break;
        case MapIdx_MAP1_S03:g_pMapOverlayHeader=&map1_s03_g_MapOverlayHeader_map1_s03;break;
        case MapIdx_MAP1_S04:g_pMapOverlayHeader=&map1_s04_g_MapOverlayHeader_map1_s04;break;
        case MapIdx_MAP1_S05:g_pMapOverlayHeader=&map1_s05_g_MapOverlayHeader_map1_s05;break;
        case MapIdx_MAP1_S06:g_pMapOverlayHeader=&map1_s06_g_MapOverlayHeader_map1_s06;break;
        case MapIdx_MAP2_S01:g_pMapOverlayHeader=&map2_s01_g_MapOverlayHeader_map2_s01;break;
        case MapIdx_MAP2_S02:g_pMapOverlayHeader=&map2_s02_g_MapOverlayHeader_map2_s02;break;
        case MapIdx_MAP2_S04:g_pMapOverlayHeader=&map2_s04_g_MapOverlayHeader_map2_s04;break;
        case MapIdx_MAP3_S00:g_pMapOverlayHeader=&map3_s00_g_MapOverlayHeader_map3_s00;break;
        case MapIdx_MAP3_S01:g_pMapOverlayHeader=&map3_s01_g_MapOverlayHeader_map3_s01;break;
        case MapIdx_MAP3_S02:g_pMapOverlayHeader=&map3_s02_g_MapOverlayHeader_map3_s02;break;
        case MapIdx_MAP3_S03:g_pMapOverlayHeader=&map3_s03_g_MapOverlayHeader_map3_s03;break;
        case MapIdx_MAP3_S04:g_pMapOverlayHeader=&map3_s04_g_MapOverlayHeader_map3_s04;break;
        case MapIdx_MAP3_S05:g_pMapOverlayHeader=&map3_s05_g_MapOverlayHeader_map3_s05;break;
        case MapIdx_MAP3_S06:g_pMapOverlayHeader=&map3_s06_g_MapOverlayHeader_map3_s06;break;
        case MapIdx_MAP4_S01:g_pMapOverlayHeader=&map4_s01_g_MapOverlayHeader_map4_s01;break;
        case MapIdx_MAP4_S02:g_pMapOverlayHeader=&map4_s02_g_MapOverlayHeader_map4_s02;break;
        case MapIdx_MAP4_S03:g_pMapOverlayHeader=&map4_s03_g_MapOverlayHeader_map4_s03;break;
        case MapIdx_MAP4_S04:g_pMapOverlayHeader=&map4_s04_g_MapOverlayHeader_map4_s04;break;
        case MapIdx_MAP4_S05:g_pMapOverlayHeader=&map4_s05_g_MapOverlayHeader_map4_s05;break;
        case MapIdx_MAP5_S00:CreeperAnimInfos_Init();HangedScratcherAnimInfos_Init();g_pMapOverlayHeader=&map5_s00_g_MapOverlayHeader_map5_s00;break;
        case MapIdx_MAP5_S01:GroanerM5S01AnimInfos_Init();g_pMapOverlayHeader=&map5_s01_g_MapOverlayHeader_map5_s01;break;
        case MapIdx_MAP5_S02:ResortAnimInfos_Init();StalkerM5S02AnimInfos_Init();g_pMapOverlayHeader=&map5_s02_g_MapOverlayHeader_map5_s02;break;
        case MapIdx_MAP5_S03:g_pMapOverlayHeader=&map5_s03_g_MapOverlayHeader_map5_s03;break;
        case MapIdx_MAP6_S00:ResortAnimInfos_Init();g_pMapOverlayHeader=&map6_s00_g_MapOverlayHeader_map6_s00;break;
        case MapIdx_MAP6_S01:ResortAnimInfos_Init();g_pMapOverlayHeader=&map6_s01_g_MapOverlayHeader_map6_s01;break;
        case MapIdx_MAP6_S02:g_pMapOverlayHeader=&map6_s02_g_MapOverlayHeader_map6_s02;break;
        case MapIdx_MAP6_S03:HangedScratcherAnimInfos_Init();StalkerM5S02AnimInfos_Init();g_pMapOverlayHeader=&map6_s03_g_MapOverlayHeader_map6_s03;break;
        case MapIdx_MAP6_S04:MonsterCybilAnimInfos_Init();ParasiteAnimInfos_Init();FlaurosAnimInfos_Init();LarvalStalkerAnimInfos_Init();g_pMapOverlayHeader=&map6_s04_g_MapOverlayHeader_map6_s04;break;
        case MapIdx_MAP7_S00:g_pMapOverlayHeader=&map7_s00_g_MapOverlayHeader_map7_s00;break;
        case MapIdx_MAP7_S01:g_pMapOverlayHeader=&map7_s01_g_MapOverlayHeader_map7_s01;break;
        case MapIdx_MAP7_S02:g_pMapOverlayHeader=&map7_s02_g_MapOverlayHeader_map7_s02;break;
        case MapIdx_MAP7_S03:g_pMapOverlayHeader=&map7_s03_g_MapOverlayHeader_map7_s03;break;
        default:game3ds_halt(452,"resident map unavailable",map);
    }
    stage4_fs_game_preload(g_pMapOverlayHeader->mapInfo->tag);
    Game3ds_Progress("MAP_OVERLAY_BOUND", map);
}

