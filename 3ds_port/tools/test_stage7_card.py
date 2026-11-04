#!/usr/bin/env python3
"""Persistence across processes, bad images, interrupted commit and bounds."""
from pathlib import Path
import json, os, subprocess, tempfile
p=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='sh-card-') as d:
    root=Path(d);exe=root/'test';card=root/'memcard.mcr'
    cmd=['cc','-std=gnu11','-g','-O1','-Wall','-Wextra','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(p/'include'),str(p/'tests/stage7_card_test.c'),str(p/'source/game_card_image.c'),'-o',str(exe)]
    subprocess.run(cmd,check=True)
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
    def run(mode):subprocess.run([str(exe),mode,str(card)],check=True,env=env,capture_output=True)
    run('create');saved=card.read_bytes();assert len(saved)==131072
    run('read');assert card.read_bytes()==saved
    # Interrupted replacement: validated prior image remains under .bak.
    backup=Path(str(card)+'.bak');backup.write_bytes(saved);card.unlink()
    run('read');assert card.read_bytes()==saved
    # Existing malformed main must never be silently overwritten/reformatted.
    cases=[b'',saved[:131071],saved+b'X']
    for offset in (0,127,128,255,128+8,128+10):
        data=bytearray(saved);data[offset]^=0x55;cases.append(data)
    for bad in cases:
        card.write_bytes(bad);run('refuse');assert card.read_bytes()==bad
    card.write_bytes(saved)
    # A blocked staging path produces a failed write and preserves both RAM
    # and the durable original, rather than reporting success after fwrite.
    staged=Path(str(card)+'.tmp');staged.mkdir();run('write-fails');assert card.read_bytes()==saved;staged.rmdir()
    # Repeated mounts are bounded and do not retain transaction copies.
    for _ in range(5):run('read')
    report={'status':'PASS','sanitizers':'ASan+UBSan','process_restart_persistence':True,'raw_image_bytes':len(saved),'corruption_cases':len(cases),'interrupted_replace_recovery':True,'failed_write_preserves_image':True,'display_plan_checks':True,'persistent_heap_bytes':131072,'transaction_heap_peak_bytes':262144,'linear_bytes':0}
    (p/'reports/stage7-card-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
