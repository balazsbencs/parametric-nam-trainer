# Standard / Nano training-time benchmark

This package includes the real Bassman dataset, added teacher attacks and the frozen
trainer. It measures Standard (8 channels) and Nano (3 channels) separately, then
estimates 50, 100 and 200 epochs, including epoch validation. It also adds the times
for training both sizes sequentially. No audio interface or pedal is needed.

## MacBook Pro M2

Unzip the Mac package into a writable folder. Double-click **Install.command** once,
then **Benchmark Both.command**. The installer creates an isolated native Python
3.12 environment with PyTorch. It does not change an existing trainer installation.
You can run **Benchmark Standard.command** or **Benchmark Nano.command** separately.
If macOS prevents opening a launcher, run it from Terminal with `bash`, for example:

```sh
cd /path/to/NAM-Benchmark-Mac-M2
bash Install.command
bash 'Benchmark Both.command'
```

Use native Apple Silicon Terminal, connect the charger, disable Low Power Mode for
the run and close heavy applications. MPS is required by default; missing Apple GPU
support produces an error instead of silently timing CPU training.

## Runpod

Use a CUDA PyTorch pod with Python 3.11–3.13 and unzip the Runpod package on persistent
`/workspace` storage. The package does not create a pod or need account credentials.

```sh
cd /workspace/NAM-Benchmark-Runpod
bash setup.sh
.venv/bin/python benchmark.py
```

The setup reuses the pod's CUDA PyTorch. Missing CUDA fails visibly. Download the
report before stopping the pod; compute/storage/idle billing is controlled by your
pod settings, not this benchmark.

## Results and options

Results appear under `results/TIMESTAMP/`. **RESULTS.txt** is the readable summary;
**results.csv** includes planning ranges; **results.json** records hardware,
settings, measured batch timings and exact full-dataset batch/window counts.
Send **benchmark-results.zip** back for analysis. Each run has a new directory.
Successful results survive if the other model fails. Ctrl-C stops the active worker
and retains partial reports.

```sh
# Time just one model:
.venv/bin/python benchmark.py --models nano
# Measure longer, or use a different batch/window:
.venv/bin/python benchmark.py --steps 60 --val-steps 20 --batch 8 --ny 16384
# Optional CUDA experiments (not enabled by default):
.venv/bin/python benchmark.py --precision bf16-mixed --compile
# Optional cost calculation using your actual pod rate:
.venv/bin/python benchmark.py --hourly-rate YOUR_RATE
```

Both packages default to FP32 eager execution, batch 4 and the dataset's original
windows, for comparable measurements. The bundled corpus has 120 ordinary training
settings plus 120 attack captures, and 24 ordinary validation settings plus 24 attack
captures. Both architectures start fresh; no Standard-only warm-start model is
loaded into Nano. Default runs measure 20 training batches and 8 validation batches
after 3 warmups in each phase. Each architecture's measurement worker has a 20-minute
timeout, configurable with `--timeout`.

Training uses the real optimizer/loss and enabled silence anchors; validation is
measured separately. Full workload counts use the pinned dataset loader's actual
alignment, cropping and receptive-field rules, including partial capture batches.
Timing samples use representative recordings rather than an entire training epoch.
Unmeasured batch shapes are extrapolated and receive a wider planning margin.

**These are approximate training + validation times, not measured full-epoch times
or convergence promises.** Setup, checkpoint/NAM exports, final qualification,
storage and idle charges are excluded. Planning ranges are not statistical confidence
intervals; long runs may slow through heat, power limits or other workloads. No
playable model or checkpoint is exported. A finished model still needs all normal
audio/transient qualification and listening checks.
