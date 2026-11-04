# SH-3DS

<img width="1163" height="777" alt="image" src="https://github.com/user-attachments/assets/f78eabb4-2197-4022-a9b8-c39e0a15398f" />

https://www.youtube.com/watch?v=DMqVBZ0_AkQ

SH-3DS is a native port of the original **Silent Hill** for the New Nintendo
3DS family. It runs the ported game code on the console; it is not PlayStation
emulation. The aim is to preserve the original experience while offering
optional 3DS-specific quality-of-life features.

The game has been completed from beginning to end on real New Nintendo 3DS
hardware with the Good+ ending. Other endings have not yet been personally
tested. Old Nintendo 3DS systems are not a supported target.

Features include 400 × 240 widescreen rendering, a lower-screen map with the
player's position, Tank, Modern and Hybrid control modes, C-Stick camera look,
an optional HUD and HP notification LED, automatic lower-screen management,
map brightness and inversion, quick reload, original FMV and in-engine cutscenes,
XA dialogue/audio, and save/load support. Gameplay pacing can be set to 30 or
60 FPS; the current 60 FPS option is synchronized to the display, not an
unlimited frame-rate mode.

## Game image and installation

The supported and tested game version is **Silent Hill — NTSC-U (USA),
SLUS-00707 v1.1**. Provide a game image from your own legally obtained copy.
Place the raw single-track MODE2/2352 image and its CUE on the SD card at:

```text
sdmc:/3ds/silenthill/sh1.bin
sdmc:/3ds/silenthill/sh1.cue
```

Place the built `.3dsx` in the SD card's `3ds` directory and run it through
the Homebrew Launcher, or install a separately packaged CIA. The image is a
runtime requirement; it is not supplied here. Virtual card 1 is saved as
`sdmc:/3ds/silenthill/memcard.mcr`; cards 2–8 use `memcard2.mcr` through
`memcard8.mcr` in the same directory.

## Controls and settings

Press START to open the lower-screen pause menu. The D-pad selects and changes
items; B confirms an action, and A or START resumes. Settings are saved to
`sdmc:/3ds/silenthill/native_settings.cfg`, with a backup alongside it. Existing
saved preferences can override the compiled defaults.

| Menu entry | Available values and purpose |
| --- | --- |
| Gameplay | 30 or 60 FPS gameplay pacing. Menus retain their own cadence. |
| Controls | Tank (classic), Modern, or Hybrid. Hybrid uses the Circle Pad for modern movement and the D-pad for tank movement. |
| Counter | Off, FPS, Frame time, or FPS + Frame time. |
| Text | White, Black, White + outline, or Black 70%. |
| Map bright | 10–100%, in 10% steps. |
| Memory Card | Select one of eight virtual cards. |
| HP indicator | OFF, LED, or SQUARE on the lower display. The square is drawn only when the HUD is enabled. |
| HUD | CURRENT ammunition, CURRENT + RESERVE ammunition, or OFF. |
| Map | ON or OFF. |
| Lower auto | Automatically manage the lower-screen backlight. |
| Map invert | Toggle map inversion. |

The menu also provides Resume, Exit to Title, Quit application and Diagnostics.
During eligible gameplay, hold SELECT and press **Up/Down** to raise/lower map
brightness, **Left** to toggle the map, or **Right** to toggle inversion. A
plain SELECT opens the original map. The C-Stick looks around while free
movement and camera control are available; it does not replace authored camera
behavior during cutscenes or other restricted states. Press **ZR + Y** for
quick reload when the equipped firearm and player state allow it.

The included settings are a starting point; adjust them to taste. A suggested
configuration is Hybrid, Map ON, HUD OFF, HP indicator LED, Lower auto ON,
Map invert OFF, Map bright 100%, and Gameplay 60 FPS. The current source's
fresh default for map brightness is 40%, so change it if you prefer 100%.

## Building from source

