/* Offline-only subsystem fixtures. Never linked into a hardware game. */
#include "game.h"
#include "game3ds.h"
#include "psx_memory.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/game_boot/game_boot.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/player.h"
#include "bodyprog/math/math.h"
#include "bodyprog/events/events_main.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "bodyprog/memcard.h"
#include "maps/shared.h"
#include "maps/characters/split_head.h"
#include "bodyprog/sys/joy.h"
#include <stddef.h>
#include <string.h>

extern void CatAnimInfos_Init(void),CreeperAnimInfos_Init(void),SplitHeadAnimInfos_Init(void),LockerDeadBodyAnimInfos_Init(void);
extern void map1_s05_SplitHead_Init(s_SubCharacter*);
extern void map1_s05_SplitHead_DamageTake(s_SubCharacter*);
extern void map1_s05_SplitHead_Control_6(s_SubCharacter*);
extern void map1_s01_MapEvent_PianoPuzzle(bool);
extern s32 map1_s01_g_PianoCursorX,map1_s01_g_PianoCursorY,map1_s01_g_PianoKeyCounter;
extern s8 map1_s01_g_PianoKeySequence[5];
extern s8 map1_s01_g_PianoKeys[11];

_Static_assert(sizeof(s_MapOverlayHdr_5C)==sizeof(s_MapHeader_field_5C),"Original effect descriptor size");
_Static_assert(offsetof(s_MapOverlayHdr_5C,field_20)==offsetof(s_MapHeader_field_5C,field_20),"Original effect descriptor position");
_Static_assert(offsetof(s_MapOverlayHdr_5C,field_16)==offsetof(s_MapHeader_field_5C,field_16),"Original effect descriptor divisor");
_Static_assert(sizeof(s_Savegame)==636,"Original save ABI");

unsigned school_probe_out[40];
const unsigned school_probe_meta[]={sizeof(s_Savegame),offsetof(s_Savegame,eventFlags),offsetof(s_Savegame,mapIdx),offsetof(s_Savegame,mapRoomIdx)};
static s_Savegame_Container saved;

void school_probe_reset(unsigned map)
{
    memset(&g_SysWork,0,sizeof(g_SysWork));
    Settings_RestoreDefaults();GameBoot_SavegameInitialize(map,GameDifficulty_Normal);
    g_OvlDynamic=PSX_ADDR(0xC9578); /* Normally initialized by retail main. */
    Game3ds_MapBind(map);
    memset(g_Controller0,0,sizeof(*g_Controller0));
    g_SysWork.playerWork.player.health=Q12(100.0f);
    g_DeltaTime=TIMESTEP_30_FPS;g_DeltaTimeRaw=g_DeltaTime;
    CatAnimInfos_Init();CreeperAnimInfos_Init();SplitHeadAnimInfos_Init();LockerDeadBodyAnimInfos_Init();
    memset(school_probe_out,0,sizeof(school_probe_out));
}

unsigned school_probe_header(void)
{
    unsigned count=0,uses=0,transitions=0;
    for(s_EventData* event=g_MapOverlayHdr.mapEvents;event->triggerType!=TriggerType_EndOfArray;event++) {
        if(++count>256)return 1;
        if(event->sysState==SysState_EventCallback && !g_MapOverlayHdr.mapEventFuncs[event->eventParam])return 2;
        uses+=event->activationType==TriggerActivationType_Item;
        transitions+=event->sysState==SysState_LoadOverlay;
    }
    school_probe_out[0]=count;school_probe_out[1]=uses;school_probe_out[2]=transitions;
    return 0;
}

unsigned school_probe_use(unsigned index)
{
    s_EventData* target=&g_MapOverlayHdr.mapEvents[index];
    if(target->activationType!=TriggerActivationType_Item)return 1;
    if(target->requiredEventFlag)Savegame_EventFlagSetAlt(target->requiredEventFlag);
    s_MapPoint2d* point=&g_MapOverlayHdr.mapPoints[target->pointOfInterestIdx];
    q3_12 yaw=target->triggerType==TriggerType_TouchObbFacing ? Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(point->triggerParam0)+2048):0;
    s_SubCharacter* p=&g_SysWork.playerWork.player;
    p->position.vx=point->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    p->position.vz=point->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));p->rotation.vy=yaw;
    Event_Update(true);
    unsigned slot;
    for(slot=0;slot<5 && g_ItemTriggerItemIds[slot]!=target->requiredItemId;slot++);
    school_probe_out[0]=slot;
    if(slot==5)return 2;
    g_SavegamePtr->items[0].id_0=target->requiredItemId;g_SavegamePtr->items[0].count_1=1;
    Inventory_ItemUse(0);
    if(g_SysWork.playerWork.extra.lastUsedItem!=target->requiredItemId)return 3;
    Event_Update(true);
    school_probe_out[1]=g_MapEventLastUsedItem;school_probe_out[2]=g_MapEventParam;
    school_probe_out[3]=g_MapEventData-g_MapOverlayHdr.mapEvents;
    if(g_MapEventSysState!=target->sysState || g_MapEventParam!=target->eventParam)return 4;
    if(g_SysWork.playerWork.extra.lastUsedItem!=InvItemId_Unequipped)return 5;
    return 0;
}

