# Validation and first Mac session

## Verified in this workspace

The workspace is Linux x86_64, not an Apple Silicon Mac. Validation uses Python 3.13.5 and a CPU-only PyTorch 2.14.1 wheel against the pinned trainer. Missing Linux Tk/PortAudio dependencies were extracted under `/tmp` for testing; the macOS installer instead uses the native Python installation and sounddevice's Mac distribution.

The test suite covers audio failures, settings leakage, delay/window semantics, Mac execution settings, preserved source configs, checksummed downloads, separate run folders and native Qt subprocess controls. A one-epoch test runs the real trainer and exports a parametric model. A second exercises the capture app's generated eight-channel architecture, spectral loss and silence anchors, also exporting a model. These are synthetic data, not pedal accuracy tests.

Final result: **18 tests passed**, exit code zero, in approximately 21 seconds. Two upstream deprecation warnings were emitted.

Native Qt screens were rendered offscreen at a desktop size and a compact window size. The training controls, setup guidance and process lifecycle were inspected. Screenshots under `screenshots/` show Linux Qt styling; they are not Mac screenshots. The GUI integration test runs in an isolated process like the launcher, avoiding Qt teardown interactions inside the PyTorch/pytest process. A prior combined-process test run had a teardown segmentation fault; the isolated GUI test and standalone render exit cleanly.

Shell launcher syntax is checked with `bash -n`. Both real excitation downloads passed their release SHA-256 checks; each is mono 48 kHz, with 38-second training and 7-second validation audio. The installer itself deliberately refuses Linux, so its macOS execution remains unverified here.

The suite emits a PyTorch Lightning deprecation warning about TreeSpec; this does not prevent export. Source configs are pinned to the reviewed trainer revision. Transitive package versions are not fully locked.

## Still needs your Mac and pedal

1. Run **Install.command**, then `.venv/bin/parametric doctor`. Confirm native arm64 Python, Tk, Qt, MPS availability and the connected UMC22. The doctor's MPS check exercises a convolution/backprop operation, not the complete model.
2. Follow the wiring guide and use **Route test**. Confirm channel mapping, microphone permission, DIRECT MONITOR off, reference headroom, timing detection and clean audio.
3. Capture a small project with distinct held-out settings and run one epoch on MPS. If any operation fails, retry CPU; retain the failing log and environment manifest.
4. Run a longer trial and check validation ESR and audio at unseen settings. Verify that the matching player loads the artifact, silence stays quiet and changing knobs behaves well.
5. Benchmark training time and peak memory on your actual Mac. Do not interpret synthetic CPU tests as evidence of pedal quality or a guaranteed Mac runtime.

Each run contains audio SHA-256 hashes and resolved source paths; it does not duplicate the WAVs. Preserve the project folder and captures when archiving a model. Later recaptures can change files referenced by an old run, and the hashes let you identify that change. `training.log` saves trainer stdout/stderr and epoch progress; Lightning also writes its own metrics/checkpoints.
