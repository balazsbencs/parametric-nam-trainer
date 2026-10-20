# Training speed work

The configuration ideas were informed by sskalnik/neural-amp-modeler at
`fd48d97f030bf0be520487edfbfd61430b6fcfd2`, particularly precision, batch/window
controls, persistent workers and ReduceLROnPlateau. This implementation uses the
existing parametric trainer, model format and export qualification. It does not
replace the A2 topology with the other fork's accuracy-oriented architectures.

The current upstream already supports compiling ConcatWaveNet's conditioned
forward on CUDA. The desktop previously forced compilation off, FP32, and zero
loader workers. The Runpod adapter already enabled cuDNN benchmarking and pinned
memory. Those supported CUDA defaults are retained. CPU/MPS remain eager FP32.

`tune` starts each candidate in a separate process with the same seed and initial
weights. It samples the beginning, middle and end of each input-file group, so
ordinary and augmented inputs both participate without loading every capture.
It executes the real loss, anchors and optimizer, checks finite weights/gradients,
and records data-loader-inclusive steady throughput. It never exports a model.
Warmup, first-step cost, total process time and peak CUDA allocation are reported
separately. Candidate timeouts and failures are recorded; cancellation terminates
the trial's process group. Sampling and short runs cannot establish convergence
or audio quality; full qualification still applies after training.

A six-trial CPU sweep of the actual Bassman Standard raw model used two Torch
threads, two warmup batches and four measured batches per candidate:

| Batch | Training window | Workers | Audio seconds/s |
| ---: | ---: | ---: | ---: |
| 1 | 8192 | 0 | 0.325 |
| 4 | 8192 | 0 | 0.936 |
| 8 | 8192 | 0 | 1.292 |
| 16 | 8192 | 0 | 1.330 |
| 16 | 16384 | 0 | 1.857 |
| 16 | 16384 | 2 | 1.855 |

Batch 16/window 16384/zero workers was selected. It measured about 2× the steady
throughput of batch 4/window 8192. Adding two workers made no meaningful difference.
These are short local CPU observations, not M2/CUDA estimates or claims about
time to convergence. Full per-trial startup and timing data is in
[the measured report](benchmarks/bassman-cpu-20261020.json). Larger batches/windows
also change optimization dynamics. Compare time to a passing qualified model on
the intended hardware before treating these settings as a quality-preserving win.

A recommendation is tied to hardware/runtime, upstream revision, architecture,
controls/losses, starting NAM, input/output recording hashes and baseline dataset
configuration. It cannot be applied to a different project/model/device without
rebenchmarking. The run snapshots its effective settings. Scheduler/stopping
choices remain independent; batch changes do not automatically increase LR.

Validation covers real benchmark subprocesses, recommendation replay, stale
hardware/model rejection, unsupported acceleration, worker cleanup, runtime-state
restoration and a real plateau-scheduler/early-stopping training/export run.
Desktop controls were inspected at 1140×840 and 800×800.
