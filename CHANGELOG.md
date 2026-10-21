# Changelog

## 0.2.0 — 2026-10-21

- Replace the desktop shell with Console: Start, Gear, Connect, Record, Train and Listen, with dark/light appearance and bundled Geist fonts.
- Find the capture route using quiet clicks, and support sound cards exposed as separate input/output devices on macOS.
- Preserve saved device choices through disconnects and reject ambiguous cards and mismatched sample rates.
- Keep clipped takes pending until they are replaced and preserve calibrated recording levels during retries.
- Bind input calibration to recording hashes, fine-tune matching raw NAM models, and require reserved transient fidelity and recovery checks before saving protected playback models.
- Benchmark training settings and estimate Standard/Nano duration with portable Mac M2 and Runpod packages. Measured profiles are checked against the hardware, recordings, model and starting weights before reuse.
- Preserve all training controls and playback checks in the Console interface; fix cancellation races and validate effective input-reference gain before replacing calibration.

This is a source-based Apple Silicon macOS release. Unzip `parametric-mac.zip`, run `Install.command`, then open `Capture.command`. The installer fetches the pinned trainer and capture inputs; environments and audio are not included. Cloud source scripts are included; portable benchmark archives must be built separately with a dataset.

Physical Mac/UMC22 recording, native CoreAudio smoke validation, full MPS/CUDA training and listening remain unverified in this Linux review environment. FiLM protected saving remains unavailable. Projects without reserved transient recordings cannot save a newly qualified playback model; see `docs/transient-validation.md`.
