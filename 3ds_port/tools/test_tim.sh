#!/usr/bin/env bash
set -euo pipefail
mkdir -p 3ds_port/build
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -I3ds_port/include 3ds_port/source/{psx_disc,sh_disc,psx_vram,psx_tim,tim_gate,tim_selftest}.c \
   3ds_port/tests/tim_test.c -Wl,--wrap=fread,--wrap=ShDisc_Resolve -o 3ds_port/build/tim_test
3ds_port/build/tim_test "${1:-sh1_data/sh1.bin}" "${2:-sh1_data/sh1.cue}" > 3ds_port/reports/tim-pc-tests.json
cat 3ds_port/reports/tim-pc-tests.json
