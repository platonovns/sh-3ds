# Captured particle contour regression

Captured read-only from Azahar run `20261025-190825-690`, normal New Game,
build `stage6.0-src-a3fea5e1b8d030dd`, during a Grey Child knife hit.
The application was spinning at `func_800CC8FC+0x4c4`, particle.c:1848.

`syswork.dat` is the 38,584-byte native g_SysWork runtime structure.
`particle-vectors.dat` is 128 bytes at PSX RAM offset 0xE0C4C.
No disc image, resource file, save or executable is included.

`tools/test_stage6_particle_hull.py` restores these inputs into a separate
bounded ARM CPU test. The original function exceeds 250,000 instructions;
the fixed function returns a closed, convex six-vertex contour. This is a
component regression, not normal-route or hardware acceptance.