unsigned school_probe_save(unsigned map,unsigned boss)
{
    g_SavegamePtr->mapIdx=map;g_SavegamePtr->mapRoomIdx=3;
    Savegame_EventFlagSet(EventFlag_M1S01_PianoPuzzleSolved);
    Savegame_EventFlagSet(EventFlag_M1S02_UsedRubberBall);
    if(boss){Savegame_EventFlagSet(EventFlag_131);Savegame_EventFlagSet(EventFlag_132);Savegame_EventFlagSet(EventFlag_133);Savegame_EventFlagSet(EventFlag_134);}
    g_SavegamePtr->items[0].id_0=InvItemId_KGordonKey;g_SavegamePtr->items[0].count_1=1;
    MemCard_GameDataCopy(&saved,g_SavegamePtr);
    if(!MemCard_ChecksumValidate(&saved.footer,(s8*)&saved.savegame,sizeof(saved)))return 1;
    if(memcmp(&saved.savegame,g_SavegamePtr,sizeof(s_Savegame)))return 2;
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));
    memcpy(g_SavegamePtr,&saved.savegame,sizeof(s_Savegame));
    if(g_SavegamePtr->mapIdx!=map || !Savegame_EventFlagGet(EventFlag_M1S01_PianoPuzzleSolved) ||
       !Savegame_EventFlagGet(EventFlag_M1S02_UsedRubberBall) || g_SavegamePtr->items[0].id_0!=InvItemId_KGordonKey)return 3;
    if(boss && !Savegame_EventFlagGet(EventFlag_134))return 4;
    return 0;
}

unsigned school_probe_boss(unsigned hard,unsigned hits)
{
    s_SubCharacter* boss=&g_SysWork.npcs[0];
    memset(boss,0,sizeof(*boss));g_SavegamePtr->gameDifficulty=hard?GameDifficulty_Hard:GameDifficulty_Normal;
    map1_s05_SplitHead_Init(boss);
    school_probe_out[0]=boss->health;
    for(unsigned i=0;i<hits && boss->health;i++) {
        /* Ordinary small damage packets, with the original weak-mouth multiplier.
         * Hit registration/aiming is outside this focused damage-state fixture. */
        boss->properties.splitHead.flags|=SplitHeadFlag_0;
        boss->damage.amount=Q12(50.0f);
        map1_s05_SplitHead_DamageTake(boss);
    }
    school_probe_out[1]=boss->health;school_probe_out[2]=boss->model.controlState;
    if(!boss->health) {
        boss->model.anim.status=ANIM_STATUS(SplitHeadAnim_7,true);
        map1_s05_SplitHead_Control_6(boss);
    }
    school_probe_out[3]=Savegame_EventFlagGet(EventFlag_131)!=0;
    return 0;
}

unsigned school_probe_piano(unsigned key)
{
    if(key==99){map1_s01_MapEvent_PianoPuzzle(false);return 0;}
    if(key>=12)return 1;
    g_SysWork.sysStateSteps[1]=0;
    int x=key==0?map1_s01_g_PianoKeys[0]-5:key==11?map1_s01_g_PianoKeys[10]+5:
        (map1_s01_g_PianoKeys[key-1]+map1_s01_g_PianoKeys[key])/2;
    map1_s01_g_PianoCursorX=Q12(x);map1_s01_g_PianoCursorY=0;
    g_Controller0->clickedBtnFlags=g_GameWorkPtr->config.controllerConfig.enter;
    map1_s01_MapEvent_PianoPuzzle(true);
    school_probe_out[0]=map1_s01_g_PianoKeyCounter;
    return 0;
}
