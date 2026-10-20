# Validation and first Mac session

## Find my connection, Phase 2 (October 20, 2026)

The full suite passed on this Mac: **256 tests**, exit code zero, with 20 upstream deprecation warnings. New tests: `tests/test_find_route.py` (click detection, loopback test, route choice), `tests/test_find_scan.py` (one output at a time on a synthetic rig, several routes, cancel, dropout, large devices) and `tests/test_ui_find.py` (the Connect button, every result state, cancel while it runs, device change). Line coverage: `find_route.py` 96%, `find_scan.py` 100% (the sounddevice call is excluded; it needs a sound card); the Connect code runs only in GUI subprocess tests, so it has no coverage number.

Find plays upstream's click preamble at **−20 dBFS** (`FIND_AMPLITUDE = 0.1`), below the route test level. With synthetic returns through a bright path (a one-pole low-pass at 8 kHz), detection works down to about −60 dBFS over a −90 dBFS noise floor and −50 dBFS over −80 dBFS, for round trips up to 20,000 samples; the clicks must stand about 30 dB above the noise. An inverted return (gain −0.03) with a DC offset of up to −50 dBFS is found at a 300-sample delay. Darker paths: when the first try fails, detection tries the return doubled, which at −90 dBFS noise finds a 3 kHz path at −40 dB gain and an 800 Hz path at −30 dB, as −14 dBFS clicks would. A 1.5 kHz path at −40 dB is found only from −7 dBFS clicks, and an 800 Hz path at −40 dB not reliably at any tested level. Find stays at −20 dBFS and, when nothing comes back and recording has not started, asks the user to turn a quiet or dark gear up. A single pop is not a return: every click must arrive. A return is a digital loopback when, in a ±16-sample window around each click and after delay alignment and gain matching, the residual is **−80 dB** or lower: this catches exact, 24-bit dithered and −120 dBFS-noise copies, but not a 16-bit dithered copy. Not yet verified on real sound cards.

## Console redesign (October 19, 2026)

The full suite passed on this Mac: **122 tests**, exit code zero, with 20 upstream deprecation warnings. New tests cover the theme tokens and WCAG AA contrast in both modes, the style sheet and appearance switch, the shell, and every page (Start, Gear, Connect, Record, Train, Listen), including the six Review Focus cases of the [Phase 1 plan](superpowers/plans/2026-10-17-ux-redesign-phase1.md). Line coverage of the pure modules: `recent.py` 97%, `ui/copy.py` 97%, `ui/tokens.py` 98%, `workflow.py` 85%. The user approved the light theme from offscreen screenshots. Not yet verified: native macOS menus and popups in each theme, real CoreAudio recording, and full MPS training with the new screens.

## uv installer on Apple Silicon (October 14, 2026)

The installer completed on native arm64 macOS 25.6 with system Python 3.15.0. uv 0.11.16 created `.venv` using managed Python 3.12.13 with Tk 9.0 and installed the pinned trainer, PyTorch 2.14.1 and PySide6 6.12.0. Both excitation downloads passed their SHA-256 checks. Doctor found all required modules, enumerated CoreAudio devices and passed an actual MPS convolution/backprop check.

The completed installer was also run with `PATH=/usr/bin:/bin`, verifying uv discovery outside `PATH` and reuse of the existing environment. Isolated checks confirmed that an existing Python 3.15 environment and a broken `.venv` symlink are rejected without replacing them; an explicit Python 3.15 override is rejected before environment creation. The version guard remains active under `PYTHONOPTIMIZE=1`. The source ZIP includes `.python-version` and executable launchers, and excludes local environments and the upstream checkout.

The complete existing suite passed on this Mac: **57 tests passed in 70.14 seconds**. This includes real synthetic CPU training/export and the isolated offscreen Qt workflow test. The 20 warnings comprise ten notices that these CPU tests do not use the available GPU and ten upstream Lightning TreeSpec deprecations.

