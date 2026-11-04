/* Accepted callers still use the original address names. */
#include "game.h"
#include "bodyprog/sound/sfx.h"
int g_Pc_SfxAzimuthValid;
void func_8005DC1C(e_SfxId id,const VECTOR3 *pos,q23_8 vol,s32 flags)
{ Sfx_WithFlagsPlay(id,pos,vol,flags); }
void func_8005DC3C(e_SfxId id,const VECTOR3 *pos,q23_8 vol,s32 flags,s32 pitch)
{ Sfx_WithFlagsAndPitchPlay(id,pos,vol,flags,pitch); }
void func_8005DD44(e_SfxId id,VECTOR3 *pos,q23_8 vol,s8 pitch)
{ Sfx_WithPitchPlay(id,pos,vol,pitch); }
void func_8005DE0C(e_SfxId id,VECTOR3 *pos,s32 vol,q19_12 falloff,s8 pitch)
{ Sfx_WithFalloffAndPitchPlay(id,pos,vol,falloff,pitch); }
