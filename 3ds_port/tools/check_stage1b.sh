#!/usr/bin/env bash
# Run from the repository root in an installed devkitPro shell.
# Optional ARM execution check requires unicorn==2.1.3 in host Python.
# Legacy regression subset checks the current Stage 3 build. Preserve the
# frozen Stage 1B/2 reports used for footprint deltas.
set -euo pipefail
make -C 3ds_port clean
make -C 3ds_port -j2
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage3-build.json
python3 3ds_port/tools/run_arm_gate.py > 3ds_port/reports/arm-gate.json
make -C 3ds_port file-contract
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -I3ds_port/include 3ds_port/tests/texture_layout_test.c -o 3ds_port/build/texture_layout_test
3ds_port/build/texture_layout_test
sha256sum 3ds_port/silenthill_3ds.3dsx 3ds_port/silenthill_3ds.elf \
          3ds_port/silenthill_3ds.smdh 3ds_port/build/foundation.shbin > /tmp/sh-stage1b-first.sha256
make -C 3ds_port clean
make -C 3ds_port -j2
sha256sum -c /tmp/sh-stage1b-first.sha256
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage3-build.json
python3 3ds_port/tools/run_arm_gate.py > 3ds_port/reports/arm-gate.json
make -C 3ds_port -j2