An actual uv resolution probe for Python 3.15 on this Mac failed because PyTorch has no compatible `cp315` wheel. The app runtime therefore remains Python 3.11–3.13, with 3.12 selected by default. Installation works independently of the system Python version. No UMC22 recording or full MPS model training was performed during installer verification. uv bootstrap was not needed because uv was already installed; transitive dependency versions are still not fully locked.

## Previous Linux verification

Earlier validation used Linux x86_64, Python 3.13.5 and a CPU-only PyTorch 2.14.1 wheel against the pinned trainer. Missing Linux Tk/PortAudio dependencies were extracted under `/tmp` for testing; the macOS installer now uses uv-managed Python with Tk and sounddevice's Mac distribution.

The test suite covers audio failures, settings leakage, delay/window semantics, Mac execution settings, preserved source configs, checksummed downloads, separate run folders and native Qt subprocess controls. A one-epoch test runs the real trainer and exports a parametric model. A second exercises the capture app's generated eight-channel architecture, spectral loss and silence anchors, also exporting a model. A third trains a switch-conditioned native manifest and verifies named switch metadata in its exported model. These are synthetic data, not pedal or amp accuracy tests.

Final result: **57 tests passed**, exit code zero, in **74.45 seconds**. Ten upstream Lightning deprecation warnings were emitted. After the final UI state corrections, the targeted native integration test passed in **30.94 seconds**. These warnings do not prevent export.

The native redesign adds realizable quality presets for one, two and four knobs, preserved physical ranges, unseen-setting uniqueness, one-knob grid saturation and fine-step limits. Native subprocess checks cover disabled empty actions, navigation during a real check job, verified input copying, custom/preset restoration, plan locking and reopening, mismatched-target refusal, route-readiness invalidation, per-run listening status and overwrite protection. The real trainer saves finite last-epoch validation measurements in `metrics.json`.

The Console redesign (2026-10-17) is rendered offscreen by `scripts/render_native.py` in dark and light at **1140×900** and **800×680**: Start (empty and with recent projects), Gear, Connect (not ready and ready), Record (choose, loop, clipped take), Train (before, running, failed) and Listen. The 48 images are in [`docs/screenshots/native/`](screenshots/native/). The script builds a synthetic demo project; no audio is recorded and no model is trained for these images. Each page and state also has an automated Qt test (`tests/test_ui_*.py`, `tests/test_shell.py`).

Shell launcher syntax is checked with `bash -n`. Both real excitation downloads passed their release SHA-256 checks; each is mono 48 kHz, with 38-second training and 7-second validation audio. The installer itself deliberately refuses Linux; macOS execution is covered by the separate uv installer verification above.

The suite emits a PyTorch Lightning deprecation warning about TreeSpec; this does not prevent export. Source configs are pinned to the reviewed trainer revision. Transitive package versions are not fully locked.

## Ardor interoperability and A2 profiles

The compatibility pass runs the real CPU trainer for A2 Standard (8 channels) and A2 Nano (3 channels), then checks their actual `ConcatWaveNet` 1.0.0 exports. Both preserve the 23-layer A2 kernel/dilation pattern. Export tests also verify amp/pedal identity and unchanged weights, config and calibration metadata. The full suite passed **50 tests**, with five upstream Lightning deprecation warnings, in **58.90 seconds** on Linux. Native GUI checks additionally cover persisted architecture choices, disabled selectors during jobs and readable Train layouts at desktop and compact widths.

`scripts/export-ardor-reference.py` reloads exported weights into the pinned Python runtime and generates audio references, including defaults, extrema and switch positions. Ardor's `pedal-parametric-trainer-compat-smoke` compares those references with its C++ runtime at 13- and 64-frame buffer sizes. The shared fixture includes trained Standard, Nano and switch models, plus an initialized 24-control Nano model for the maximum-control contract. Ardor's asset-store tests upload the exact exports and verify their controls and amp/pedal categories. This proves format and inference interoperability; the initialized fixture and one-epoch synthetic training do not establish capture quality.

Preflight now requires 48 kHz recordings and at most 24 controls to match Ardor. The GUI Train page was inspected with Linux Qt offscreen renders at 1140×900 and 800×680. Mac, MPS and physical hardware qualification remain outstanding.

