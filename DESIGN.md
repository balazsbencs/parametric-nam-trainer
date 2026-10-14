---
name: Parametric native desktop
description: An approved light desktop utility for physical gear capture and local training.
colors:
  primary: "#175cd3"
  primary-hover: "#124db5"
  primary-pressed: "#1047a4"
  primary-soft: "#e4ecfc"
  paper: "#ffffff"
  sidebar: "#f6f7f9"
  detail-surface: "#f8fafc"
  ink: "#252a32"
  muted: "#606773"
  quiet-ink: "#52617a"
  divider: "#e1e5ec"
  field-border: "#cdd6e3"
  field-hover-border: "#a8bbd6"
  hover-surface: "#f4f7fc"
  quiet-hover: "#eef3fa"
  disabled-surface: "#f3f5f8"
  disabled-primary: "#edf1f7"
  disabled-ink: "#687382"
  disabled-border: "#dfe5ee"
  disabled-handle: "#929aa6"
  dial-border: "#d2ddec"
  dial-surface: "#f3f6fb"
  caution: "#925517"
  coverage-low: "#e2c79e"
  coverage-balanced: "#b6d2c1"
  coverage-high: "#d3d9e2"
typography:
  headline:
    fontFamily: "Inter"
    fontSize: "27px"
    fontWeight: 600
    letterSpacing: "-0.6px"
  section:
    fontFamily: "Inter"
    fontSize: "13px"
    fontWeight: 600
  body:
    fontFamily: "Inter"
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: "Inter"
    fontSize: "12px"
    fontWeight: 400
  button:
    fontFamily: "Inter"
    fontSize: "12px"
    fontWeight: 500
  quality:
    fontFamily: "Inter"
    fontSize: "28px"
    fontWeight: 600
  dial-value:
    fontFamily: "Inter"
    fontSize: "30px"
    fontWeight: 600
  stop-label:
    fontFamily: "Inter"
    fontSize: "12px"
    fontWeight: 400
rounded:
  progress: "3px"
  field: "6px"
  button: "6px"
  navigation: "7px"
  signal-route: "8px"
  target-group: "10px"
spacing:
  field-label-gap: "6px"
  small: "8px"
  control-padding: "10px"
  group-gap: "12px"
  sidebar-inset: "16px"
  page-gap: "18px"
  page-inset: "24px"
  column-gap: "28px"
  frame-inset: "30px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.button}"
    typography: "{typography.button}"
    padding: "8px 13px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.disabled-primary}"
    textColor: "{colors.disabled-ink}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    typography: "{typography.button}"
    padding: "8px 13px"
  button-secondary-hover:
    backgroundColor: "{colors.hover-surface}"
  button-secondary-disabled:
    backgroundColor: "{colors.disabled-surface}"
    textColor: "{colors.disabled-ink}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.quiet-ink}"
    rounded: "{rounded.button}"
    padding: "7px 10px"
  navigation-current:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    rounded: "{rounded.navigation}"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "7px 10px"
  detail-view:
    backgroundColor: "{colors.detail-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
---

# Design System: Parametric native desktop

## Overview

**Creative North Star: "Your pedal, captured."**

The approved direction is a familiar light desktop utility: quiet working surfaces, blue actions, compact task labels and explicit state messages. The user chose the conventional utility in the [original mockups](docs/mockups/DESIGN.md), then said the native app looked dated beside those approved screenshots. This refinement restores their typography, control chrome and density. Retain that commitment as the controls grow from pedals to amp layouts. Its signature remains a read-only physical dial target paired with a numerical position and confirmation before recording.

This refresh records the built [native theme](parametric_mac/theme.py), [Qt shell](parametric_mac/gui.py), [controls editor](parametric_mac/control_editor.py) and [bundled UI assets](parametric_mac/ui_assets/FONT-SOURCE.md). The historical [workflow mockups](docs/mockups/overview.html) and [Plan proposal](docs/mockups/plan-quality.md) remain approved references. The approved Inter face is bundled for native use; current Qt code supplies production tokens. Browser framing and example metrics remain reference material. Evidence and unresolved finish findings belong in the [native handoff](docs/ui-audit/native-design-handoff.md), not in the visual system as new rules.

**Key Characteristics:**

- Five persistent numbered stages with short secondary labels.
- Working and reference columns, a centered coverage choice and pinned next actions.
- Editable knobs and named switches, with readable rows and grouped physical targets.
- Readiness, saved progress, actual run data and recovery explain the next task.

## Colors

Restrained neutrals and one blue action accent suit hands-on setup beside physical audio gear. An explicit light Qt palette keeps that direction across platform styles.

### Primary

Action Blue marks the principal enabled action, selected stage, focus border, progress fill and physical dial pointer. Dial values use Utility Ink. Its darker variants identify button hover and press; its pale companion identifies current navigation. The low, balanced and high coverage colors support the five-stop scale, whose labels explain their meaning.

### Neutral

