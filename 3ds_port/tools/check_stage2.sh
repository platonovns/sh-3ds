#!/usr/bin/env bash
# Run from repo root in devkitPro shell; optional Unicorn dependency as in 1B.
# Legacy regression entry point for the current Stage 3 build. Frozen Stage 2
# report remains intact for memory deltas. Original BIN/CUE stay read-only.
set -euo pipefail
python3 3ds_port/tools/inspect_disc.py > /dev/null
make -C 3ds_port clean
make -C 3ds_port -j2
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage3-build.json
bash 3ds_port/tools/test_disc.sh
python3 3ds_port/tools/run_arm_gate.py > 3ds_port/reports/arm-gate.json
python3 3ds_port/tools/run_arm_disc.py > 3ds_port/reports/disc-arm-tests.json
python3 3ds_port/tools/probe_abi.py
make -C 3ds_port file-contract
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -I3ds_port/include 3ds_port/tests/texture_layout_test.c -o 3ds_port/build/texture_layout_test
3ds_port/build/texture_layout_test
hashes=$(mktemp /tmp/sh-stage2-repro-XXXXXX)
trap 'rm -f "$hashes"' EXIT
sha256sum 3ds_port/silenthill_3ds.3dsx 3ds_port/silenthill_3ds.elf \
          3ds_port/silenthill_3ds.smdh 3ds_port/build/foundation.shbin > "$hashes"
make -C 3ds_port clean
make -C 3ds_port -j2
sha256sum -c "$hashes"
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage3-build.json
make -C 3ds_port -j2
printf 'Stage 2: reference, sanitizer, ARM, ABI, namespace, texture, packaging and reproducibility PASS\n'