## Combined Standard + Nano export

The full suite now passes **52 tests** (seven upstream Lightning deprecation warnings, 81.90 seconds). Combined-mode tests run one actual CPU epoch for each size, retain typed switch controls, verify that the final container embeds the exact individual exports, and preserve per-tier validation metrics. An interruption test confirms that stopping the second tier retains the first without publishing a combined file. Packaging rejects inconsistent controls, gear types and input calibration. Dry-run preparation snapshots both models and their common data/learning settings.

Ardor's regression test compares 14 additional Python audio cases with both children of the combined file at 13- and 64-frame buffers. It also selects Standard and Nano after loading the processor, preserving control values and independent loudness normalization. Upload/list/rename produces one asset; the native drawer retains the size choice and switch in the preset. Train and Review were inspected at 1140×900 and 800×680 using the native GUI test project; its example Review metrics are UI fixtures. CPU training and exported-model inference are verified separately with real synthetic training runs. Mac hardware qualification remains outstanding.

## FiLM training and export

The final full trainer suite passed **57 tests** with ten upstream Lightning deprecation warnings in **130.20 seconds** on Linux. This includes both combined-mode interruption cases (concat and FiLM), real concat training, three real FiLM training runs, native GUI checks, and the capture configuration export action. FiLM runs use joint target normalization and the existing checkpoint/export workflow. Tests cover gradients through every modulation layer and the chunked DC filter, export/reload with physical ranges, output-scale compensation, 16-control limits, switch rejection, preserved individual calibration, and combined normalized playback.

Ardor's final compatibility smoke passed in **105.44 seconds**, including 18 FiLM audio cases at 13- and 64-frame buffer sizes, both bundled tiers, switching sizes with controls retained, native preset restoration, and malformed export rejection. Maximum absolute Python/C++ error across the 36 FiLM comparisons was **2.36183e-6**. The actual combined pedal and individual amp exports also pass Go upload/rename/list checks. Fixtures and reproduction details are in Ardor's `tests/fixtures/parametric-trainer-film.md`. No Gene Ko player binary was run; interoperability here is verified against Ardor's supported Gene Ko format and C++ kernels.

Train and Review were inspected at 1140×900 and 800×680. Review uses actual one-epoch synthetic FiLM metrics, copied into a native UI test project; its high ESR values are not presented as finished gear models. The advanced capture export action has a format-neutral label and writes the selected FiLM configuration. UI inspection was performed in-thread because the user prohibits subagents. Disposition: **ship**; changed controls and copy remain readable, native scrolling and pinned actions are preserved, and no material UI findings remain. The design detector reported two existing advisory values (32px and `#25664d`), both outside this change. Mac/CoreAudio, MPS, physical-gear accuracy, and Raspberry Pi performance still require hardware qualification.

## Still needs your Mac and pedal

1. Run **Install.command**, then `.venv/bin/parametric doctor`. Confirm native arm64 Python, Tk, Qt, MPS availability and the connected UMC22. The doctor's MPS check exercises a convolution/backprop operation, not the complete model.
2. Follow the wiring guide and use **Test connection**. Confirm channel mapping, microphone permission, DIRECT MONITOR off, reference headroom, timing detection and clean audio.
3. Capture a small project with distinct held-out settings and run one epoch on MPS. If any operation fails, retry CPU; retain the failing log and environment manifest.
4. Run a longer trial and check validation ESR and audio at unseen settings. Verify that the matching player loads the artifact, silence stays quiet and changing knobs behaves well.
5. Benchmark training time and peak memory on your actual Mac. Do not interpret synthetic CPU tests as evidence of pedal quality or a guaranteed Mac runtime.

Each run contains audio SHA-256 hashes and resolved source paths; it does not duplicate the WAVs. Preserve the project folder and captures when archiving a model. Later recaptures can change files referenced by an old run, and the hashes let you identify that change. `training.log` saves trainer stdout/stderr and epoch progress; Lightning also writes its own metrics/checkpoints.

