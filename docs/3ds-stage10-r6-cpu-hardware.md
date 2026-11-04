# Stage 10 R6 CPU audit: New 3DS hardware recordings

Date: 2026-10-28. Hardware timing/core inventory received. The user subsequently
closed [Stage 10 as HARDWARE ACCEPTED](3ds-stage10-accepted.md) on this date.
Performance observations below are retained for follow-up after stage closure.
No game code, affinity, priority, CPU budget, renderer or audio behavior changed
for this analysis. No new hardware build was produced.

## Evidence and reproducibility

The user identified 001 as the school courtyard without the flashlight, 002 as
the courtyard with the flashlight, and 003 as the Harry/Cybil Cafe dialogue.
Original Downloads files are preserved. Byte-identical copies, SHA-256 hashes,
labels and calculated metrics are stored in
`3ds_port/reports/stage10-r6-cpu-hardware-20261028/`:

- `samples.json`: provenance and evidence hashes;
- `cpu_audit_001.txt`, `cpu_audit_002.txt`, `cpu_audit_003.txt`: raw hardware files;
- `analysis.json`: recording-window calculations and symbolized thread inventory.

All three have sample_complete=1, report_complete=1, valid coherent CPU deltas,
matching LCD/profile frame counts, and the same build
`stage10.0-cpurec-src-a5ed13f76dac9640`, CPU_AUDIT_RECORDER_ONLY.
Entry addresses were symbolized against the frozen recorder ELF, SHA-256
`60af1d986bb7da4c041058950b74abbe3f99523aed8c1f379d89588490a40d8e`.
This is real hardware evidence, separate from the similarly named emulator files.

Reproduce inside the configured toolchain environment from the repository root:

```sh
python3 3ds_port/tools/analyze_stage10_cpu_windows.py \
  --samples 3ds_port/reports/stage10-r6-cpu-hardware-20261028/samples.json \
  --elf 3ds_port/build/hardware-stage10-cpu-recorder/silenthill_cpu_recorder.elf \
  --output 3ds_port/reports/stage10-r6-cpu-hardware-20261028/analysis.json
```

The analyzer checks hashes, completion/schema, build-to-ELF identity, frame and
duration consistency, scope/mean arithmetic, light pairing and player pose. It
does not use `cpu_scope_*` lifetime timings for recording-window comparisons.

## Measured frames and main-thread envelopes

Both courtyard samples are map 3 / room 23, with exactly the same player pose
(-73816, -262627, 1663). All samples use 30 FPS mode and Hybrid controls.
Cafe is map 1 / room 36, flashlight OFF. These are diagnostic-build measurements.

| Recording | Duration s | Frames | LCD FPS | Wall ms/frame | Work excluding pacing/report/pause ms/frame |
| --- | ---: | ---: | ---: | ---: | ---: |
| 001 courtyard OFF | 30.4844 | 723 | 23.7170 | 42.1638 | 41.5820 |
| 002 courtyard ON | 30.7562 | 355 | 11.5424 | 86.6371 | 85.5823 |
| 003 Cafe dialogue | 110.2557 | 1160 | 10.5210 | 95.0480 | 83.6251 |

Camera is not perfectly matched: 001 has a small camera drift (context mask
0x40); 002 is internally stable but has a different camera from 001. For example,
camera yaw starts at 1513 in 001 and 1470 in 002. The player remains stationary.
The 51.33% FPS reduction and 44.47 ms/frame increase identify the observed pair,
not an exact causal flashlight-only delta at identical camera pixels.
Cafe also has camera changes (mask 0x40), expected during dialogue. Its 110-second
aggregate cannot identify a particular camera shot as the worst one.

All times below are inclusive elapsed time, including preemption and blocking.
Rows overlap. World is inside update; decode/flush are inside primitive work;
commands/presentation are inside submission. GTE is sampled every 16th frame
(46/22/72 sampled frames), not the mean of all frames or a separate additive phase.
Main scopes can include audio-worker preemption. Work is wall minus explicit
pacing/report/pause; it is not exclusive main scheduled CPU time.

| Elapsed ms/frame | Courtyard OFF | Courtyard ON | Cafe dialogue |
| --- | ---: | ---: | ---: |
| Update | 21.2803 | 23.0971 | 24.0423 |
| World | 19.6320 | 18.4971 | 19.8180 |
| GTE, sampled frames only | 22.2736 | 22.7257 | 25.1340 |
| Primitive processing | 5.4225 | 40.9827 | 14.8543 |
| Texture decode | 0 | 21.0456 | 0.0636 |
| Texture cache flush | 0 | 4.6066 | 0.0062 |
| CPU framebuffer RGB5 resolve, per call | 0 calls | 9.3787 | 0 calls |
| Flashlight setup, per call | 0.0199 | 0.0429 | 0.0314 |
| Submission | 5.9004 | 6.2534 | 28.3603 |
| Command emission | 3.9936 | 5.7775 | 27.6251 |
| Renderer wait_idle | 8.4059 | 9.0251 | 13.1063 |
| Explicit VBlank wait | 0.2419 | 0 | 10.3906 |
| Diagnostic report | 0.3399 | 1.0548 | 1.0322 |
| Main resource/I/O | 0 | 0 | 0 |
| Primitives per frame | 493.12 | 534.51 | 1795.50 |
| Draw calls per frame | 274.64 | 309.87 | 1509.76 |