Working Paper is the main region; Quiet Sidebar separates navigation; Detail Surface groups routes, targets, tables and logs. Utility Ink carries primary text and Supporting Gray carries instructions and disabled labels. Divider separates regions, Field Border defines controls and dial arcs, and Hover Surface identifies available actions. Disabled surfaces and the gray slider handle distinguish unavailable controls.

### Status

Readable Caution accompanies device and sample-rate explanations. The slim progress bar uses Action Blue. The Good recommendation has a small green text badge; it identifies a suggested starting point rather than verified sound quality. The status bar retains the same light surface and readable supporting text.

**The State Meaning Rule.** Explain readiness and recovery in text; color alone must not imply successful recording, finished sound quality or completed listening.

## Typography

Inter is the approved mockup's interface face. Native Qt loads bundled static Regular (400), Medium (500) and SemiBold (600) fonts through `theme.install_typography()` before building the interface. Actual weight files make selection consistent across platform styles. [Font provenance and licensing](parametric_mac/ui_assets/FONT-SOURCE.md) accompany the assets; runtime requires neither network access nor fontTools. Keep this native implementation separate from the historical HTML-only detector exception.

The hierarchy is compact: body text (13px, regular); muted instructions, field labels and stop names (12px, regular); action labels (12px, medium); section headings (13px, semibold); stage titles (27px, semibold, −0.6px absolute tracking); selected coverage (28px, semibold); physical target values (30px, semibold). Primary action labels are semibold. Navigation main labels use 14px, with semibold for the current stage. Dial names are 12px semibold; range endpoints, captions, stage numbers and status-bar text use 11px regular.

Keep the selected quality name at its natural width so Good and Overkill remain intact beside the recommendation badge. Wrapping instructions use native height-for-width sizing. No fixed line-height or font-loading animation is established.

## Layout

A fixed sidebar (208px), project header, independently scrolling pages and pinned action row form the native shell. Sidebar insets are (16px horizontal, 24px top, 20px bottom). Working-frame insets are (30px horizontal, 16px top, 12px bottom). Pages add insets (8px horizontal, 24px vertical) and gaps (18px). Pinned actions use insets (8px sides/top, zero bottom).

Connect, Capture, Train and Review use two equal working/reference columns separated by (28px), with internal gaps (12px). Columns align contents to the top. Wrapping labels and panels advertise height-for-width sizing; stacked panels use natural content heights and the same 28px gap, without trailing stretches. They stack when the available page content width falls below (780px); the calculation uses the scroll viewport width minus (16px), not the whole window width. Plan centers its quality panel with a maximum width (780px), while summaries and disclosures use the page width.

The initial window is (1140 × 840px), with a code minimum (760 × 580px). Evidence covers (1140 × 900px) and (800 × 680px). Compact windows retain the sidebar and scroll the page; there is no phone navigation pattern. Explicit form growth, left/top alignment and long-row wrapping address Qt Mac style defaults; editable fields expand horizontally. Advanced tables and the control list scroll internally.

Project fields place labels above their controls; Name and Gear share a row, followed by Keep fixed. Send and Return channels share equal-width fields below the interface selector. Control rows retain height (42px) and gaps (6px). The list grows between (92px) and (292px) before scrolling, while the editor fixes its total height to the list plus (48px), preserving its action row. Adding controls must never compress editable rows. Physical targets reflow into one to three columns at (170px per target), with rows (190px high).

**The Pinned Handoff Rule.** Keep the stage's next action outside its scrolling content and show why it is unavailable.

**The Readable Control Rule.** Preserve control-row height and scroll longer layouts rather than squeezing editable fields and actions.

## Elevation & Depth

Flat surfaces, pale tonal separation, thin borders and spacing provide hierarchy without decorative shadows. Qt/platform style supplies native window chrome. No browser shadow, Material elevation scale or decorative layout animation is established. Progress and state update immediately.

## Shapes

Small rounded rectangles define buttons, fields, navigation and details; route and physical-target groups use the slightly softer corners recorded in frontmatter. Styled buttons, line edits, selectors and number fields retain a thin blue focus border (1px). Checkbox focus uses a visible outline. Scrollbars are slim (8px), without decorative end buttons. Comboboxes, spin boxes, checkboxes and disclosures use bundled SVG chrome rather than platform-dependent glyphs.

Coverage uses three separated rounded track segments (7px high) and a circular blue handle (11px radius, 3px white border); keyboard focus adds an outer ring (14px radius). Its painted center comes from Qt's actual slider handle geometry so native hit testing and keyboard behavior agree. Numbered navigation uses small painted circles. Physical dials use an open arc (96px diameter), pale inner disk (74px diameter) and short rounded blue pointer; they remain instruction diagrams.

## Components

### Buttons

Filled blue actions lead available tasks; white bordered buttons express secondary actions. Primary labels are semibold. Hover and keyboard focus remain visible. Disabled primary and secondary variants use separate pale surfaces with muted labels. Quiet transparent Add/Remove actions reduce chrome around editable rows. Checkable disclosures use a dividing line and SVG chevrons, pointing right when closed and down when open, and reveal details in place. Preserve the QSS state ordering when extending variants.

