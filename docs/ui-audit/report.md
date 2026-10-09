# Parametric UI / UX audit

9 October 2026 · current native desktop app, plus a separate proposed workflow.

**Verdict: the capture/training foundation works, but the interface expects users to understand its internal structure. The biggest improvement is a guided session with a persistent next action.** This audit does not change the production app.

## Scope and evidence

Inspected `parametric_mac/gui.py` and the pinned upstream `nam/capture/gui/main.py`; rendered the actual Qt window at 1050×740 and requested 720×640; queried Qt accessibility metadata. The application runs here under Linux, not macOS. Existing screenshots were replaced by fresh audit captures in [evidence](evidence/). Evidence includes [native probe results](evidence/native-probe.json) and current Project, Capture, Train and Setup screens.

The Impeccable native audit's five dimensions are adapted to a **macOS desktop Qt app**. Phone touch-target, notch and Android Back rules are not applicable. Scores below are provisional source/render assessments, not a VoiceOver, dark-mode or Mac performance certification. The skill catalog does not recognize the project's truthful desktop platform value; that catalog mismatch does not make this application a website. Existing product/design records were retained.

## Audit health

| Dimension | Score | Main evidence |
| --- | ---: | --- |
| Accessibility | 2/4 | Standard named widgets exist; training-device accessible name exposes the selected value, and important state changes have no explicit announcement/focus handling |
| Performance | 2/4 | Real jobs use QProcess, but eager training imports delay the first visible window; local cold-ish launch measured 7.261 s |
| Appearance and theming | 3/4 | Native widget palette is the right foundation; upstream warning/helper text uses literal colors with no confirmed dark variants |
| Desktop platform conformance | 2/4 | Actual native Qt widgets, but seven equal tabs expose implementation structure; primary actions lack keyboard commands and context |
| Window adaptivity | 1/4 | A requested 720 px window expands to 778 px; dense horizontal actions/tables set the minimum instead of deliberate compact behavior |
| **Total** | **10/20** | **Acceptable foundation; significant UX work before a polished release** |

This is a native utility, not a ported webpage. Native controls are a strength; their arrangement does not yet guide the user's task. No P0 task-blocking issue was reproduced. **10 findings: 5 P1, 5 P2, 0 P3.**

## The whole user journey

| Moment | Current experience | Proposed experience |
| --- | --- | --- |
| First launch | Two project buttons above a large empty diagnostic log | Create/open a session with gear-specific setup and a clear continuation |
| Connect hardware | Routing form and passive instructions live in different tabs | Wiring diagram, fixed-level checklist and a route test together |
| Define controls | Editable six-column table with terms such as Avoid zero and Gain/Drive | One quality slider sets capture detail for all knobs; physical ranges and technical controls stay under Advanced |
| Understand recording effort | Initial LHS random captures, validation count, seed and corners | Total takes and playback estimate first; advanced sampling details behind disclosure |
| Record each setting | One small next-entry line, six peer controls, table and log | Large knob positions, one action, visible saved progress, short quality summary |
| Recover a bad take | QA flags and a modal error, followed by diagnostic text | The target remains; explain retry versus recalibration and preserve prior takes |
| Train | Device, epochs and batch size before a readable project summary | Readiness checks plus test/full presets, measured epoch progress and a deliberate fallback |
| Finish | Generic “Finished. Review the results below”; outputs folder | An exported candidate model with held-out results, listening checklist and player requirements |
| Return later | Project persists, but flow is distributed over tabs | Resume at the next pending take with the saved calibration and a route-verification reminder |

The proposed resume guidance, structured run review and embedded A/B panel need implementation. The existing recorder already persists takes; the mockups reorganize that capability rather than inventing automatic knob turning.

## Findings, ordered by impact

### P1 · A01: the app makes the user assemble the workflow

**Location:** [upstream tab construction](../../.upstream/nam/capture/gui/main.py:452), [companion tabs](../../parametric_mac/gui.py:72).