Flashlight: 2931 decoded/flushed pages in 355 frames, 8.26 pages/frame, versus
zero in the OFF window. Counted C3D_TexFlush allocation sizes total 768344064
bytes, 23.82 MiB/s. This counts flushed page sizes, not measured physical DRAM
bandwidth. Setup is only 0.043 ms/call; vertex lighting is not separately isolated.
The dominant extra envelopes are repeated feedback resolve, page decoding and
flushes, rather than flashlight setup or a measured rise in world/GTE cost.
Investigate invalidation/decode frequency and current-frame dependencies first.

Cafe: about 5.50 times as many draws/frame as courtyard OFF and 6.92 times the
command time. Texture decoding is almost absent: 26 pages over the entire
110-second window. The renderer command path is the main scene-dependent lead.
wait_idle times C3D_FrameBegin/FrameEnd and may include GPU/transfer waits and
audio preemption; it does not by itself prove a GPU bottleneck. Explicit VBlank
waiting adds 10.39 ms/frame and should be traced separately from rendering cost.
Zero main FsQueue I/O does not mean zero SD activity: XA owns a private BIN handle.

## Actual threads, cores and CPU resources

Hardware reports New 3DS, Luma 13.3.3, 804 MHz current/high clock and L2 enabled.
APT CPU budget is zero. Six live threads match both kernel process count and
symbolized handle inventory; three completed probe threads are not live workers.

| Thread / exact ELF symbol | ID | Priority | Stack | Requested core | Observed core |
| --- | ---: | ---: | ---: | --- | --- |
| Main / main | 992 | 0x30 | inherited | inherited | 0 |
| APT / aptEventHandler | 993 | 0x31 | 4 KiB | -2 default | not sampled |
| GSP / gspEventThreadMain | 997 | 0x1a | 4 KiB | -2 default | not sampled |
| XA / worker | 1001 | 0x2f | 24 KiB | -2 default | 0 |
| NDSP / ndspThreadMain | 1003 | 0x18 | 4 KiB | -2 default | 0, callback sampling |
| SPU / audio_thread | 1004 | 0x18 | 32 KiB | -2 default | 0 |

Observed main/SPU/XA/NDSP masks are all 0x1. APT/GSP execution on the same default
core is inferred, not measured. Lower priority numbers have higher priority;
SPU/XA can preempt main. Game simulation, software GTE, geometry, lighting,
main resource queue, primitive/texture preparation and GPU submission remain on
main. The application does not currently distribute this work to cores 2/3.

One-shot probes actually executed on requested cores 0, 2 AND 3, with matching
MPIDR and successful kernel creation Results. Core 1 was skipped because APT
budget was zero. In this actual launcher/CFW environment both extra cores 2/3
are accessible to the probe; the earlier generic expectation that core 3 would
be unavailable does not describe this observation. No permission-policy change
is made from it. This proves execution, not full-core sustained throughput,
exclusive ownership, system-wide idleness or a guarantee for another launcher.
Core 2 is the first conservative target for a future bounded experiment.

Probe IDs 998/999/1000 were joined/freed. Their later 0xD9001BF7 handle-query
results are expected closed handles, not game failures. Inventory overflow is 0.
Exact thread scheduled percentages and core-idle percentages remain unavailable.

## Audio is a substantial shared-core load

| Recording | SPU blocks/s | Elapsed ms/512-frame block | SPU block elapsed/window | XA step elapsed/window |
| --- | ---: | ---: | ---: | ---: |
| 001 OFF | 86.14 | 6.4260 | 55.36% | 0.038% |
| 002 ON | 86.13 | 6.4285 | 55.37% | 0.040% |
| 003 Cafe | 86.14 | 6.4072 | 55.19% | 7.718% |

The real SPU worker prepares 512 frames at 44.1 kHz, approximately one block
every 11.61 ms. It spends about 552-554 elapsed ms per second inside block work
on the SAME core as main, at higher priority. RenderFrames accounts for about
54-55% of wall time; flush/submission/diagnostic scanning account for the small
remainder. This is strong evidence of substantial shared-core audio work, not
an exact 55% scheduled CPU measurement. It was absent in DSP-less Azahar runs.

Audio cost per second/block is essentially constant across the three windows.
The existing per-visual-frame SPU values (23.04 / 47.34 / 51.47 ms) increase when
visual FPS falls; this does not mean the flashlight doubles audio work.
XA gains real activity in dialogue (8509.54 ms step elapsed over 110255.66 ms),
including decode, private BIN access, locks and possible SPU preemption.
Its 7.72% elapsed fraction cannot be added to SPU as exclusive CPU utilization.

