#!/usr/bin/env bash
# Independent Python oracle must already have generated the reviewed profile.
set -euo pipefail
mkdir -p 3ds_port/build
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -I3ds_port/include 3ds_port/source/{psx_disc,sh_disc,psyq_file,disc_gate}.c \
   3ds_port/tests/disc_test.c -Wl,--wrap=fread -o 3ds_port/build/disc_test
3ds_port/build/disc_test "${1:-sh1_data/sh1.bin}" "${2:-sh1_data/sh1.cue}" \
    3ds_port/reports/disc-pc.log 3ds_port/reports/disc-negative.log \
    > 3ds_port/reports/disc-pc-tests.json
cat 3ds_port/reports/disc-pc-tests.json