Seven tabs—Project, Knobs, Plan, Audio I/O, Capture, Train on Mac, Pedal setup—have equal visual priority. Hardware setup appears last, though it is a prerequisite. The first Project screen is mostly an empty log, rather than explaining the route to a first capture.

**Impact:** a new user has to learn where information lives, navigate backward for prerequisites and remember what is ready. There is no single session summary or explicit next stage.

**Recommendation:** a persistent five-stage sidebar: Connect, Plan, Capture, Train, Review. Keep project identity, hardware state, recording progress and the next actionable step visible. Pair hardware guidance with its routing controls. Recommended command: `$impeccable onboard`, then `$impeccable shape` for a production flow brief.

### P1 · A02: the physical knob task is visually subordinate

**Location:** [capture view](../../.upstream/nam/capture/gui/main.py:704), [capture action row](../../.upstream/nam/capture/gui/main.py:718).

The next knob setting is an ordinary QLabel above six peer actions. Capture next competes with recapture, Cancel, Check captures, Clear captures and sort; the take table/log occupy most of the view. “Clear captures” is confirmed before deletion—the problem is prominence, not a missing confirmation.

**Impact:** the user moves between the physical pedal and laptop repeatedly. Small target text and competing controls increase checking effort and make it easier to record the wrong position.

**Recommendation:** show large labeled positions, a clear current-take status and one primary Record action. Put queue/history alongside and destructive/project operations in a secondary location. Confirm that the physical controls are set before recording, then reset that confirmation for the next target. Keep the same target on failure. Recommended command: `$impeccable layout` and `$impeccable clarify`.

### P1 · A03: readiness is checked too late and training context is missing

**Location:** [training controls](../../parametric_mac/gui.py:31), [enabled actions](../../parametric_mac/gui.py:52), [no-project guard](../../parametric_mac/gui.py:104).

“Start training” and “Check captures” are enabled with no project; clicking them opens an informational modal. Apple GPU is offered before availability is established. Epochs and batch size lead the screen; project identity, take count and selected run do not. A route/capture readiness summary is not visible here.

**Impact:** buttons appear actionable when prerequisites are unmet. Beginners must understand training terminology and remember guidance about one versus 200 epochs. Choosing an unavailable backend produces a later error.

**Recommendation:** show unmet prerequisites inline. Use labeled setup-test/full-run presets; display the resolved device and explain an unavailable GPU before launch. A partial-capture run must be intentional; the current trainer can use completed entries, so do not silently turn partial runs into an unexplained hard prohibition. Recommended command: `$impeccable harden` and `$impeccable clarify`.

### P1 · A04: finishing and recovering are described instead of designed

**Location:** [job status](../../parametric_mac/gui.py:149), [folder action](../../parametric_mac/gui.py:188), [player note](../../parametric_mac/gui.py:68).

Both a successful check and a successful training job receive the same generic finished message. Failures direct users to a raw error log and suggest CPU without an action to retry. Open outputs leads to a folder; there is no in-app artifact or quality review. The compatible-player requirement is a passive footer note.

**Impact:** users can mistake export for demonstrated modeling quality, lose the latest run among folders, or struggle to recover without understanding framework errors.

**Recommendation:** distinguish check passed, test completed, model exported, stopped and failed. Provide the exact artifact/run, structured failure cause and recovery actions that preserve captures. Add a review stage showing held-out/worst-case metrics and a listening checklist; show the player requirement at export. An embedded A/B player is a future feature, not an existing capability. Recommended command: `$impeccable harden` and `$impeccable clarify`.

### P1 · A05: window resizing is governed by incidental widget minimums

**Location:** [training action row](../../parametric_mac/gui.py:51), [capture row](../../.upstream/nam/capture/gui/main.py:718), [probe](evidence/native-probe.json).

Requesting a 720×640 window produced a 778×640 window in all inspected tabs. The seven-tab strip and long peer-button rows constrain the whole application, including simple screens. No scroll-area or alternate compact arrangement is provided in the companion pages.

**Impact:** smaller screens, split-screen working and enlarged text cannot be accommodated deliberately. This is a verified Linux layout result; the exact Mac minimum still needs measurement.

