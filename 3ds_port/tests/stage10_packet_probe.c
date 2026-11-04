#include "game.h"
#include "game3ds.h"
#include "game_render_budget.h"
#include "bodyprog/bodyprog.h"
unsigned stage10_packet_test(unsigned which)
{
    g_GameWork.gameState=GameState_InGame;g_ActiveBufferIdx=0;
    unsigned char *base=Game3ds_PacketBegin(0);
    uintptr_t bounds;unsigned capacity;Game3ds_PacketBounds(&bounds,&capacity);
    if(bounds!=(uintptr_t)base || capacity!=GAME_PACKET_BYTES)game3ds_halt(460,"packet fixture bounds",0);
    if(which==1)Game3ds_PacketCheck(base+capacity-8,72);
    if(which==2) {base[capacity]=0;Game3ds_PacketValidate();}
    if(which==3) {
        OT_TAG ot={0};SPRT *sprite=(SPRT*)(base+131400-sizeof(SPRT));
        setSprt(sprite);setWH(sprite,12,16);addPrim(&ot,sprite);
        Game3ds_PacketValidate();return 131400;
    }
    if(which==4)Game3ds_PacketCheck(base+capacity-sizeof(POLY_GT4),sizeof(POLY_GT4));
    if(which==5) {Game3ds_PacketBegin(1);Game3ds_PacketCheck(base,sizeof(SPRT));}
    Game3ds_PacketValidate();return capacity;
}
