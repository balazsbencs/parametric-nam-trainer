# Design handoff: separate Parametric UX proposal

9 October 2026 · Impeccable documenter finish handoff.

The deliverable is the [five-stage interaction proposal](../mockups/index.html), [full overview](../mockups/overview.html) and [audit](report.md). It demonstrates a clearer physical capture task and recovery flow around the existing native engine. It is a code-led proposal, with synthetic data throughout, rather than an approved replacement production visual world. No approved raster composition or QUALITY BAR was supplied. The [separate finish review](finish-review.md) records all seven material fixes and the compact Plan regression resolved, with disposition `ship` at that limited artifact scope.

[Root PRODUCT.md](../../PRODUCT.md) and [root DESIGN.md](../../DESIGN.md) remain incumbent production truth. They were read and kept untouched by this handoff. Extracted browser tokens and visual guidance live only in [docs/mockups/DESIGN.md](../mockups/DESIGN.md); they are descriptive of the proposal and have no authority over production widgets. No global Impeccable sidecar was created or refreshed.

## Proposal compared with production

| Concern | Incumbent production | Proposed artifact and implementation boundary |
| --- | --- | --- |
| Platform | macOS desktop, Python/PySide6 and pinned upstream NAM capture app | HTML is a local review artifact. It does not change the runtime stack or host real audio/training. |
| Visual authority | Standard Qt widgets, system typography, incumbent native tabs | Light neutral surfaces, blue action, local Inter and approximate desktop framing communicate the proposal. Native styling must be translated and verified on Mac. |
| Workflow | Project, Knobs, Plan, Audio I/O, Capture, Train on Mac and Pedal setup tabs | Five stages bring setup, targets, readiness and review together. Production needs an explicit shared session-state contract. |
| Physical capture | Existing planner/recorder persists captures and supports QA/recapture | Large dial instructions make the real knob task dominant. User confirmation gates Record; no automatic physical control is proposed. |
| Continuity | Real project files and run folders | Example state survives re-render and stage navigation in browser memory. Reload persistence and structured resume are production work. |
| Recovery | Real processes, capped log and preserved capture/run files | Retry retains target; changed gain starts a separate calibration example; CPU retry retains captures. The browser preserves illustrative counters, not actual files or checkpoint contents. |
| Background jobs | QProcess separates checking/training from rendering; other tabs currently disabled | Simulated training survives stage navigation. Production must snapshot immutable inputs before allowing inspection of other surfaces. |
| Training result | Actual trainer exports model/metrics | A setup test is distinguished from candidate export. Review, held-out presentation and A/B UI are proposed work; no audio is played and no weights are downloaded. |
| Compact layout | Native minimum and appearance need Mac measurement | Stacked HTML at 390px supports artifact inspection. Plan uses a 600px internal table with a 160px first column; no page overflow does not mean no internal scrolling. |

## Preserved constraints

- The UMC22 is the user's interface; a reamp box is missing. The proposal exposes that setup requirement and does not silently treat a line send as a calibrated instrument-level route.
- Pedal identity, actual knob count, Mac memory and hardware choices remain undecided. Drive/Tone with fixed Level are illustrative. Continuous controls are modeled; switches remain fixed per project.
- Keep calibration repeatable across a real session. A changed gain setting must be handled deliberately rather than mixed with earlier captures without explanation.
- Preserve the existing capture planner/recorder, standard native widget semantics, separate training/check processes, reproducible run folders, retained raw captures and the capped diagnostic log.
- Keep the compatible parametric-player requirement visible. Export alone does not establish quality, and stationary-knob data does not prove smooth automation.

## Evidence checked

Read the incumbent product/design records, proposal [stylesheet](../mockups/styles.css), [state implementation](../mockups/app.js), [overview](../mockups/overview.html), [prototype entry](../mockups/index.html), [README](../mockups/README.md), [mockup-verification.json](evidence/mockup-verification.json) and the finish review. Visually inspected the five desktop screenshots and five 390px screenshots in [screenshots](../mockups/screenshots/). Rechecked the refreshed compact Plan screenshot after its final readability adjustment: Drive/Tone descriptions remain readable, Minimum/Maximum are initially visible, and further columns stay within the table's internal horizontal scroller.

The supplied verification records all five stages at 1440, 960, 720 and 390px with no page horizontal overflow, and no console errors. Its interaction checks cover setup gating, cancellation, accepted/clipped takes, routing/range continuity, new-calibration separation, background simulated training, test/full outcomes, past-only epoch plots, review checklist/A/B continuity, CPU recovery, clearly labeled JSON handoff and opening directly through a file URL. This documenter pass inspected that evidence and source; it does not claim to have rerun the browser suite.

No real pedal recording, CoreAudio routing/permission behavior, MPS training or Mac VoiceOver behavior was verified. Root design guidance already identifies Linux offscreen screenshots as layout evidence with a pending Mac pass. That limit also applies to the audit's source/native evidence; HTML accessibility feedback is not a native accessibility certification.

## Pre-existing skill platform-schema mismatch

The incumbent product record truthfully says `macOS desktop · Python/Qt`. The Impeccable context launcher recognizes `web`, `ios`, `android` and `adaptive` and reported a desktop platform-schema mismatch. This is a tooling limitation, recorded independently from interface findings. It does not authorize recategorizing the application as web, rewriting root records or performing visual drift repair. The audit adapted its native dimensions to macOS Qt; no approval block resulted.

## Production handoff

Implement task structure/readiness first, then physical targets and state-preserving recovery, then structured training/review outcomes. Retain native Qt semantics while adapting the visual hierarchy. Verify real Mac keyboard behavior, VoiceOver announcements, appearance/font scaling, window limits, UMC22/CoreAudio permissions/routing and MPS fallback against the implemented app. The synthetic prototype is available for reviewing the intended interactions now.