### Cards / Containers

The outlined signal route has a muted caption, compact icon-and-text rows and thin row dividers. Pale physical-target groups separate instruction from supporting reference. They use small rounded corners, tonal fill and spacing rather than shadows. Logs and tables use the same detail family with internal scrolling. Avoid adding a card around every form group.

### Inputs / Fields

Native line edits, selectors and number fields retain labeled Qt semantics, padding and content height. Bundled vector arrows, check marks and styled scrollbars keep their chrome consistent across platform styles; checked-disabled indicators stay visibly checked in muted colors. Routing, capture and training details begin under collapsed disclosures. Mutable inputs disable during jobs; navigation remains available. Native dialogs edit knob bounds and gain/avoid-zero roles, or named switch positions one per line. Validation copy wraps and explains how to recover.

### Navigation

Connect, Plan, Capture, Train and Review remain a vertical sequence. Each native button has a painted stage number, main label and secondary task description, with a minimum height (62px). The selected row uses a pale blue surface, a filled numbered circle and semibold blue text; keyboard focus has its own border. Project identity and New/Open stay in the header. Sidebar job status remains visible independently of the selected stage.

### Controls editor

Connect provides Add knob, Add switch and a Remove action on each row, alongside an editable name and range/position button. Pedal starter supplies Drive and Tone; Amp starter supplies six knobs and Bright. Starters remain editable. The bounded list supports up to 24 total controls, including switches, and prevents removing the last continuous knob. Preserve visible names and named positions as controls are added; numerical switch codes stay out of physical prompts. Accepted recordings lock this editor with the plan.

### Capture-quality plan

The segmented native keyboard-accessible CoverageSlider has five stops: Quick test, Decent, Good, Thorough and Overkill. Good is the initial recommendation. Visible hints, accessible value text, generated counts and effort update together. Presets adjust every continuous knob's sampling while retaining physical ranges and switch labels. Every switch combination receives training and held-out settings; count and effort copy must reflect the actual entries. Plans bound combinations to 32 and recordings to 5,000. More than eight knobs use bounded axis boundary sweeps rather than exponential corners. These are functional limits, not promises of model accuracy; [planning source](parametric_mac/workflow.py) and [control metadata](parametric_mac/controls.py) own the algorithms.

Advanced starts collapsed. Manual edits show Custom; moving the slider restores a complete preset while retaining bounds and roles. After the first accepted take, a sticky lock disables edits even if captures are cleared. Locked copy directs the user to continue with saved settings or create a separate project in an empty directory. Prior source files remain intact.

### Physical knob target

Grouped read-only dial drawings place the knob name above an outlined arc and inner disk; the blue pointer, actual range endpoints, dark semibold value and Physical knob position caption clarify the target. Exact target text includes named switch positions and fixed-control instructions. Accessible descriptions and a native checkbox support physical confirmation before recording. The preview queue follows the same pending-entry order as the capture engine. Selected-row rerecording displays that row's saved setting; a changed target clears confirmation. Cancellation, saved-take feedback and QA remain actual engine states.

### Training and review

Training offers exclusive segmented Full training, Quick test and Custom profiles backed by the original duration combo and actual epoch settings (200 epochs, one epoch and editable duration). Selection, accessible names and duration notes stay synchronized. Disabled profiles use muted checked styling during jobs. The architecture selector retains NAM A2 Standard + Nano, Standard, Nano, automatic-width and FiLM variants; dual profiles use the selected epoch count for each size. Real process progress, metrics, log/error disclosure, stop and CPU retry provide recovery. An error opens the log through its checked disclosure state so the chevron and visible content stay synchronized. Review separates export status, last logged validation ESR and per-run listening confirmation. It opens run/test folders, copies the actual model and links the compatible player. Last-epoch ESR is not a separate evaluation of the exported checkpoint. No built-in A/B player or simulated waveform is present.

## Do's and Don'ts

### Do:

- **Do** preserve native Qt control semantics and visible keyboard focus.
- **Do** keep working/reference columns, physical targets and pinned next actions readable as layouts grow.
- **Do** retain readable control rows with direct Add, Remove and settings actions.
- **Do** show named switch positions and real physical dial ranges.
- **Do** explain locked or unavailable actions with a concrete next step.
- **Do** derive counts, progress and review metrics from saved application data.
- **Do** retain separate projects and source files when capture settings change.

### Don't:

- **Don't** interpret capture coverage as a guaranteed sound-quality rating.
- **Don't** make the physical dial diagram appear interactive or automatic.
- **Don't** add runtime font downloads, browser framing, phone breakpoints or example metrics to native truth.
- **Don't** imply a completed export has been listened to or validated on real hardware.
- **Don't** infer Mac/CoreAudio/MPS/VoiceOver verification from Linux offscreen screenshots.
