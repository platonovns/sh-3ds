#!/usr/bin/env bash
set -euo pipefail
for name in pc_native_menu pc_bind_core pc_input_glyphs pc_ach_model; do
    cc -O1 -g -fsanitize=address,undefined -Ipc_port/include \
        "pc_port/tests/${name}_test.c" "pc_port/src/${name}.c" \
        -o "3ds_port/build/${name}_test"
    "3ds_port/build/${name}_test"
done