**Recommendation:** separate primary/secondary actions, use compact sidebar/navigation behavior and scrollable content at small window heights. Define a supported minimum with actual layout testing; do not simply force a larger window. Recommended command: `$impeccable adapt`.

### P2 · A06: important changes do not have explicit accessible feedback

**Location:** [training device](../../parametric_mac/gui.py:32), [status label](../../parametric_mac/gui.py:60), [status updates](../../parametric_mac/gui.py:149).

Qt reports the device selector's accessible name as its current selected value (“Automatic · Apple GPU when available”), while epochs and batch size have semantic names. Status QLabel changes are not paired with explicit accessibility announcements or focus movement. Only the training log receives an explicit accessible name.

**Impact:** a screen-reader user may hear what is selected without the purpose of the control, and miss the state transition from running to failed/exported. This is a metadata/source finding; actual VoiceOver behavior was not tested.

**Recommendation:** set the device's stable accessible name to Training device, associate labels consistently, and send the appropriate native accessibility event for completion/failure. Announce the stage/next physical target without reading every log line. Verify keyboard and VoiceOver in the real Mac build. Recommended command: `$impeccable harden`.

### P2 · A07: desktop commands and task-specific cancellation are absent

**Location:** [training stop button](../../parametric_mac/gui.py:54), [start method](../../parametric_mac/gui.py:104), production GUI sources.

No QAction/menu commands or keyboard shortcuts for the primary operations are defined. During a dataset check the stop button still reads “Stop training”; it does not name the job running. Closing a running window tells the user to stop first instead of offering a clear task-specific close/stop decision.

**Impact:** repeated capture work is mouse-heavy; cancellation labels reduce confidence about what will happen. Do not interpret this as a keyboard trap—standard Qt navigation still exists.

**Recommendation:** expose native menu commands and discoverable shortcuts; provide task-specific Stop check / Stop training text and explain saved-state outcomes. Shortcuts must avoid firing while editing a field. Recommended command: `$impeccable harden` and `$impeccable clarify`.

### P2 · A08: background work disables every other surface

**Location:** [tab disabling](../../parametric_mac/gui.py:129).

Every non-training tab, including the read-only hardware guide, is disabled during checking/training. This protects mutable source paths but blocks unrelated reference information too.

**Impact:** a long run locks the user into a diagnostic screen even when they only want to inspect the plan or setup. The behavior is safe but broader than necessary.

**Recommendation:** freeze the run's project/input state and restrict mutations, while allowing read-only inspection of other stages. Keep a persistent background-job status. The mockup demonstrates this proposed behavior; production needs a careful state/snapshot contract. Recommended command: `$impeccable harden`.

### P2 · A09: slow first-frame work has no explanation

**Location:** [eager upstream import](../../parametric_mac/gui.py:10), upstream `nam/__init__.py`, [measured launch](evidence/native-probe.json).

Importing the native window also imports NAM's training chain before showing the app. One local Linux launch measured 7.261 seconds to first processed frame. This includes module imports and initial device refresh; it is not a controlled Mac benchmark. Actual training/checks are correctly separated with QProcess.

**Impact:** a new user can think the launcher did not work and start it again, while the UI is still loading.

**Recommendation:** load the minimum capture shell first, or provide honest startup feedback while the necessary imports/driver enumeration happen. Measure on the user's Mac before setting a performance target. Recommended command: `$impeccable optimize`.

### P2 · A10: warning text is outside the native palette contract

**Location:** upstream [warning colors](../../.upstream/nam/capture/gui/main.py:650), [helper text](../../.upstream/nam/capture/gui/main.py:664).

Audio warnings use `#b36b00` and routing help uses `#6b6b6b` through setStyleSheet, rather than palette-aware roles. Most other widgets inherit the platform palette. Mac light/dark and increased-contrast rendering were not available here; do not claim a verified contrast failure from source alone.

**Impact:** these messages can drift from the rest of the app's appearance and need verification when the background/system appearance changes.

**Recommendation:** use semantic palette roles or theme-aware warning colors. Test light, dark and increased-contrast settings on Mac, including selected/disabled states. Recommended command: `$impeccable colorize`, then `$impeccable audit`.

