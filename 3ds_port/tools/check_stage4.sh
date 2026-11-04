#!/usr/bin/env bash
# Preserve historical accepted Stage 1-3 build reports; audit current Stage 4.
set -euo pipefail
make -C 3ds_port -j2
bash 3ds_port/tools/test_disc.sh
bash 3ds_port/tools/test_tim.sh
bash 3ds_port/tools/test_stage4.sh
python3 3ds_port/tools/test_orientation.py
python3 3ds_port/tools/run_arm_gate.py > 3ds_port/reports/arm-gate.json
python3 3ds_port/tools/run_arm_disc.py > 3ds_port/reports/disc-arm-tests.json
python3 3ds_port/tools/run_arm_tim.py > 3ds_port/reports/tim-arm-tests.json
python3 3ds_port/tools/run_arm_orientation.py
python3 3ds_port/tools/run_arm_stage4.py > 3ds_port/reports/stage4-fs-arm.json
python3 3ds_port/tools/verify_tim.py
python3 3ds_port/tools/probe_abi.py
make -C 3ds_port file-contract
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -I3ds_port/include 3ds_port/tests/texture_layout_test.c -o 3ds_port/build/texture_layout_test
3ds_port/build/texture_layout_test
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage4-build.json
printf 'Stage 4.1 FS integration + Stage 1-3 regressions PASS (current build; frozen hardware-accepted baseline is separate)\n'
