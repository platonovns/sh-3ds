#!/usr/bin/env bash
set -euo pipefail
p=3ds_port
audio=pc_port/PsyCross/src/audio
g++ -std=c++17 -O2 -g -Wall -Wextra -fwrapv -ffunction-sections -fdata-sections \
    -fsanitize=address -I$p/build/audio -I$audio -Ipc_port/PsyCross/include \
    -Ipc_port/PsyCross/include/psx $p/build/audio/PsyX_SPUCore.cpp \
    $audio/PsyX_SPUReverb.cpp pc_port/PsyCross/tests/audio/PsyX_SPUCore_test.cpp \
    $p/tests/stage9_core_stubs.cpp -Wl,--gc-sections -o $p/build/stage9_core_test
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 $p/build/stage9_core_test
for kind in original native; do
    if [ "$kind" = original ]; then
        inc=$audio
        sources="$audio/PsyX_SPUCore.cpp $audio/PsyX_IdealReverb.cpp $audio/PsyX_ReferenceReverb.cpp $audio/PsyX_ReferenceResampler.cpp"
    else
        inc=$p/build/audio
        sources="$p/build/audio/PsyX_SPUCore.cpp"
    fi
    g++ -std=c++17 -O2 -fwrapv -ffunction-sections -fdata-sections -I$inc -I$audio \
        -Ipc_port/PsyCross/include -Ipc_port/PsyCross/include/psx \
        $sources $audio/PsyX_SPUReverb.cpp $p/tests/stage9_spu_equivalence.cpp \
        $p/tests/stage9_core_stubs.cpp -Wl,--gc-sections -pthread -o $p/build/stage9_equivalence_$kind
    $p/build/stage9_equivalence_$kind > $p/reports/stage9-core-equivalence-$kind.txt
done
cmp $p/reports/stage9-core-equivalence-original.txt $p/reports/stage9-core-equivalence-native.txt
echo 'PASS: 48 PCM/voice-state/SPU-RAM/ENDX cases are identical to the original exact renderer'