The 3DS build uses devkitPro's devkitARM, libctru and citro3d, plus GNU make,
Python 3, `patch`, `picasso`, `3dsxtool`, and the tools provided by devkitPro's
3DS development environment. The release build used Linux/WSL, devkitARM GCC
16.1.0, citro3d 1.7.1-2, and a libctru installation recorded as 2.7.0-1 whose
`mcuhwc.h` defines `InfoLedPattern`. A
different locally installed libctru defines `MCU_InfoLedPattern` instead and
fails to compile this release; compatibility with that version is not yet
verified. The PsyCross submodule must be initialized at the
commit pinned by this repository. No personal game image is used by the normal
source preparation scripts; the image is required to run the result.

The following is the Linux/WSL procedure. A clean-object build was verified
with the matching local toolchain and the initialized PsyCross submodule; a
fresh clone on a second machine has not yet been verified:

```sh
git submodule update --init pc_port/PsyCross
export DEVKITPRO=/path/to/the/compatible/devkitpro
export DEVKITARM="$DEVKITPRO/devkitARM"
export PATH="$DEVKITPRO/tools/bin:$DEVKITARM/bin:$PATH"
cd 3ds_port
make -j8 -f Makefile.game SH_3DS_DEPLOY=0
```

The expected output is `3ds_port/silenthill_game.3dsx`, accompanied by the
ELF, map and SMDH files. `SH_3DS_DEPLOY=0` disables an optional local
post-build hook; a clean checkout does not include that hook. Generated
provenance and symbol reports are written to `3ds_port/build/reports/`.

### CIA packaging

`3ds_port/cia/package.py` packages a built ELF using the included custom panel
CGFX, icon PNG and WAV in `3ds_port/packaging/`, plus external `bannertool`
and `makerom`; it then runs the included container verifier. From `3ds_port`:

```sh
python3 cia/package.py \
  --elf silenthill_game.elf \
  --bannertool /path/to/bannertool --makerom /path/to/makerom \
  --output build/cia
```

The script writes `SH-3DS-v0.9.1.cia`, `SH-3DS.smdh` and `SH-3DS.bnr` under
the output directory. No separate image or audio conversion tool is needed for
the supplied inputs: bannertool converts the PNG and WAV while packaging. The
pre-converted CGFX is retained as the known-working input; an editable source
and repeatable CGFX conversion have not been established. The presentation
inputs are included in the source tree; makerom and bannertool must be supplied
separately. A fresh clone on a second machine remains untested.

The local verification used [Project_CTR makerom](https://github.com/3DSGuy/Project_CTR)
commit `d52c2b0e788c2d085763d7c5dcc4b2edd9ffb7d8` and
[bannertool](https://github.com/diasurgical/bannertool) commit
`16d8c5a0ce02a5e06e64ab42275132fca57c04a2` (buildtools submodule
`b7043ff1854be48ef0d055bba81b0a69a5bc892f`).
For example, with Git, GNU make and a native C/C++ compiler installed, build
these external tools in a separate directory:

```sh
git clone https://github.com/3DSGuy/Project_CTR.git
git -C Project_CTR checkout d52c2b0e788c2d085763d7c5dcc4b2edd9ffb7d8
make -C Project_CTR/makerom deps program
git clone https://github.com/diasurgical/bannertool.git
git -C bannertool checkout 16d8c5a0ce02a5e06e64ab42275132fca57c04a2
git -C bannertool submodule update --init --recursive
make -C bannertool output/linux-x86_64/bannertool
```

The verified executable paths on x86-64 Linux are
`Project_CTR/makerom/bin/makerom` and
`bannertool/output/linux-x86_64/bannertool`. The latter target avoids the
optional zip step. Toolchain installation and equivalent paths on other hosts
have not been verified here.

## Credits and licensing

SH-3DS is based on the `pc-port` work in
[SlickAmogus/silent-hill-decomp](https://github.com/SlickAmogus/silent-hill-decomp)
and uses [PsyCross](https://github.com/SlickAmogus/PsyCross). The 3DS port was
developed primarily with the help of OpenAI Codex, with development direction,
hardware testing and iteration by the project author. Thanks to the upstream
decompilation, PC-port, PsyCross and third-party contributors.

See [COPYRIGHT.md](COPYRIGHT.md), [LICENSE](LICENSE), the PsyCross submodule and
the individual components' notices for applicable terms. The root GPL file
does not grant a license to Konami's original game or to the decompilation.
See [source provenance](docs/source-provenance.md) for the repository's
game-related data and upstream history.
