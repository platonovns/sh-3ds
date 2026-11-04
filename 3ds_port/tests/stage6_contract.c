#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/game_boot/game_boot.h"
#include "bodyprog/player.h"
#include "bodyprog/math/math.h"
#include "psx_memory.h"
#include "maps/shared.h"
#include "game3ds.h"

extern s_MapOverlayHdr map0_s01_g_MapOverlayHeader_map0_s01;
extern s_WorldObjectPose map0_s01_g_WorldObject_KitchenKnife;
extern s32 map0_s01_g_Particle_SpeedX;
void map0_s01_SysWork_StateStepIncrementAfterTime(q19_12*,q19_12,q19_12,q19_12,bool,bool);

_Static_assert(sizeof(s_WorldObjectModel)==28,"Original object RAM stride");
_Static_assert(sizeof(s_WorldObjectPose)==48,"Original pickup placement stride");
_Static_assert(sizeof(s_AnimInfo)==16,"Original ARM32 animation table ABI");

unsigned test_stage6_contract(void)
{
    unsigned failures=0;
    PsxMemory_Init();
    g_OvlDynamic=PSX_ADDR(0x800C9578);
    if((u8*)&map0_s01_g_WorldObject_KitchenKnife != g_PsxRam+0xE24A0 ||
       (u8*)&map0_s01_g_Particle_SpeedX != g_PsxRam+0xDE254)failures|=1;
    Game3ds_MapBind(1);
    if(g_pMapOverlayHeader!=&map0_s01_g_MapOverlayHeader_map0_s01 ||
       !g_MapOverlayHdr.playerStub_F8 || !g_MapOverlayHdr.charaCollisionReset ||
       g_MapOverlayHdr.func_68)failures|=2;
    Game3ds_MapBind(0);
    if(g_pMapOverlayHeader==&map0_s01_g_MapOverlayHeader_map0_s01)failures|=4;
    GameBoot_SavegameInitialize(1,0);
    func_80086470(3,InvItemId_Handgun,HANDGUN_AMMO_PICKUP_ITEM_COUNT,false);
    unsigned guns=0;
    for(unsigned i=0;i<INV_ITEM_COUNT_MAX;i++)if(g_SavegamePtr->items[i].id_0==InvItemId_Handgun){
        guns++;if(g_SavegamePtr->items[i].count_1!=HANDGUN_AMMO_PICKUP_ITEM_COUNT)failures|=8;
    }
    if(guns!=1 || g_SavegamePtr->inventorySlotCount<8 || g_SavegamePtr->mapIdx!=1)failures|=16;
    q19_12 timer=0;g_DeltaTime=4096;g_SysWork.sysStateSteps[0]=0;
    for(unsigned i=0;i<3;i++)map0_s01_SysWork_StateStepIncrementAfterTime(&timer,4096,0,8192,true,true);
    if(timer!=8192 || g_SysWork.sysStateSteps[0]!=1)failures|=32;
    return failures;
}
