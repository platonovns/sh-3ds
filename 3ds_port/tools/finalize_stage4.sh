#!/usr/bin/env bash
set -euo pipefail
make -C 3ds_port -j2
# Re-execute affected ARM paths against the final linked artifact.
python3 3ds_port/tools/run_arm_stage4.py > 3ds_port/reports/stage4-fs-arm.json
python3 3ds_port/tools/run_arm_tim.py > 3ds_port/reports/tim-arm-tests.json
python3 3ds_port/tools/run_arm_orientation.py
python3 3ds_port/tools/verify_tim.py
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage4-build.json
python3 3ds_port/tools/classify_stage4.py
sha256sum 3ds_port/silenthill_3ds.3dsx