## What to preserve

- The actual recorder plans and persists captures, tracks timing and QA, and supports recaptures. The redesign should make these capabilities easier to use.
- Standard Qt controls provide useful native semantics and focus behavior; do not replace them with inaccessible painted widgets for the sake of screenshots.
- QProcess keeps training/checking separate from UI rendering. Preserve this separation.
- The log is capped at 10,000 blocks; source captures, run configs and checkpoints are preserved.
- Dangerous clearing has an explicit confirmation and keeps original raw recordings. Avoid reporting a nonexistent unguarded-delete bug.
- The player compatibility limitation is stated honestly. Make it more actionable rather than removing it.

## Proposed mockups and implementation order

[Open the full overview](../mockups/overview.html) or [the clickable prototype](../mockups/index.html). Five desktop screens and recovery states live in [mockup screenshots](../mockups/screenshots/). This is a UX proposal around the existing native engine; no audio/training backend runs in the browser artifact.

1. **P1 — `$impeccable onboard` / `$impeccable shape`:** shared session summary and five-stage task structure.
2. **P1 — `$impeccable layout` / `$impeccable clarify`:** physical knob targets, the recording action and plan commitment.
3. **P1 — `$impeccable harden`:** prerequisites, structured job states, recovery and export/review handoff.
4. **P1/P2 — `$impeccable adapt` / `$impeccable harden`:** compact windows, native accessibility and desktop commands.
5. **P2 — `$impeccable optimize` / `$impeccable colorize`:** launch work and appearance verification.
6. **Final — `$impeccable polish`:** refine the implemented flow, then re-run `$impeccable audit` on Mac.

These can be implemented individually or together; the current request delivers the audit and mockups, not those production changes.

## Verification boundaries

T3 preview status and open both returned an explicit unsupported/no-host error. A local headless Chromium browser inspected the separate HTML mockup after that failure. The actual app was inspected with native Qt probes and captures, not browser accessibility rules. Mockup interactions and overflow checks are recorded in [mockup verification](evidence/mockup-verification.json).

The initial mockup detector found small-text warnings, a titlebar-padding heuristic and an Inter-font warning. The small-text findings are relevant and are corrected in the mockup refinement. Native utility typography makes the categorical font warning a context judgment rather than a product-specific defect. Titlebar padding is checked against actual rendered centering. This detector does not audit Python/Qt or certify the actual Mac app.

The final prototype passed **20 screen/viewport checks and 19 interaction checks**, with no JavaScript errors. Verified interactions include cancelled and accepted takes, unchanged-target failure, separate recalibration, background training, one-epoch success, CPU recovery, configuration/focus continuity, review-state continuity, labeled handoff download and offline file access. The simplified Plan adds all five automatic quality levels, default Good, keyboard/pointer use, custom overrides and locked-plan recovery. Advanced controls remain available in a collapsed disclosure; their compact table retains an internal scroller. These browser checks verify the mockups, not native Mac behavior.

The original independent Impeccable finish reviewer scored seven requested fixes and one compact-table regression resolved, with disposition **ship at the scope of those fixes**. See [finish review](finish-review.md); this is not a whole-product certification. A fresh [Plan quality review](plan-quality-review.md) approved the subsequent single-slider refinement at its own scope. Screenshot origin metadata is embedded in all 29 prototype captures.

Final hook triage: removed the progress bar's width transition, preserving the same progress values and static appearance. A targeted browser check confirmed 18/40 remains 45%, transition duration is zero, and no JavaScript errors occur. The intentional Inter choice is suppressed only for `overused-font=Inter` in `docs/mockups/styles.css`, with the native utility rationale recorded through the hook's value-ignore command. Neither rule is disabled globally. No hook findings were left standing from this triage.

Remaining device checks: actual UMC22/CoreAudio routing, microphone permission behavior, MPS training, keyboard commands after implementation, VoiceOver announcements, Mac appearance and supported window/font sizes. No real pedal data or quality claims are supplied by the mockups.
