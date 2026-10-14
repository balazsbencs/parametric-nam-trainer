# Product
<!-- impeccable:product-schema 1 -->

## Platform
macOS desktop · Python/Qt

## Stack
Python, PySide6 and the public parametric NAM fork at a pinned revision. A source-based desktop app with command launchers and a local virtual environment.

## Users
Pedal and amp owners who want to capture knobs and named switches and train a controllable model locally on an Apple Silicon Mac. The initial user's interface is a UMC22; recording requires a reamp box, cables and a powered pedal.

## Product Purpose
Guide the physical task and local model workflow through Connect, Plan, Capture, Train and Review, with practical hardware instructions and recoverable saved projects.

## Capabilities and Constraints
The native app implements the approved five-stage workflow. A five-stop capture-coverage slider defaults to Good, generates real reachable counts and estimates recording effort; Connect has an editable control list, range / position editors, Add knob / Add switch / Remove and pedal / amp starters. Advanced supports manual sampling settings. It models 1–24 total controls, including named switches, with at least one knob. Every switch combination receives training and held-out settings. Projects are bounded to 32 combinations and 5,000 recordings; more than eight knobs use axis boundary sweeps. Unmodeled controls stay fixed. Coverage is not a measured sound-quality score. Presets preserve physical ranges; grid capacity bounds small plans.

Recording uses the existing native capture engine and QA. Physical dial diagrams and confirmation guide manual knob positioning. Accepted takes lock the plan, including after captures are cleared; changing settings requires a separate project in an empty directory. Existing source recordings are retained. Connection readiness must be checked again after reopening.

Checking and training run in separate processes. Mutable inputs disable during jobs while navigation remains available. Runs retain configs, audio hashes, logged validation metrics, status and actual model exports. Automatic execution selects MPS when available, otherwise CPU; stop and CPU retry support recovery. Review saves listening status per run and copies the exported model. A compatible parametric player is required; there is no built-in A/B player. Last logged ESR describes the last epoch, not a fresh evaluation of the exported checkpoint.

The Mac README and app are implemented; this is not a signed standalone installer or a new plugin runtime. The initial protocol targets suitable overdrive, distortion and EQ pedals, with optional modeled switches. Amp layouts are supported, with load-box routing guidance; actual amp capture remains unverified. Delay and modulation are outside that protocol. The trainer is pinned; transitive dependencies are not fully locked.

## Evidence on Hand
Public trainer/player source, inspected at the revision pinned in `parametric_mac/__init__.py`; the user's linked ParametricOD article; approved synthetic HTML workflow and Plan proposals. Current Linux Qt offscreen evidence includes twenty desktop / compact images. The full suite passed 57 tests in 74.45 seconds, with 10 upstream deprecation warnings, including the existing A2/FiLM/dual-export workflows. A final targeted GUI test passed in 30.94 seconds after job-state corrections. UI assets were verified in a built wheel.

The user’s renewed feedback that the app looked dated supersedes earlier native visual verdicts. The current refinement matches the approved Inter lettering, flat control chrome, icon route rows, segmented coverage geometry, physical targets and training presets. It preserves all current capture and architecture behavior. The fresh reviewer’s final disposition is ship: disabled presets, automatic error-log disclosure and persistence documentation are resolved. No new design-detector suppression was added.

No physical hardware recording was performed for those screenshots. Mac installation, CoreAudio recording, full MPS training, real-pedal sound quality and Mac VoiceOver remain unverified. These limits do not change the intended macOS desktop platform.
