#!/usr/bin/env bash
set -euo pipefail
cc -std=gnu11 -O1 -g -Wall -Wextra -Werror=implicit-function-declaration \
   -Werror=incompatible-pointer-types -ffunction-sections -fdata-sections \
   -fno-strict-aliasing -fwrapv -fsanitize=address,undefined \
   -include 3ds_port/include/engine_profile.h \
   -I3ds_port/include -Ipc_port/include -Ipc_port/include/psyq_compat \
   -Iinclude -Iinclude/decomp -Ipc_port/PsyCross/include/psx -Ipc_port/PsyCross/include \
   3ds_port/source/{stage4_fs,psx_disc,sh_disc,psx_tim,psx_vram}.c \
   src/main/{fsqueue_1,fsqueue_2,fsqueue_3,fileinfo,fsmem}.c pc_port/src/psx_memory.c \
   3ds_port/tests/stage4_fs_test.c -Wl,--gc-sections,--wrap=fread -o 3ds_port/build/stage4_fs_test
3ds_port/build/stage4_fs_test sh1_data/sh1.bin sh1_data/sh1.cue > 3ds_port/reports/stage4-fs-pc.json
cat 3ds_port/reports/stage4-fs-pc.json
