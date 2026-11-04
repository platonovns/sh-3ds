"""Exercise the production HP observer across gameplay and Status healing."""
from pathlib import Path
import subprocess
import tempfile

port=Path(__file__).resolve().parents[1]
source=(port/'source/game_native.c').read_text()
start=source.index('    static int hp_death_latched',source.index('void Game3ds_Observe(void)'))
end=source.index('\n    if(game_prof_enabled)',start)
body=source[start:end]
driver=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include "game_lower_policy.h"
enum {GameState_InGame=11,GameState_InventoryScreen=14,GameState_MainLoadScreen=10,
      GameState_MainMenu=7,GameState_MovieOpening=9,SysState_Gameplay=0,SysState_Fmv=4,
      SysState_LoadRoom=6,SysState_GameOver=13,PlayerState_Death=8,PlayerState_InstantDeath=9,
      SysFlag_CutsceneActive=1,SysFlag_DemoActive=2,Chara_Harry=1,
      MapIdx_MAP0_S00=0,MapIdx_MAP0_S01=1,EventFlag_M0S01_FmvStarted=39,EventFlag_M0S01_CafeCutsceneStarted=40};
static struct {int gameState;} g_GameWork;
static struct {int sysState,sysFlags;struct {struct {struct {int charaId;} model;
    int32_t health;} player;struct {int state;} extra;} playerWork;} g_SysWork;
static struct {void *registeredCharaModels[2];} g_WorldGfxWork;
static struct {int mapIdx;} savegame,*g_SavegamePtr=&savegame;
static int event_flags[64];
static int Savegame_EventFlagGet(int flag){return event_flags[flag];}
static int g_Player_DisableControl,g_Player_IsDead,can_pause=1;
static int Game3ds_CanPause(void){return can_pause;}
static uint32_t validity;static int32_t value;
static void game3ds_hp_observe(uint32_t valid,int32_t health){validity=valid;value=health;}
static void observe(void) {
''' + body + r'''
}
int main(void) {
    g_GameWork.gameState=GameState_InGame;g_SysWork.sysState=SysState_Gameplay;
    g_SysWork.playerWork.player.model.charaId=Chara_Harry;
    g_WorldGfxWork.registeredCharaModels[Chara_Harry]=&g_GameWork;
    g_SysWork.playerWork.player.health=10*4096;observe();assert(validity==1 && value==10*4096);
    g_GameWork.gameState=GameState_InventoryScreen;observe();assert(validity==2);
    g_GameWork.gameState=GameState_InGame;g_SysWork.playerWork.player.health=0;
    observe();assert(validity==0);
    g_SysWork.playerWork.extra.state=PlayerState_Death;
    g_SysWork.playerWork.player.health=100*4096;observe();assert(validity==0);
    g_SysWork.playerWork.extra.state=0;observe();assert(validity==0);
    g_SysWork.sysState=SysState_LoadRoom;observe();assert(validity==0);
    g_SysWork.sysState=SysState_Gameplay;observe();assert(validity==0);
    g_GameWork.gameState=GameState_MainLoadScreen;observe();assert(validity==0);
    g_GameWork.gameState=GameState_InGame;g_SavegamePtr->mapIdx=1;observe();assert(validity==0);
    g_SysWork.sysState=SysState_Fmv;observe();assert(validity==0);
    g_SysWork.sysState=SysState_Gameplay;g_Player_DisableControl=1;observe();assert(validity==0);
    g_Player_DisableControl=0;observe();assert(validity==0);
    event_flags[EventFlag_M0S01_FmvStarted]=1;observe();assert(validity==0);
    event_flags[EventFlag_M0S01_CafeCutsceneStarted]=1;observe();assert(validity==1);
    g_SysWork.playerWork.extra.state=PlayerState_InstantDeath;observe();assert(validity==0);
    g_SysWork.sysState=SysState_GameOver;observe();assert(validity==0);
    g_GameWork.gameState=GameState_MainMenu;observe();assert(validity==0);
    g_GameWork.gameState=GameState_MainLoadScreen;observe();assert(validity==0);
    g_GameWork.gameState=GameState_InGame;g_SysWork.sysState=SysState_Gameplay;
    g_SysWork.playerWork.extra.state=0;observe();assert(validity==1);
    g_GameWork.gameState=GameState_InventoryScreen;observe();assert(validity==2);
    observe();assert(validity==2);
    g_SysWork.playerWork.player.health=90*4096;observe();assert(validity==1 && value==90*4096);
    observe();assert(validity==2);
    g_SysWork.playerWork.player.health=100*4096;observe();assert(validity==1 && value==100*4096);
    g_SysWork.sysFlags=SysFlag_CutsceneActive;g_SysWork.playerWork.player.health=80*4096;
    observe();assert(validity==0);
    g_SysWork.sysFlags=0;g_GameWork.gameState=GameState_InGame;observe();assert(validity==1);
    g_GameWork.gameState=GameState_InventoryScreen;observe();assert(validity==2);
    puts("PASS: status heals update HP LED, unchanged health holds; gameplay and cutscene remain gated");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-status-hp-') as name:
    root=Path(name);(root/'test.c').write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(port/'include'),
                    str(root/'test.c'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