The measured audio_lock totals are only 1.4130 / 1.5285 / 5.0568 ms per window.
This counter measures SPU-worker lock acquisition, NOT main-thread time waiting
for SPU register-access locks. Main lock waits must be separated before claiming
that moving the mixer would remove all its impact. Voice/reverb/mix estimates
sample one rotating PCM frame per block and extrapolate by 512; their sums can
exceed the exact block measurement. They suggest voice processing is the largest
audio component, without establishing additive exact component percentages.

The current generated native SPU already skips only proven stationary zero-pitch,
zero-envelope direct-volume voices (prepare_audio.py / frozenVoices). A broad
"skip all inaudible voices" change would violate current decoder/ENDX/PMON/sweep
semantics. Audit interpolation, ADPCM, per-sample arithmetic and state-preserving
fast paths before considering another thread. Preserve PCM and internal SPU state.
Window underrun/dropped-frame deltas and worst-block duration are not recorded
here; lifetime peaks cannot be presented as window worst cases or a zero-drop proof.

## Future candidates after algorithmic work

These costs are elapsed inclusive envelopes, not additive removable CPU time.
Numerical FPS gains are not justified without scheduled-time or isolated job
measurements; the benefit assessments below are conditional estimates.

| Candidate / current hardware cost | State dependencies and async safety | Synchronization cost | Expected benefit and risk |
| --- | --- | --- | --- |
| GTE/geometry: sampled 22.27/22.73/25.13 ms | Global GTE registers/FIFOs/flags, scratchpad, bones, matrices, packet arena and ordering table. Individual operations cannot safely run concurrently. Immutable coarse object jobs need private state. | Snapshot inputs, disjoint packet regions, barrier and deterministic ordered merge; fine per-op jobs are unsuitable. | Potentially material in geometry-heavy scenes, but not a measured frame-average saving. High risk; optimize redundant transforms and isolate coarse batches first. |
| Lighting: setup 0.020/0.043/0.031 ms, vertex cost unisolated inside world/GTE | Live lights, fog, transforms and shared GTE. Only a pure color batch over frozen inputs could run asynchronously. | Copy light/vertex state, join before primitive use, preserve exact rounding and current-frame state. | Setup-only offload is negligible; vertex benefit unknown. Medium/high risk. Flashlight regression points chiefly to feedback/textures, not setup. |
| Texture/CLUT decode: 21.05 ms/frame ON, 0 OFF, 0.064 Cafe; resolve 9.38 and flush 4.61 ON | Mutable VRAM/CLUT generations, feedback ordering, pinned cache and eviction. Async decode requires immutable source generations and disjoint output ownership. | Snapshot/copy costs, generation tags, queue/join before PICA use, flush/coherency fences; avoid scarce linear-memory staging. | High potential in ON window, almost no steady OFF/Cafe benefit. Pure compute saving is below the 21.05 ms elapsed envelope; no defensible FPS estimate yet. Medium/high risk. Reduce invalidations and repeated full-page work first. |
| Resource/BIN: main steady cost 0; Cafe XA step 7.72% wall separately | Original FsQueue RAM/overlay ownership; XA already has a private FILE and bounded queue. Read-only bounded prefetch can be async; decompression/relocation/commit remain ordered. | Private handles, epoch/cancel queue, SD contention control and main commit barrier. | No steady courtyard/Cafe resource gain supported; possible transition latency reduction remains unmeasured here. Medium risk; protect XA deadlines and memory headroom. |
| Renderer preparation: command 3.99/5.78/27.63 ms; Cafe 1509.76 draws/frame | Stateful ordered PS1 packets, masks/blends/STP, cache pins, feedback generations and global Citro3D/PICA state. Only isolated immutable parsing/conversion could be parallel. GPU commands stay on main. | Ordered merge, resource fences and joins per useful coarse batch. | High scene-specific priority in Cafe; reduce command/draw/state overhead algorithmically first. The full 27.63 ms scope cannot simply be moved to another core. High risk. |
| Audio/SPU: existing worker 6.4 ms/block, 55.2-55.4% elapsed wall; XA active in Cafe | Global SPU state/RAM, register chronology, reverb history, core_lock and XA ring/epochs. Moving the existing worker is more plausible than splitting voices; not automatically deterministic/safe. | Cross-core cache and mutex traffic; main register-lock waits may replace preemption. Preserve bounded queues, priority, PCM chronology and deadlines. | Strongest shared-core relief candidate after algorithm audit, potentially substantial across all scenes. Exact FPS gain unknown. Medium/high risk: benchmark core 2 under fixed scenes with bit/state equivalence, main lock waits, queue/drop deltas and block deadlines before adoption. Core 3 is not needed for the first experiment. |

## Result and next validation boundary

The recorder solved the SD collection workflow: three independently numbered,
complete windows were recovered without manual mid-run SD access. The analysis
tool preserves their hashes and separates recording windows from lifetime data.
No additional replay or replacement samples are needed to establish these leads.

Next useful work is isolated profiling/algorithm optimization of SPU voice work,
flashlight feedback/decode/invalidation, and Cafe command generation, in that
order of cross-scene relevance rather than speculative broad threading. A future
worker-affinity experiment requires explicit experimental build identity and
deterministic/audio-deadline checks. Current affinity, priorities and budget are
unchanged. Hardware R6 performance improvement is not claimed from this audit.
