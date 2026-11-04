# Integration through Block 5, Native-FMV and OVERLAP

This is a hardware integration, not a sealed content checkpoint or hardware
acceptance. The content lineage ends at `80912cb1837a0faa7814f22e988629a2c491b470`
and descends from the recovered Stage 11A B context `6679d655a`. It already
contains School `65ab73346`, Post-school `6ae58172b`, Alchemilla `06a13a05a`,
Otherworld Central `0ba637697`, and First Sewer `9e02278c2`. Native-FMV
`e94a90a6b` is applied separately once. No Block 6 was added.

Stage 11A B accepted control is `stage11a-cpu-B-src-8c51d74ee1feb7e0`.
The four files in `3ds_port/stage11a_b` are the exact generated CPU B inputs
whose SHA-256 values appear in its source provenance. The Makefile restores
its per-object feature defines, Core 2 SPU affinity, wrappers and extra runtime
objects. FMV's independent objects are explicitly included in the ELF inputs.

The only scheduling change from Stage 11B is the transform in
`build_stage11b_async_overlap.py` for candidate
`stage11b-10-overlap-src-6212e8c101220862`: defer the final wait in stable
in-game top display, drain pending primitives at the next stable update, and
retain full synchronization for transitions, DrawSync, VRAM and readback.
FMV entry explicitly synchronizes before taking over display. No 11B sampled
frame attribution, audit UI, readback, RGB5, LIGHT, PACKET, GTE_CLEAN, PICA
or Q12 experiment is included. Existing 11A diagnostics are retained.

The hardware evidence for OVERLAP is one limited courtyard observation,
not general acceptance. Real hardware must still validate feedback effects,
resource lifetimes, transitions, audio/video, save/load and all later scenes.

On the integrated ARM ELF, the short CPU fixtures reached MAP0, School,
Post-school, Hospital, Otherworld, Sewer, Resort, Kaufmann and the completed
Boat state; the standard scene entry reached 21 updates and the existing Boat
skip fixture completed with flags 424 and 1024.
The host FMV lifecycle fixture and eight 636-byte save/checksum roundtrips
passed. A separate seeded Boat entry at MAP6_S00 point 4 failed after three
updates in DMS character lookup with an invalid pointer. This is an unresolved
fixture/scene risk, not evidence of a successful natural Boat playthrough.
SDK/GPU/audio boundaries are simulated in these CPU tests.
