# Design handoff: separate Parametric UX proposal

9 October 2026 · Impeccable documenter finish handoff.

The deliverable is the [five-stage interaction proposal](../mockups/index.html), [full overview](../mockups/overview.html) and [audit](report.md), now including the [one-slider Plan refinement](../mockups/plan-quality.md). It demonstrates a clearer physical capture task and recovery flow around the existing native engine. It is a code-led proposal, with synthetic data throughout, rather than an approved replacement production visual world. No approved raster composition or QUALITY BAR was supplied. The [earlier finish review](finish-review.md) records the original proposal fixes. The [current Plan finish review](plan-quality-review.md) finds no material defects and gives disposition `ship` for this ordinary refinement only.

[Root PRODUCT.md](../../PRODUCT.md) and [root DESIGN.md](../../DESIGN.md) remain incumbent production truth. They were read and kept untouched by this handoff. Extracted browser tokens and visual guidance live only in [docs/mockups/DESIGN.md](../mockups/DESIGN.md); they are descriptive of the proposal and have no authority over production widgets. No global Impeccable sidecar was created or refreshed.

## Proposal compared with production

| Concern | Incumbent production | Proposed artifact and implementation boundary |
| --- | --- | --- |
| Platform | macOS desktop, Python/PySide6 and pinned upstream NAM capture app | HTML is a local review artifact. It does not change the runtime stack or host real audio/training. |
| Visual authority | Standard Qt widgets, system typography, incumbent native tabs | Light neutral surfaces, blue action, local Inter and approximate desktop framing communicate the proposal. Native styling must be translated and verified on Mac. |
| Workflow | Project, Knobs, Plan, Audio I/O, Capture, Train on Mac and Pedal setup tabs | Five stages bring setup, targets, readiness and review together. Production needs an explicit shared session-state contract. |
| Physical capture | Existing planner/recorder persists captures and supports QA/recapture | Large dial instructions make the real knob task dominant. User confirmation gates Record; no automatic physical control is proposed. |
| Capture planning | Existing native planner and knob controls | One five-stop quality slider sets capture density, checks and both knob increments; Good is recommended. The Qt planner, backend and preset algorithm have not been changed. Real hardware validation is needed before adopting these example thresholds. |
| Continuity | Real project files and run folders | Example state survives re-render and stage navigation in browser memory. Reload persistence and structured resume are production work. |
| Recovery | Real processes, capped log and preserved capture/run files | Retry retains target; changed gain starts a separate calibration example; CPU retry retains captures. The browser preserves illustrative counters, not actual files or checkpoint contents. |
| Background jobs | QProcess separates checking/training from rendering; other tabs currently disabled | Simulated training survives stage navigation. Production must snapshot immutable inputs before allowing inspection of other surfaces. |
| Training result | Actual trainer exports model/metrics | A setup test is distinguished from candidate export. Review, held-out presentation and A/B UI are proposed work; no audio is played and no weights are downloaded. |
| Compact layout | Native minimum and appearance need Mac measurement | Stacked HTML at 390px supports artifact inspection. Plan's technical table is collapsed under Advanced; when expanded below 480px it uses a 600px internal table with a 160px first column. No page overflow does not mean no internal scrolling. |

## Current Plan contract

Ordinary pedal users choose Quick test, Decent, Good, Thorough or Overkill; Good is selected initially and Start capturing is the primary next action. Plain descriptions distinguish sparse setup coverage, a starting point, recommended coverage, extra detail and diminishing returns. Total recordings, sound-check count and estimated recording effort update immediately. The five presets contain 15, 26, 40, 68 and 116 recordings, with example effort of 11, 19, 29, 50 and 85 minutes. These are coverage choices for the illustrative two-knob pedal, not measured sound-quality guarantees. Estimates include playback and knob changes; training and retries add time.

The native browser range input retains its element through pointer movement, supports keyboard use and provides descriptive value text. Existing blue action/focus styling, utility typography, neutral surfaces and status badges remain the proposal's visual vocabulary. Local muted track segments support text labels rather than become new global tokens. No new visual-world selection, approved composition or sidecar is needed for this extension.

