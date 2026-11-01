# sh-3ds
Native Silent Hill (1999) port on nintendo new 3ds (based on pc port)

<img width="1163" height="777" alt="image" src="https://github.com/user-attachments/assets/6b553caf-0f74-42ba-a27a-03092c6bed64" />



[!IMPORTANT]
Development status

This port was developed primarily with the help of OpenAI Codex. I directed the development, tested the game extensively on real New Nintendo 3DS hardware, reported issues, and iterated on the implementation with Codex.

At the moment, I have exhausted my available Codex usage limits and credits while preparing the first public release.

Because of this, the initial release currently contains only the ready-to-use 3DSX and CIA builds. The source tree still needs to be cleaned up and prepared for public release.

The source code will be published later.

This is not intended to be a binary-only project. The delay is simply because I want to publish the working build now rather than postpone the release while waiting for my Codex limits to reset.

**SH-3DS** is a native port of the original *Silent Hill* for the **New Nintendo 3DS**.

The project is based on the [`pc-port` branch of SlickAmogus/silent-hill-decomp](https://github.com/SlickAmogus/silent-hill-decomp) and uses **PsyCross** as part of the original porting foundation.

The goal of SH-3DS is to preserve the atmosphere, gameplay and overall feel of the original game while adapting it naturally to the Nintendo 3DS hardware.

This is **not PlayStation emulation**. The game code runs natively on the New Nintendo 3DS.

SH-3DS does not include any original Silent Hill game data.

---

## Features

### Native New Nintendo 3DS port

- Native New Nintendo 3DS executable
- Full **400×240 widescreen** rendering on the top screen
- Original FMVs and in-engine cutscenes
- XA dialogue and game audio
- Working save/load system
- Unlocked frame rate option

### Bottom-screen map

The original map can be displayed continuously on the bottom screen during gameplay.

It includes:

- Live player position and direction
- Original map markings and progression
- Adjustable brightness
- Optional color inversion
- Automatic screen management when the map is not needed

The original map screen is still available and the bottom-screen map does not replace the original game interface.

### 3DS controls

SH-3DS includes several control modes:

- **Classic** — controls close to the original PlayStation game
- **Modern** — movement adapted for the Circle Pad
- **Hybrid** — a compromise between the original controls and modern analog movement

The **C-Stick** can be used for camera control.

A quick reload shortcut is also available:

**ZR + Y** — reload the currently equipped firearm.

### Optional HUD

An optional gameplay HUD can display health and ammunition information without opening the Status screen.

For a more original Silent Hill experience, the HUD can be disabled completely.

### HP Notification LED

Harry's health can optionally be represented using the New Nintendo 3DS notification LED.

The LED gradually changes from green toward red as Harry's health decreases.

This allows health information to remain available while keeping the gameplay screen free of a permanent HUD.

---

# Controls

The normal game controls depend on the selected control mode.

SH-3DS also adds several 3DS-specific shortcuts.

### Map controls

Hold **SELECT** and use the D-Pad:

- **SELECT + D-Pad Up / Down** — adjust bottom-screen map brightness
- **SELECT + D-Pad Left / Right** — change the map display/inversion setting

These controls allow the bottom-screen map to be adjusted without entering the options menu.

### Reload

**ZR + Y** — quick reload

This uses the normal game reload behavior and works with supported firearms.

---

# Settings

SH-3DS includes additional options specifically for the 3DS port.

The included defaults are intended to provide a safe starting point. **You should review the settings and adjust them to your preference before playing.**

## Frame Limit / FPS

Controls the game's frame-rate limit.

The original game targeted approximately 30 FPS, while SH-3DS can run at higher frame rates in many areas on New Nintendo 3DS hardware.

**Unlocked** allows the game to run as fast as the hardware can maintain.

Performance varies depending on the location and scene complexity.

## Controls

Selects the movement/control style.

**Classic**  
Preserves controls close to the original PlayStation release.

**Modern**  
Provides more direct analog movement intended for the 3DS Circle Pad.

**Hybrid**  
Combines aspects of the original controls with more comfortable analog movement.

Hybrid is the recommended mode if you want to preserve much of the original feel while taking advantage of the 3DS controls.

## Map

Enables or disables the persistent bottom-screen map.

When enabled, the current map is displayed on the lower screen whenever appropriate.

## HUD

Enables or disables the additional gameplay HUD.

The HUD provides information such as health and ammunition without requiring the Status screen.

For an experience closer to the original game, leave this disabled.

## HP LED

Enables health indication using the New Nintendo 3DS notification LED.

The LED changes according to Harry's current health.

This is useful when playing with the additional HUD disabled.

## Lower Screen Auto

Automatically manages the bottom screen depending on the current game state.

When enabled, the lower-screen backlight can be turned off when the screen has nothing useful to display, such as during FMVs and other appropriate scenes.

It is automatically restored when needed.

## Map Invert

Changes the color presentation of the bottom-screen map.

This can also be controlled during gameplay using the **SELECT + D-Pad** shortcuts.

## Map Brightness

Controls the brightness of the bottom-screen map.

This can also be adjusted during gameplay using **SELECT + D-Pad Up / Down**.

---

# Recommended setup

There is no required configuration, and the settings are intended to be adjusted to personal preference.

For a playthrough that stays close to the original presentation while using the most useful 3DS-specific features, I recommend:

- **Controls:** Hybrid
- **Map:** On
- **HUD:** Off
- **HP LED:** On
- **Lower Screen Auto:** On
- **Map Invert:** Off
- **Map Brightness:** 100%
- **Frame Limit:** Unlocked

This keeps the main gameplay screen relatively close to the original game while using the second screen and 3DS hardware for additional information and quality-of-life features.

---

# Game data

SH-3DS does **not** include any original *Silent Hill* game data.

You must provide the required game image from your own legally obtained copy of *Silent Hill*.

Currently, SH-3DS supports:

**Silent Hill — NTSC-U (USA), SLUS-00707 v1.1**

Place your game image on the SD card as:

```text
sdmc:/3ds/silenthill/sh1.bin
sdmc:/3ds/silenthill/sh1.cue
```

The filenames must be exactly:

```text
sh1.bin
sh1.cue
```

Do not rename a different version of the game and expect it to work. The port currently expects the supported **SLUS-00707 v1.1** game data.

---

# Installation

SH-3DS is available as both a **CIA** build and a **3DSX** build.

## CIA

Install the CIA using your preferred Nintendo 3DS title installer.

The game will then appear directly on the HOME Menu.

You still need to provide the required `sh1.bin` and `sh1.cue` files on the SD card.

## 3DSX

Place the 3DSX build in the appropriate location on your SD card and launch it through the Homebrew Launcher.

The same external game data is required.

---

# Compatibility

SH-3DS is designed for the **New Nintendo 3DS family**.

The game has been played from beginning to end on a real New Nintendo 3DS.

My complete hardware playthrough used the **Good+ ending**.

Other endings have not yet been personally tested.

Because this is the first public release, there may still be bugs, unusual save-state interactions or hardware-specific issues that were not encountered during development and testing.

If you encounter a problem, please open an issue and include:

- Where in the game it happened
- What you were doing immediately before the problem
- Whether the problem is reproducible
- Which build you are using
- Any other information that may help reproduce it

---

# Project background

SH-3DS is based on the work of the **Silent Hill decompilation / PC port project by SlickAmogus**.

The 3DS port builds on that work and adds the platform-specific rendering, input, audio, dual-screen integration and other changes necessary to run the game natively on New Nintendo 3DS hardware.

This project would not exist without the work done by the original decompilation and PC-port contributors.

---

# Philosophy

SH-3DS is not intended to redesign or modernize Silent Hill.

The objective is to keep the original game's atmosphere and identity intact while adding features that make sense on the Nintendo 3DS:

- The second screen is used for the map rather than replacing the original interface.
- Modern and Hybrid controls are optional.
- The additional HUD is optional.
- HP information can be moved away from the gameplay screen using the system LED.
- The original controls and interfaces remain available.

The intention is simple: **Silent Hill should still feel like Silent Hill.**
