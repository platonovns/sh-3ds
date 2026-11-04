# Stage 11B — CLOSED: measured boundary, no new accepted baseline

28.10.2026. Closed by user direction to prioritize gameplay content. Accepted
performance baseline remains exact Stage 11A B: `stage11a-cpu-B-src-8c51d74ee1feb7e0`,
3DSX SHA-256 `af896f46797e8df7f71188f3ef9faed60364176d69029569a8ff84b4f02c1690`,
ELF SHA-256 `0da43e2d73eb2950440e0885dbe0efc724c9b600f5564fe6441d6c699723878c`.
The accepted artifact and its existing archive/receipt are unchanged. There is
no accepted 11B optimization, and no School, FMV or other content merge.

## Hardware evidence

Same general MAP3/room23 courtyard, New 3DS, P0, F1, 60 cap, flashlight ON.
Raw frame count and recording duration are used for ms/frame and comparisons.
Different binaries were tested at different times and poses. These are observed
single-window differences, not isolated speedups or reproducibility evidence.

| Window | Build | Frames | Duration ms | LCD FPS | ms/frame |
|---|---|---:|---:|---:|---:|
| 033 | exact accepted B CONTROL | 840 | 20628.8401 | 40.7197 | 24.5581 |
| 045 | CONTROL_DEV (diagnostic derivative) | 1050 | 25689.1481 | 40.8733 | 24.4659 |
| 046 | 11B.9 FRAME_AUDIT diagnostic | 1048 | 25640.5832 | 40.8727 | 24.4662 |
| 048 | OVERLAP diagnostic candidate | 1099 | 25531.1803 | 43.0454 | 23.2313 |

OVERLAP versus like-instrumented 046: +2.1727 FPS, **+5.3158%**, and
−1.2349 ms/LCD frame. Versus the separately captured exact B 033: +5.7115%,
−1.3269 ms/frame; this comparison is even less controlled, with differing pose,
camera and diagnostic instrumentation. 046 has a small camera drift; 048 is
stationary but its player yaw and camera differ from 046. OVERLAP session has
one ON window only: no OFF window and no second workload. The user observed
about 42–43 FPS and no visual problems in the courtyard. This is useful but
does not establish general correctness, repeatability or a substantial accepted
gain. No further A/B is requested in this closure.

11B.9 OFF window 047 is 59.2106 FPS, 16.8889 ms/frame, and is not an OVERLAP
comparison. 046/047 source session SHA-256
`9c534b7d453ce21e8122a5cf7fb4222b1c06b7daca109781977f9e392d6e81ef`;
048 source session SHA-256
`94cf19bcbbc0ffebcdabd425fa143d0fe1cf20e6a4f42e8fbc95c55ae8f60cc6`.
Both raw files and receipts passed independent receipt/hash verification.
Both sessions completed; 048 sampled 69 frames with zero accounting errors,
P0/F1, stable recorded pose, and audio reported zero starves and drops.

11B.9 selected-frame exclusive ON timing: world 6.581, OT 1.610, texture 1.178,
command preparation 1.343, FrameBegin 4.669, RGB5 4.258, cache flush 2.041,
cache invalidation 1.191 and unclassified 2.131 ms/frame. CPU elapsed includes
preemption and SDK overhead. Selected vs unselected frame means 25.313 vs
24.410 ms/frame show measurement perturbation and scene/time variability.
OVERLAP selected FrameBegin is 3.181 ms/frame; selected and unselected wall
means are 22.913 and 23.251 ms/frame. These figures do not prove causality.
GPU drawing-time queries refer to earlier queues, overlap CPU and are not
additive with CPU categories; FrameBegin alone does not prove GPU saturation.

## Experiments retained, not accepted

* OVERLAP: `stage11b-10-overlap-src-6212e8c101220862`, SHA-256
  `e28175f7d80cf6526a10a9ac9298dc69d2b85159776c9e21f146de9db78cda90`.
  Its guarded final in-game GPU submission defers a fence but retains explicit
  DrawSync, VRAM, feedback and renderer resource barriers. Offline checks did
  not execute PICA; the one hardware window is not broad semantic validation.
  Preserve as an experimental checkpoint, not an accepted build.
* GTE_CLEAN: `stage11b-7-gte-clean-src-6954554d37252a4d`, SHA-256
  `fbf047a90eacf5d24dce4798991c5096b3839730502aa68ae488b8fa2a8dbbc3`.
  One GTE_CLEAN/CONTROL_DEV pair measured 41.7806/40.8733 FPS (+2.22%);
  retained as positive but unaccepted.
* READBACK, RGB5, LIGHT, PACKET, GTE coverage, bounded PICA probes and their
  original evidence remain available. READBACK and RGB5 showed small single
  P0 differences, PACKET did not establish an improvement. RGB5's paired
  oracle checked 8 captures on hardware, not all possible scenes. The old
  direct VRAM alias mismatch remains non-authoritative; it is neither proof
  of a defect nor proof of equivalence. See 11B.1/11B.2 hardware reports.

## Boundary and future work

CPU consumes the examined GTE outputs for lighting, clipping, OT and primitive
construction before final PICA submission; moving these computations earlier
to GPU without a synchronous return requires changing those boundaries. The
single shared attachment, canonical CPU-visible PS1 VRAM, feedback cuts and
queue/resource lifetimes constrain parallelism. The measured 4.3 ms RGB5 and
4.7 ms FrameBegin intervals are not established removable fractions. These
results document the current architecture and workloads, not a universal or
mathematically proven performance ceiling.

For a future separate Renderer v2/performance stage, investigate explicit
resource ownership and frame/feedback scheduling, safe overlap and bounded
region materialization while preserving CPU-visible LoadImage, StoreImage,
MoveImage, ClearImage, CLUT/STP/ABR, masks, invalidation and command order.
Any retained candidate should be compared repeatedly with exact B in a second
representative gameplay workload and checked for broad visual and CPU-visible
correctness before acceptance. Do not assume a GPU-authoritative texture can
replace canonical VRAM. Gameplay remains the performance priority.

## Recovery

Frozen B: `3ds_port/build/hardware-stage11a-accepted-20261028/manifest.json`;
freeze receipt `3ds_port/reports/stage11a-hardware-accepted-20261028-freeze.json`.
Experimental artifacts and generated sources: `3ds_port/build/stage11b-7-gte-clean/`,
`3ds_port/build/stage11b-9-frame-audit/`, `3ds_port/build/stage11b-10-overlap-offline/`.
The durable experimental bundle and its separate SHA-256 inventory/receipt are
under `3ds_port/baselines/stage11b-closure-experiments-20261028.zip` and its
`.receipt.json`; existing earlier checkpoint archives remain untouched.
Raw received hardware sessions and receipts are in `3ds_port/reports/incoming-hardware/`.
