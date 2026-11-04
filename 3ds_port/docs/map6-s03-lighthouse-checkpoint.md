# Lighthouse and MAP6_S03 playtest checkpoint

The reported New 3DS halt was `FAIL 406 OpenTIM queue extent` after the
lighthouse stairs. In the original upper-room path, `func_800D2170` queues
`LHEFFECT.TIM`, waits for the queue, then opens that same buffer again. The
3DS `OpenTIM` adapter assumed every call occurred during queue post-load;
after the wait, the queue cursor no longer described that read. The adapter
now permits this explicit original call through a bounded API which verifies
the last completed CD read's destination, file identity and size. The normal
queue check and the TIM parser remain in use. The lighthouse header also
now installs the collision-reset callback in its proper slot rather than
overwriting the other callback at 0x104.

MAP6_S03 is linked as a resident native overlay, with its original events,
character updates, animation tables, entrance, items, FMV hook and exit
transition. MAP6_S04 is a boundary and is not integrated by this checkpoint.

The ARM component suites cover MAP6_S02 and MAP6_S03 event/callback closure,
transitions, flags, items, save checksums, Unknown Liquid, Kaufmann flag 391,
and the 636-byte save ABI. The previous-content component regression passes.
The MAP6_S03 main-loop runner reaches controllable play using explicit
runner-only GPU cache service substitution; its audio/GPU boundaries are not
hardware emulation. Strong unresolved ELF symbols: none.
The upper-lighthouse runner exercised the direct TIM reopen and 70 Alessa
updates without a halt; the unskipped scene did not finish within its CPU
time limit, so scene completion remains a hardware validation item.

Hardware validation required: start from the boat save, climb the lighthouse,
observe the full Alessa sequence, leave the lighthouse, enter and traverse
MAP6_S03 to the MAP6_S04 transition boundary. Verify rendering, audio, FMV,
controls and save/reload on the New 3DS. Publishing is not hardware acceptance.
