# Native finish review

disposition: ship

Final verdict pass: **both listed material fixes resolved**. This disposition scores the two fixes from the full review below; it is not a new whole-surface audit or Mac hardware certification.

## persistence

The native implementation preserves the approved five-stage task and real data. `gui.py` uses the existing capture session, saves a committed plan and workflow metadata, restores projects, keeps a sticky lock after an accepted take, and requires an empty separate-project directory rather than replacing prior recordings. Navigation stays enabled during jobs while input mutations are disabled. `training.py` produces separate run directories, saved configs, audio hashes, real logged metrics and actual exports. Review stores listening status per run and copies the real model. The README explains installation, physical routing, recovery and the compatible player. This is source and screenshot evidence, not physical Mac/CoreAudio/MPS verification.

## fidelity

This is a full review after the invalid Advanced capture was replaced. All sixteen current PNGs were opened: five stages at 1140 × 900 and 800 × 680, Quick/Overkill/locked Plan, expanded compact Advanced, running check, and training error. Each now shows its named state. The expanded Advanced capture shows physical ranges/steps, manual counts and seed, with Start capturing pinned. Its table has an internal horizontal scrollbar rather than overflowing the app.

The light utility, quiet sidebar, approved blue actions, readable numerical dial targets and explicit physical confirmation translate the mockups convincingly to native Qt. Good defaults to one five-stop decision; Advanced begins collapsed. Actual plan counts are used, including Quick's 14 recordings instead of copying the illustrative web count, and effort is calculated from generated entries and source durations. Review clearly distinguishes export, last-epoch ESR and listening, and makes an honest compatible-player handoff without simulated A/B playback. The full review identified the two bounded state/accessibility defects below; the subsequent verdict pass resolved both.

## ceiling

No rebuild was warranted by the full review. The composition, task hierarchy, native controls, scroll containment, pinned stage handoffs, focus outline, and job/error recovery meet the familiar desktop direction. No web detector ran; the native craft floor was inspected directly. The verdict pass scores only warning contrast and locked Plan state. Both are resolved; no further correction round is owed for this list.

## material_fixes

| Listed fix | Verdict | Evidence |
| --- | --- | --- |
| Warning text contrast | resolved | Reopened Connect desktop and Capture desktop/compact captures. Actual foreground pixels are `#925517` on white, approximately **5.94:1**, exceeding 4.5:1. Native wrapper directly overrides the inherited label foreground. Messages and layout remain intact. |
| Locked Plan copy and disabled appearance | resolved | Reopened locked Plan and enabled Good captures. Locked copy now says “Recording has started. Continue with the saved capture settings.” The separate-project notice remains actionable. Disabled groove `#e4e6e9` and handle `#929aa6` visibly differ from enabled Good's blue handle and colored track; stop labels remain readable. Source applies the locked description independently of whether the saved plan has a named preset. |

No partial or unresolved items remain in the two-fix list. No application changes were made by this reviewer. The final test run is reported as running by the build thread and is not certified by this visual verdict.

## keep

Keep the five-stage sidebar, single Good-default quality slider, real deduplicated counts and effort, collapsed technical settings, physical dial targets and confirmation, frozen plans and separate projects, visible job navigation, CPU recovery, genuine saved-run metrics and exports, and compatible-player listening flow. Preserve the README's explicit Linux/synthetic development provenance and remaining Mac hardware checks. Preserve the native desktop translation rather than reproducing browser framing or requiring phone conventions. Root DESIGN.md remains the documenter's authorized follow-up.
