# Native controls and mockup-fidelity review

The user requested easier knob counts, future amp layouts with more knobs and switches, and closer fidelity to the approved mockups. Their actual Mac screenshot superseded the earlier native finish verdict. The fresh Impeccable reviewer compared the original five-stage images against 20 current native desktop / compact images and sampled the implementation. The documenter refreshed the built design system independently.

Final reviewer disposition: **ship**. Remaining: **clear**.

| Material fix | Final status |
| --- | --- |
| Compact layout and spacing | Resolved: listening guidance follows folder actions with the intended 28px gap. |
| Quality panel and headings | Resolved |
| Readable amp editor rows | Resolved |
| Exact queue / target order | Resolved |
| Visible dial bounds | Resolved |
| Warning glyph removal | Resolved |
| Persistence refresh | Resolved |

The light shell, 208px sidebar, numbered stages with task descriptions, working/reference columns, bounded centered quality panel, grouped physical targets and pinned actions preserve the approved utility composition. Direct control rows and pedal / amp starters implement the new request. Native system typography and actual engine states replace browser-specific framing and illustrative signals. There is no simulated waveform or A/B player.

The initial fixes exposed a Qt sizing regression: width-independent minimum constraints allocated extra vertical space even when text wrapped into fewer lines. Final labels and panels advertise height-for-width, stacked panels keep natural heights, and visible-content geometry is tested. Evidence includes the intended 28px compact Review gap, not merely a gap between containers.

Final functional verification: **43 tests passed in 45.53 seconds**, with three upstream Lightning deprecation warnings. Tests include typed project save/reload, switch-conditioned CPU training and export, all switch combinations in both splits, bounded 24-control planning, safe capture filenames, native editing and compact geometry. This evidence uses Linux Qt offscreen and synthetic audio; Mac installation, CoreAudio, full MPS training, hardware captures, player listening and VoiceOver remain unverified.

The earlier HTML hook findings retain their existing disposition: the layout-property animation was removed; the intentional self-hosted Inter font remains narrowly exempted for `docs/mockups/styles.css`. No new rule/file/value suppression was added in this native pass.

Evidence: [current native screenshots](../../.impeccable/review/native/evidence.json), [built design](../../DESIGN.md), [native handoff](native-design-handoff.md), [validation](../validation.md). Approved references: [workflow mockups](../mockups/overview.html), [quality proposal](../mockups/plan-quality.md).
