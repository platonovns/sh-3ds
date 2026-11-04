#ifndef SH_GAME_LOWER_POLICY_H
#define SH_GAME_LOWER_POLICY_H
enum LowerOwner {LOWER_SPECIAL, LOWER_START, LOWER_GAME_DRAW, LOWER_GAME_HOLD};
static inline int hp_led_hold_policy(unsigned game,unsigned sys,unsigned cutscene,unsigned demo)
{
    if(cutscene || demo)return 0;
    if(game==10 || game==12 || game==14 || game==15 || game==19 || game==20)return 1;
    return game==11 && (sys==0 || sys==2 || sys==3 || sys==5 || sys==6 || sys==7 || sys==10 || sys==11 || sys==12);
}
/* -1 retains the previous state while a room or game state is transitioning. */
static inline int lower_backlight_policy(unsigned automatic,unsigned game,unsigned sys,unsigned cutscene,unsigned disabled,unsigned has_map)
{
    if(!automatic)return 1;
    if(game==6 || game==7 || game==9 || game==13 || (game==11 && sys==4))return 0;
    if(game==14 || game==19 || (game==11 && (sys==1 || sys==2 || sys==3 || sys==8 || sys==9)))return 1;
    if(cutscene)return 0;
    (void)disabled; /* A temporary loss of control is not a cutscene. */
    if(game==12 || (game==11 && (sys==0 || sys==7 || sys==10 || sys==11 || sys==12 || sys==14)))return has_map?1:0;
    if(game==14 || game==15 || game==16 || game==18 || game==19 || game==20)return 1;
    return -1;
}
static inline int lower_backlight_content_policy(unsigned automatic,unsigned game,unsigned sys,unsigned cutscene,
    unsigned disabled,unsigned has_map,unsigned map_enabled,unsigned hud_enabled)
{
    if(game==11 && sys==0 && !cutscene && !map_enabled)
        return hud_enabled?1:0;
    return lower_backlight_policy(automatic,game,sys,cutscene,disabled,has_map);
}
/* game/sys are original e_GameState/e_SysState values. Fullscreen owners and
 * video must win; transient in-game states retain the last complete image. */
static inline enum LowerOwner lower_owner(unsigned game,unsigned sys,unsigned display,unsigned start,unsigned cutscene)
{
    if(start)return LOWER_START;
    if(display==1 || game==8 || game==9 || game==13 || (game>=14 && game<=20))return LOWER_SPECIAL;
    if(game==10 || game==12)return LOWER_GAME_HOLD;
    if(game!=11)return LOWER_SPECIAL;
    switch(sys) {
    case 0:return cutscene?LOWER_GAME_HOLD:LOWER_GAME_DRAW;
    case 5: case 6: case 7: case 10: case 11: case 12: case 14:return LOWER_GAME_HOLD;
    default:return LOWER_SPECIAL;
    }
}
#endif
