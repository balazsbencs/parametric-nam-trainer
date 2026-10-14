# Native mockup styling review

The user reported that the app still looked dated compared with the approved mockups. This refinement preserves the capture workflow, controls editor and current architecture options while matching the mockups’ typography, control chrome and grouped instruction graphics. Earlier native ship conclusions are historical and superseded by this feedback.

Fresh reviewer disposition: **ship**. No material findings remain.

| Finding | Final status |
| --- | --- |
| Disabled training presets | Resolved |
| Error-log disclosure synchronization | Resolved |
| Persistence documentation | Resolved — handoff and sidecar record the verified 15-asset package. |

The reviewer compared all twenty current native screenshots with the approved five-stage comps. TYPE and MATERIAL match: bundled Inter, restrained semibold headlines, quiet secondary text, flat paper surfaces, fine dividers and geometric vectors. Route rows, segmented coverage geometry, circular handle, physical diagrams, training presets and pinned actions retain the approved hierarchy. Extra controls, architecture options and actual export information are adaptations required by the current product. Example graphs and invented hardware statuses were not added.

The first pass caught two state issues. Explicit checked-disabled rules now distinguish unavailable presets during a job. Error and failed-start paths open the training log through its disclosure toggle, synchronizing visible content, arrow and first-click collapse. Both were confirmed resolved in recaptured running/error states. Documentation now points to the actual theme source and records the final font, sizes, assets, geometry and verification.

Verification: full suite **57 tests passed in 74.45 seconds**, with ten upstream Lightning deprecation warnings. The final targeted native test passed in **30.94 seconds** after the state fixes, including a real failed check job and disclosure collapse. A rebuilt wheel contains all **15** font, SVG, license and source assets and passes archive integrity checks. No runtime font download or fontTools dependency is introduced.

Evidence is Linux Qt offscreen, not macOS. Mac appearance, CoreAudio capture, full MPS training, hardware sound quality and VoiceOver remain unverified. The retained HTML-specific Inter exception remains narrow and historical; no new suppression was added. There are no new unresolved detector findings.

[Native screenshots](../../.impeccable/review/native/evidence.json) · [Built design](../../DESIGN.md) · [Handoff](native-design-handoff.md) · [Approved comps](../mockups/overview.html)
