/* Synthetic runtime state; the original save ABI and game state remain untouched. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/items.h"
#include "bodyprog/screen/cutscene_border.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include <string.h>

static uint16_t pixels[320*240];
void lower_hud_probe(int hp,int firearm,int current,int reserve,unsigned *result)
{
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));
    g_SysWork.playerWork.player.health=hp;
    g_Inventory_EquippedItem=firearm?InvItemId_Handgun:InvItemId_SteelPipe;
    g_SysWork.playerCombat.currentWeaponAmmo=current;
    g_SysWork.playerCombat.totalWeaponAmmo=reserve;
    memset(pixels,0xaa,sizeof(pixels));result[0]=Game3ds_LowerDraw(pixels);
    result[1]=result[2]=result[3]=result[4]=result[5]=0;
    for(unsigned i=0;i<320*240;i++) {
        uint16_t p=pixels[i];
        if(p==0xf800)result[1]++;if(p==0xfd20)result[2]++;
        if(p==0x07e0)result[3]++;if(p==0xffff)result[4]++;
        if(p && p!=0xf800 && p!=0xfd20 && p!=0x07e0 && p!=0xffff)result[5]++;
    }
}
void lower_map_setup(int owned)
{
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));
    g_SavegamePtr->paperMapIdx=PaperMapIdx_OldTown;g_SavegamePtr->mapIdx=MapIdx_MAP2_S00;
    g_SavegamePtr->paperMapFlags=owned?(1<<PaperMapIdx_OldTown):0;
    g_SysWork.playerWork.player.health=Q12(100.0f);
    g_SysWork.playerWork.player.position.vx=0;g_SysWork.playerWork.player.position.vz=0;
    g_SysWork.playerWork.player.rotation.vy=0;g_Inventory_EquippedItem=InvItemId_SteelPipe;
}
void lower_map_move(int x,int z,int angle)
{
    g_SysWork.playerWork.player.position.vx=x;
    g_SysWork.playerWork.player.position.vz=z;
    g_SysWork.playerWork.player.rotation.vy=angle;
}
void lower_test_firearm(void)
{
    g_Inventory_EquippedItem=InvItemId_Handgun;
    g_SysWork.playerCombat.currentWeaponAmmo=12;
    g_SysWork.playerCombat.totalWeaponAmmo=37;
}
uint16_t *lower_map_pixels(void){return pixels;}
void lower_map_area(int idx,int owned)
{
    g_SavegamePtr->paperMapIdx=idx;
    g_SavegamePtr->paperMapFlags=owned?(1u<<idx):0;
}

void lower_map_mark(void){Savegame_EventFlagSet(0x364);}
unsigned lower_owner_probe(unsigned state,unsigned sys,unsigned cutscene)
{
    g_GameWork.gameState=state;g_SysWork.sysState=sys;
    g_SysWork.sysFlags=cutscene?SysFlag_CutsceneActive:0;
    g_SysWork.cutsceneBorderState=CutsceneBorderState_None;
    return Game3ds_CanPause();
}
unsigned lower_pause_probe(unsigned state,unsigned sys,unsigned cutscene,unsigned border)
{
    g_GameWork.gameState=state;g_SysWork.sysState=sys;
    g_SysWork.sysFlags=cutscene?SysFlag_CutsceneActive:0;
    g_SysWork.cutsceneBorderState=border?CutsceneBorderState_Shown:CutsceneBorderState_None;
    return Game3ds_CanOpenPause();
}
unsigned lower_original_marker_probe(void)
{
    static OT_TAG tags[2048];static unsigned char packets[128];
    extern int g_PcMapQueryOnly;
    memset(tags,0,sizeof(tags));g_OrderingTable0[0].org=tags;
    g_ActiveBufferIdx=0;GsOUT_PACKET_P=(PACKET*)packets;
    g_Controller0->heldBtnFlags=0;g_PcMapQueryOnly=0;
    func_80067914(PaperMapIdx_OldTown,0,0,Q12(1.0f));
    return (unsigned)((unsigned char*)GsOUT_PACKET_P-packets);
}
unsigned lower_select_probe(int owned)
{
    lower_map_setup(owned);memset(&g_SysWork,0,sizeof(g_SysWork));
    g_GameWork.gameState=GameState_InGame;g_SysWork.sysState=SysState_MapScreen;
    g_SysWork.sysStateSteps[0]=1;g_Controller0->clickedBtnFlags=0;D_800A9A0C=1;
    SysState_MapScreen_Update();return g_GameWork.gameState;
}