The quality slider estimates recording effort from the actual plan after boundary deduplication and, when available, the project’s input durations. Defaults add ten seconds per setting for manual knob changes. The one-knob grid can saturate; higher presets keep the held-out allocation bounded so they do not consume increasingly more training settings. Presets express coverage, not measured listening quality.


The control-editor pass adds native Add knob / Add switch / Remove, range and named-position dialogs, editable pedal / amp starters and persisted drafts. Tests cover all switch combinations in both splits, typed save/reload/config generation, switch-conditioned CPU training/export, 24-control bounded planning, combination limits and safe shortened filenames for long or path-like display names. Native subprocess tests exercise the editor, switch-position dialog, amp selection, persisted drafts and locked manifests. Geometry checks verify that compact pages need no horizontal scrolling, editor fields retain readable height, dials receive their full height, hints do not overlap them, queue targets match capture order and stacked reference content follows the work area naturally.

The Mac field-sizing problem in the user's screenshot was traced to platform defaults: QMacStyle normally keeps fields at their size hints and centers forms. The app explicitly enables field growth, left alignment and long-row wrapping. It also uses an explicit light palette and status / progress backgrounds. These policies are asserted in the GUI test; an actual Mac screenshot is still needed to verify the complete native appearance. [Qt form-layout documentation](https://doc.qt.io/qt-6/qformlayout.html).


The October 14 visual refinement bundles the approved Inter face as static Regular, Medium and SemiBold instances, with no runtime font download or fontTools dependency. Packaging checks confirm font, license and vector assets are present in the built wheel. Qt controls retain their input and accessibility semantics while their chrome, field grouping, disclosure arrows, physical diagrams and training presets match the mockups. Profile selection still changes the original duration combo, including actual epoch counts, and cannot deselect the active preset. Native tests now cover a real failed check job opening the error disclosure in its checked state and the first click collapsing it. Disabled profile styling and failure disclosure geometry were reviewed in actual rendered states.


## Split interfaces on Connect — 2026-10-20

Implemented on `plan/split-interfaces` (PR #7), stacked on Find my connection (PR #6).
The full suite passed **282 tests**, with **1 macOS-only smoke test skipped** and ten upstream
Lightning deprecation warnings, in **498.73 seconds** on Linux/Python 3.13/PySide6 6.12.
`capture_cards.py` and the testable part of `device_rates.py` both have **100% coverage**;
only the native CoreAudio adapter calls are excluded.
The pure device-list tests cover duplex and split cards, ambiguous names, separate host APIs,
Bluetooth exclusion, stable ordering and upstream recording resolving each direction by name.
Offscreen GUI tests cover saving the selected card, a missing or ambiguous saved card without
rewriting the project, restoration on refresh, per-half rate blocks, and Find resolving changed
indexes before a scan. The optional timing loopback stays off for new projects even before a
card has been selected. No upstream files or runtime dependencies changed.

CoreAudio's stream-scope walk and transport decoding have an injected-backend test; its native
smoke test is skipped on Linux. Native calls still need macOS qualification. The Linux test
runtime required Tk libraries extracted under `/tmp` because the pinned trainer imports Tk.
The bundled-font assertion accepts Linux's additional weight-family aliases while still checking
the expected family and actual regular/medium/semibold styles.

`render_native.py --connect-only` produced 16 offscreen screenshots, in dark and light at
1140×900 and 800×680. They include the selected split card and a simulated Find result of
Output 1 → Input 1. The rate label reserves its text width; the compact mismatched-rate state
has a geometry assertion. `connect-evidence.json` records that no audio was recorded and no
model was trained for these screenshots. The design detector reported no findings on the
changed Connect modules.

**Hardware check pending:** on the Mac, plug in the UMC22 without an Aggregate Device. Confirm
**USB Audio CODEC (Core Audio) · 2 in · 2 out**, Find returning **Output 1 → Input 1**, a passed
**Check level**, and one recorded take without dropouts. Record the outcome here; automated
and offscreen tests do not establish those hardware results.
