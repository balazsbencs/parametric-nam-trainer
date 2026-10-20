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
The native app implements the approved Console redesign (2026-10-17): a Start page with recent projects, then Gear, Connect, Record, Train and Listen, in dark and light with a Match macOS / Light / Dark switch. Gear holds the editable control tiles (Add knob / Add switch / ×, range and position editors, Pedal / Amp starters) and creates the project in `~/Music/Parametric/<name>` or a chosen empty folder. Connect has three stages: wiring confirmation, Find the connection (the sound card, a sample-rate block, and **Find my connection**, which plays quiet clicks on one output at a time and sets the channels; manual channels are under Expert settings), and a loudest-level check. Record offers three detail levels (Fast, Good, Max) with Decent and Overkill under Expert settings; counts come from the real planner. It models 1–24 total controls, including named switches, with at least one knob. Every switch combination receives training and held-out settings. Projects are bounded to 32 combinations and 5,000 recordings; more than eight knobs use axis boundary sweeps. Unmodeled controls stay fixed. Coverage is not a measured sound-quality score. Presets preserve physical ranges; grid capacity bounds small plans.

Recording uses the existing native capture engine and QA. Record shows the positions to set, marks controls that changed since the last take, and records only the setting it shows (button or Space). A clipped take must be recorded again; the app never suggests changing levels, and a new capture is the way to set a lower level. Accepted takes lock the plan; before the first take the level and the controls can still change. Existing source recordings are retained. Connection readiness must be checked again after reopening.

Checking and training run in separate processes; Start training checks first and then trains. Inputs that change a job are disabled while it runs; navigation remains available. Runs retain configs, audio hashes, logged validation metrics, status and actual model exports. Automatic execution selects MPS when available, otherwise CPU; Stop and Try again on CPU support recovery. Listen shows the newest run with a model, saves a two-item listening checklist per run and copies the exported model. A compatible parametric player is required; there is no built-in A/B player yet. Last logged ESR describes the last epoch, not a fresh evaluation of the exported checkpoint, and the held-out settings also select the best checkpoint.

The Mac README and app are implemented; this is not a signed standalone installer or a new plugin runtime. The initial protocol targets suitable overdrive, distortion and EQ pedals, with optional modeled switches. Amp layouts are supported, with load-box routing guidance; actual amp capture remains unverified. Delay and modulation are outside that protocol. The trainer is pinned; transitive dependencies are not fully locked.

## Evidence on Hand
Public trainer/player source, inspected at the revision pinned in `parametric_mac/__init__.py`; the user's linked ParametricOD article; the approved Console redesign spec and mockups in `docs/superpowers/specs/` and `docs/design/2026-10-17-ux-redesign/`. Offscreen Qt renders of every page and main state, in dark and light at 1140×900 and 800×680, are in `docs/screenshots/native/`; the user approved the light theme from them on 2026-10-19. The automated suite covers the tokens and contrast, the style sheet, the shell, every page and the existing A2/FiLM/dual-export workflows.

No physical hardware recording was performed for those screenshots. Mac installation, CoreAudio recording, full MPS training, real-pedal sound quality and Mac VoiceOver remain unverified. These limits do not change the intended macOS desktop platform.