The slider adjusts counts and increments for both knobs without changing physical ranges, fixed Level or switches. Advanced stays collapsed and contains the physical range table, manual increments/counts, effort assumptions and coverage plot. Overrides are marked Custom settings; moving the slider restores automatic settings while preserving physical bounds. After an accepted take the plan is locked, Continue capturing becomes the main action and Start a separate plan retains earlier example count/quality/control metadata separately while starting at zero. Recording or training in progress blocks the separate-plan action. This is browser-memory behavior; native implementation must preserve immutable plan/calibration identity and real captures.

## Preserved constraints

- The UMC22 is the user's interface; a reamp box is missing. The proposal exposes that setup requirement and does not silently treat a line send as a calibrated instrument-level route.
- Pedal identity, actual knob count, Mac memory and hardware choices remain undecided. Drive/Tone with fixed Level are illustrative. Continuous controls are modeled; switches remain fixed per project.
- Keep calibration repeatable across a real session. A changed gain setting must be handled deliberately rather than mixed with earlier captures without explanation.
- Preserve the existing capture planner/recorder, standard native widget semantics, separate training/check processes, reproducible run folders, retained raw captures and the capped diagnostic log.
- Keep the compatible parametric-player requirement visible. Export alone does not establish quality, and stationary-knob data does not prove smooth automation.

## Evidence checked

Read the incumbent product/design records, proposal [stylesheet](../mockups/styles.css), [state implementation](../mockups/app.js), [overview](../mockups/overview.html), [prototype entry](../mockups/index.html), [README](../mockups/README.md), [Plan brief](../mockups/plan-quality.md), [mockup-verification.json](evidence/mockup-verification.json) and finish reviews. The original documenter pass inspected the five desktop and five 390px screens. For this refinement, visually inspected the current [default Plan](../mockups/screenshots/plan.png), [390px Plan](../mockups/screenshots/plan-390.png), [Quick test](../mockups/screenshots/plan-quality-0.png), [Overkill](../mockups/screenshots/plan-quality-4.png), [locked Plan](../mockups/screenshots/plan-locked.png) and [expanded Advanced](../mockups/screenshots/plan-advanced.png). These show the recommended default, clear low/high guidance, stacked compact commitment, disabled plan and bounded technical disclosure. The table is no longer exposed on the initial Plan screen.

Current supplied verification records 20 layout checks across all five stages at 1440, 960, 720 and 390px, 19 interaction checks and zero console errors. The 19 interactions are the current evidence total. They cover setup gating, cancellation, accepted/clipped takes, routing/range continuity, new-calibration separation, background simulated training, test/full outcomes, past-only epoch plots, review checklist/A/B continuity, CPU recovery, clearly labeled JSON handoff and direct file URL access. Plan-specific coverage includes all five levels, both knob increments, unchanged physical ranges, pointer dragging, keyboard focus/value text, custom overrides, capture handoff, locking and separation of earlier metadata. The refreshed screenshot set contains 29 PNGs with embedded local-render origins. This documenter pass inspected the evidence and source; it does not claim to have rerun the browser suite.

No real pedal recording, CoreAudio routing/permission behavior, MPS training or Mac VoiceOver behavior was verified. Root design guidance already identifies Linux offscreen screenshots as layout evidence with a pending Mac pass. That limit also applies to the audit's source/native evidence; HTML accessibility feedback is not a native accessibility certification.

## Pre-existing skill platform-schema mismatch

The incumbent product record truthfully says `macOS desktop · Python/Qt`. The Impeccable context launcher recognizes `web`, `ios`, `android` and `adaptive` and reported a desktop platform-schema mismatch. This is a tooling limitation, recorded independently from interface findings. It does not authorize recategorizing the application as web, rewriting root records or performing visual drift repair. The audit adapted its native dimensions to macOS Qt; no approval block resulted.

## Production handoff

Implement task structure/readiness first, then the single-decision Plan and physical targets with state-preserving recovery, then structured training/review outcomes. Before shipping a native quality preset, account for the actual knob count, reachable physical ranges and reference signals, and validate coverage on real captures. Keep accepted plans/calibration immutable and preserve old files when beginning a separate plan. Retain native Qt semantics while adapting the visual hierarchy. Verify real Mac keyboard behavior, VoiceOver announcements, appearance/font scaling, window limits, UMC22/CoreAudio permissions/routing and MPS fallback against the implemented app. The synthetic prototype is available for reviewing the intended interactions now; this refinement changes no Qt or backend code.
