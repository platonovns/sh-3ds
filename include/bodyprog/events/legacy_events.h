#ifndef SH_LEGACY_EVENTS_H
#define SH_LEGACY_EVENTS_H
/* Exact declarations for retail functions whose public headers were renamed
 * before the map translation units were migrated. No state or event aliases. */
void SysWork_StateStepIncrementDelayed(q19_12 delay, bool reset);
void SysWork_StateStepIncrementAfterFade(s32 step, bool cond, s32 type, q19_12 speed, bool reset);
void func_80085EB8(u32 cmd, s_SubCharacter* chara, s32 arg, bool reset);
void func_80085DF0(void);
void func_800862F8(s32 step, e_FsFile file, bool reset);
void func_80086470(u32 step, e_InvItemId item, s32 count, bool reset);
void func_8003A16C(void);
void func_8008605C(e_EventFlag flag, s32 yes, s32 no, bool secondary);
void func_800865FC(bool absolute, s32 slot, s32 waypoint, q3_12 angle, q19_12 x, q19_12 z);
void func_800866D4(s32 anim, s32 count, bool reset);
void func_80086728(s_SubCharacter* chara, s32 anim, s32 count, bool reset);
void func_800867B4(s32 state,s32 paperMapFileIdx);
void func_80086C58(s_SubCharacter* chara,s32 arg1);
void func_80086E50(e_FsFile fileIdx,q19_12 fade0,q19_12 fade1);
void func_80086F44(q19_12 fade0,q19_12 fade1);
void MapMsg_DisplayWithTexture(e_FsFile fileIdx,q19_12 fade0,q19_12 fade1,s32 msg);
void MapMsg_DisplayWithTexture1(e_FsFile fileIdx,q19_12 fade0,q19_12 fade1,s32 msg0,s32 msg1);
void Event_MapTake(s32 mapFlagIdx,e_EventFlag eventFlagIdx,s32 mapMsgIdx);
void Map_MessageWithSfx(s32 mapMsgIdx,e_SfxId sfxId,VECTOR3* sfxPos);
void func_8008677C(s_SubCharacter* chara, s32 anim, s32 count);
void func_800868DC(s32 idx);
s32 func_800868F4(s32 target, s32 time, s32 idx);
void MapMsg_DisplayAndHandleSelection(bool selection, s32 msg, s32 a, s32 b, s32 c, bool secondary);
void Map_MessageWithAudio(s32 msg, u8* idx, const u16* commands);
void Camera_PositionSet(VECTOR3* pos, q19_12 x, q19_12 y, q19_12 z, q19_12 axz, q19_12 ay, q19_12 vxz, q19_12 vy, bool warp);
void Camera_LookAtSet(VECTOR3* pos, q19_12 x, q19_12 y, q19_12 z, q19_12 ax, q19_12 ay, q19_12 vx, q19_12 vy, bool warp);
void Map_PlaceIpdAtCell(s16 file, s32 x, s32 z);
void func_8005DC1C(e_SfxId id, const VECTOR3* pos, q23_8 volume, s32 type);
void func_8005DD44(e_SfxId id, VECTOR3* pos, q23_8 volume, s8 pitch);
void func_8005DE0C(e_SfxId id, VECTOR3* pos, s32 volume, q19_12 falloff, s8 pitch);
#endif
