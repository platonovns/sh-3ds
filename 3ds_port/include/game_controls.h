#ifndef SH_GAME_CONTROLS_H
#define SH_GAME_CONTROLS_H
#include <stdint.h>
#include "game_modern_controls.h"
void Game3ds_InputSample(uint32_t keys,int cx,int cy,int rx,int ry);
void Game3ds_MovementInput(void);
void Game3ds_MovementApply(void);
void Game3ds_CameraLook(void *matrix);
void Game3ds_ControlsReset(void);
void Game3ds_TankActions(void);
#endif
