# Desktop playback export — October 19, 2026

The desktop trainer now separates raw training exports from qualified playback
models. The original weights and optimizer checkpoints are retained.

## Workflow

In Train, set Playback input attenuation and confirm the mapping. Use 0 dB for
identical digital input domains; use 12 dB for the prepared Bassman teacher dataset.
The app does not guess a mapping from model name or audio peaks. It persists this
setting in workflow.json and snapshots it per run.

After training, qualification runs automatically. For existing runs, select the
run in Review and click Qualify saved run after confirming its input mapping.
CLI: `parametric qualify /path/to/run --input-pad-db 12`.

Review saves only a hash-matching `playback/model_playback.nam` with a passing
qualification report. It does not copy raw/checkpoint NAM files. Modified playback
files disable Save model. The save boundary validates the exact bytes again,
including after the Save dialog, and replaces the destination atomically.

The protected concat transfer is the original model at the chosen input pad,
clipped to +/-0.8 with a standard NAM Hardtanh head. Loudness is recomputed for
this transfer, with a normalization floor preventing output amplification above
-1 dBFS. Controls retain their original scaling. Normalization and clipping do
not establish faithful tone at inputs outside the recorded distribution.

Checks use the run's own controls, audio hashes, window/delay settings and held-out
recordings. Small declared control grids are exhaustive; larger or unquantized
spaces use deterministic sampling plus held-out settings. Reports state the
coverage. Mean held-out ESR must be <=0.10; every capture must be <=0.25. Standard
and Nano must both pass before the protected combined file is published.

## Evidence

- Full pytest suite on current main plus this patch: 64 tests passed in 81.01 s.
  Upstream PyTorch deprecation warnings remain. Linux uses extracted Tk libraries
  because this host lacks system Tk.
- Known teacher tests cover calibrated transfer, reload, fidelity rejection, changed
  recordings, unknown calibration, source tampering, atomic save protection and
  combined-tier qualification. Non-Bassman control names and a bounded 24-control
  sampling case are covered.
- The actual supplied Bassman Standard was qualified through the desktop CLI:
  mean ESR 0.03395467, worst 0.12882319,
  all 24 recordings and 152 stress settings.
- Native Qt offscreen inspection: Train and qualified Review at 1140x840 and
  800x800; tampered-model state disables saving. Existing UI regression passes.
- Logs, screenshots and qualification JSON are in `dist/desktop-playback-validation/`.

## Limits and installation

Protection currently supports single-array concat exports without an existing
post-stack head, FiLM routes, grouped input mixers or analog input-level metadata.
FiLM training outputs are retained, but protected FiLM Save is blocked with an
explanation. Mac/CoreAudio/MPS hardware, listening and live-pedal operation were
not tested as part of this desktop code change.

Install through the repository's existing Install.command, then launch Train.command.
The installer uses the project's managed Python and fetches the pinned upstream
trainer. Open the existing project, confirm its input mapping, and qualify a saved
run. Retraining is unnecessary for that recovery operation.
