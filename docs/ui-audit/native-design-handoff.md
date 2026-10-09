# Native design handoff

The user approved implementation of the five-stage HTML workflow and quality-slider refinement in the actual app, plus Mac run instructions. [Root DESIGN.md](../../DESIGN.md) now records the built native system, replacing stale tab guidance; [.impeccable/design.json](../../.impeccable/design.json) extends its tokens. Historical [mockup design](../mockups/DESIGN.md) and [Plan refinement](../mockups/plan-quality.md) remain approved interaction references. Their original scope disclaimers describe their creation before native implementation approval.

| Approved interaction | Native implementation |
| --- | --- |
| Connect → Plan → Capture → Train → Review | Persistent five-stage sidebar, header, scrollable pages and pinned handoffs. Navigation remains available during jobs. |
| One quality decision, Good recommended | Native five-stop slider; per-knob presets, real deduplicated counts, grid-bounded test allocation and effort from entries/source durations. Physical ranges and fixed controls stay fixed. |
| Advanced stays available | Initially collapsed disclosures; manual changes show Custom. Moving the slider restores presets while retaining bounds and roles. |
| Freeze recorded plans and keep prior takes | Sticky accepted-take lock, clear instructions and gray disabled slider. Separate projects require empty directories and retain earlier sources. |
| Physical target and confirmation | Read-only dials/values, accessible descriptions, native confirmation, selected-row rerecording and real capture QA. |
| Training and review | Real processes, retained run data/metrics/exports, stop and CPU retry, per-run listening state and compatible-player handoff. No simulated A/B player. |
| Mac run instructions | [README](../../README.md) covers installation, launchers, routing, workflow, recovery and remaining hardware checks. |

Production uses the approved familiar light utility direction and blue primary, with native system typography and Qt controls. Browser Inter loading, window framing, shadows and phone breakpoints were not transferred. Evidence covers 1140 × 900 and 800 × 680; code minimum is 760 × 580. Advanced tables scroll internally and stage actions stay pinned.

The [evidence manifest](../../.impeccable/review/native/evidence.json) identifies sixteen actual Linux Qt offscreen screenshots. [Native finish review](native-finish-review.md) gives a ship verdict: warning contrast and locked Plan copy/appearance both resolved. Functional validation passed 37 tests in 21.71 seconds, with two upstream deprecation warnings and real synthetic CPU model exports. Tests extend the visual verdict; they do not certify Mac hardware behavior.

Mac installation, CoreAudio, full MPS training, real-pedal accuracy and Mac VoiceOver need an actual Mac/hardware pass. Review reports last-epoch ESR honestly and requires external listening. The sidecar stores native source/state metadata without fabricated HTML/CSS previews or invented tonal ramps. Existing mockup-specific detector configuration is unchanged; no native suppression was added.
