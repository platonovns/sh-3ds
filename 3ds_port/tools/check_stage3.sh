#!/usr/bin/env bash
# Full current suite, preserving frozen Stage 1B/2 footprint reports.
set -euo pipefail
python3 3ds_port/tools/inspect_disc.py > /dev/null
python3 3ds_port/tools/inspect_tim.py > /dev/null
make -C 3ds_port clean
make -C 3ds_port -j2
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage3-build.json
bash 3ds_port/tools/test_disc.sh
bash 3ds_port/tools/test_tim.sh
python3 3ds_port/tools/test_orientation.py
python3 3ds_port/tools/run_arm_gate.py > 3ds_port/reports/arm-gate.json
python3 3ds_port/tools/run_arm_disc.py > 3ds_port/reports/disc-arm-tests.json
python3 3ds_port/tools/run_arm_tim.py > 3ds_port/reports/tim-arm-tests.json
python3 3ds_port/tools/run_arm_orientation.py
python3 3ds_port/tools/verify_tim.py
python3 3ds_port/tools/probe_abi.py
make -C 3ds_port file-contract
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -I3ds_port/include 3ds_port/tests/texture_layout_test.c -o 3ds_port/build/texture_layout_test
3ds_port/build/texture_layout_test
hashes=$(mktemp /tmp/sh-stage3-repro-XXXXXX)
trap 'rm -f "$hashes"' EXIT
sha256sum 3ds_port/silenthill_3ds.3dsx 3ds_port/silenthill_3ds.elf \
          3ds_port/silenthill_3ds.smdh 3ds_port/build/foundation.shbin > "$hashes"
make -C 3ds_port clean
make -C 3ds_port -j2
sha256sum -c "$hashes"
python3 - "$hashes" <<'PY'
import json,sys
from pathlib import Path
entries = [line.split() for line in Path(sys.argv[1]).read_text().splitlines()]
Path('3ds_port/reports/stage3-reproducibility.json').write_text(json.dumps(dict(
    clean_builds=2, byte_identical=True, sha256={name: digest for digest,name in entries}),indent=2)+'\n')
PY
python3 3ds_port/tools/verify_build.py > 3ds_port/reports/stage3-build.json
make -C 3ds_port -j2
printf 'Stage 3: PC/ARM TIM+VRAM+PICA bytes, ANM, regressions, ELF and reproducibility PASS\n'
