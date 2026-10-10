---
name: Parametric native desktop
description: A familiar light desktop utility for physical gear capture and local training.
colors:
  primary: "#175cd3"
  primary-hover: "#124db5"
  primary-soft: "#eaf1fe"
  paper: "#ffffff"
  sidebar: "#f6f7f9"
  detail-surface: "#f8f9fb"
  ink: "#252a32"
  muted: "#606773"
  divider: "#e4e6e9"
  field-border: "#d0d5dd"
  hover-surface: "#f1f5fc"
  disabled-surface: "#f3f4f6"
  disabled-primary: "#e8edf5"
  disabled-handle: "#929aa6"
  caution: "#925517"
  coverage-low: "#e2c79e"
  coverage-balanced: "#b6d2c1"
  coverage-high: "#d3d9e2"
  progress: "#b5cbf3"
typography:
  headline:
    fontSize: "28px"
    fontWeight: 600
  section:
    fontSize: "15px"
    fontWeight: 600
  body:
    fontSize: "14px"
  quality:
    fontSize: "28px"
    fontWeight: 600
  dial-value:
    fontSize: "26px"
    fontWeight: 700
  stop-label:
    fontSize: "12px"
rounded:
  progress: "4px"
  field: "5px"
  button: "6px"
  slider-handle: "12px"
spacing:
  field: "6px"
  small: "8px"
  sidebar-inset: "12px"
  button-inline: "14px"
  page-gap: "16px"
  page-inset: "24px"
  column-gap: "28px"
  frame-inset: "30px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.button}"
    padding: "9px 14px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.disabled-primary}"
    textColor: "{colors.muted}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "9px 14px"
  button-secondary-hover:
    backgroundColor: "{colors.hover-surface}"
  button-secondary-disabled:
    backgroundColor: "{colors.disabled-surface}"
    textColor: "{colors.muted}"
  navigation-current:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    padding: "12px 16px"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "{spacing.field}"
  detail-view:
    backgroundColor: "{colors.detail-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
---

# Design System: Parametric native desktop

## Overview

**Creative North Star: "Your pedal, captured."**

The approved direction is a familiar light desktop utility: quiet working surfaces, blue actions, compact task labels and explicit state messages. The user chose the conventional utility in the [original mockups](docs/mockups/DESIGN.md) and requested closer native fidelity after seeing drift on Mac. Retain that commitment as the controls grow from pedals to amp layouts. Its signature remains a read-only physical dial target paired with a numerical position and confirmation before recording.

This refresh records the built [Qt shell](parametric_mac/gui.py) and [controls editor](parametric_mac/control_editor.py). The historical [workflow mockups](docs/mockups/overview.html) and [Plan proposal](docs/mockups/plan-quality.md) remain approved references. Qt code supplies production tokens; browser fonts, framing and example metrics do not. Evidence and unresolved finish findings belong in the [native handoff](docs/ui-audit/native-design-handoff.md), not in the visual system as new rules.

**Key Characteristics:**

- Five persistent numbered stages with short secondary labels.
- Working and reference columns, a centered coverage choice and pinned next actions.
- Editable knobs and named switches, with readable rows and grouped physical targets.
- Readiness, saved progress, actual run data and recovery explain the next task.

## Colors

Restrained neutrals and one blue action accent suit hands-on setup beside physical audio gear. An explicit light Qt palette keeps that direction across platform styles.

### Primary

Action Blue marks the principal enabled action, selected stage, focus border and physical dial pointer/value. Its darker variant identifies button hover; its pale companion identifies current navigation. The low, balanced and high coverage colors support the five-stop scale, whose labels explain their meaning.

### Neutral

Working Paper is the main region; Quiet Sidebar separates navigation; Detail Surface groups routes, targets, tables and logs. Utility Ink carries primary text and Supporting Gray carries instructions and disabled labels. Divider separates regions, Field Border defines controls and dial arcs, and Hover Surface identifies available actions. Disabled surfaces and the gray slider handle distinguish unavailable controls.

### Status

Readable Caution accompanies device and sample-rate explanations. Progress supplies the native progress-bar fill. The Good recommendation has a small green text badge; it identifies a suggested starting point rather than verified sound quality. The status bar retains the same light surface and readable supporting text.

**The State Meaning Rule.** Explain readiness and recovery in text; color alone must not imply successful recording, finished sound quality or completed listening.

## Typography

Use the Qt application's native system font. The wrapper loads no font and sets no family. Frontmatter records explicit QSS and painter sizes without invented line heights or letter spacing.

Headlines and the selected quality use the large semibold step. Section labels use the smaller semibold step, with body text for wrapping instructions and fields. Physical dial values use bold painter text; knob names use body size. Stop hints and navigation secondary labels use the compact label size. Stage numbers and dial range endpoints use the smaller painter size (11px). Keep the selected quality name at its natural width so Good and Overkill remain intact beside the recommendation badge.

## Layout

A fixed sidebar (208px), project header, independently scrolling pages and pinned action row form the native shell. Sidebar insets are (12px horizontal, 24px top, 20px bottom). Working-frame insets are (30px horizontal, 16px top, 12px bottom). Pages add insets (8px horizontal, 24px vertical) and gaps (16px). Pinned actions use insets (8px sides/top, zero bottom).

Connect, Capture, Train and Review use two equal working/reference columns separated by (28px), with internal gaps (12px). Columns align contents to the top. Wrapping labels and panels advertise height-for-width sizing; stacked panels use natural content heights and the same 28px gap, without trailing stretches. They stack when the available page content width falls below (780px); the calculation uses the scroll viewport width minus (16px), not the whole window width. Plan centers its quality panel with a maximum width (780px), while summaries and disclosures use the page width.

The initial window is (1140 × 840px), with a code minimum (760 × 580px). Evidence covers (1140 × 900px) and (800 × 680px). Compact windows retain the sidebar and scroll the page; there is no phone navigation pattern. Explicit form growth, left/top alignment and long-row wrapping address Qt Mac style defaults; editable fields expand horizontally. Advanced tables and the control list scroll internally.

Control rows retain height (42px) and gaps (6px). The list grows between (92px) and (292px) before scrolling; adding controls must never compress the rows. Physical targets reflow into one to three columns at (170px per target), with rows (165px high).

**The Pinned Handoff Rule.** Keep the stage's next action outside its scrolling content and show why it is unavailable.

**The Readable Control Rule.** Preserve control-row height and scroll longer layouts rather than squeezing editable fields and actions.

## Elevation & Depth

Flat surfaces, pale tonal separation, thin borders and spacing provide hierarchy without decorative shadows. Qt/platform style supplies native window chrome. No browser shadow, Material elevation scale or decorative layout animation is established. Progress and state update immediately.

## Shapes

Small rounded rectangles define buttons, fields, detail regions and progress bars. Focused styled buttons, line edits, selectors, integer fields and the slider use a blue border (2px). The slider has a rounded groove (8px high) and rounded handle (20px wide, 3px white border). Numbered navigation uses small painted circles. Physical dials use an open arc (84px diameter) and rounded pointer; they are instruction diagrams.

## Components

### Buttons

Filled blue actions lead available tasks; white bordered buttons express secondary actions. Primary labels are semibold. Hover and keyboard focus remain visible. Disabled primary and secondary variants use separate pale surfaces with muted labels. Checkable disclosures use a dividing line and reveal details in place. Preserve the QSS state ordering when extending variants.

### Cards / Containers

Light bordered route and target groups separate instruction from supporting reference. They use small rounded corners, tonal fill and spacing rather than shadows. Logs and tables use the same detail family with internal scrolling. Avoid adding a card around every form group.

### Inputs / Fields

Native line edits, selectors and number fields retain labeled Qt semantics, padding and content height. Routing, capture and training details begin under collapsed disclosures. Mutable inputs disable during jobs; navigation remains available. Native dialogs edit knob bounds and gain/avoid-zero roles, or named switch positions one per line. Validation copy wraps and explains how to recover.

### Navigation

Connect, Plan, Capture, Train and Review remain a vertical sequence. Each native button has a painted stage number, main label and secondary task description, with a minimum height (62px). The selected row uses a pale blue surface, a filled numbered circle and semibold blue text; keyboard focus has its own border. Project identity and New/Open stay in the header. Sidebar job status remains visible independently of the selected stage.

### Controls editor

Connect provides Add knob, Add switch and a Remove action on each row, alongside an editable name and range/position button. Pedal starter supplies Drive and Tone; Amp starter supplies six knobs and Bright. Starters remain editable. The bounded list supports up to 24 total controls, including switches, and prevents removing the last continuous knob. Preserve visible names and named positions as controls are added; numerical switch codes stay out of physical prompts. Accepted recordings lock this editor with the plan.

### Capture-quality plan

The native keyboard-accessible slider has five stops: Quick test, Decent, Good, Thorough and Overkill. Good is the initial recommendation. Visible hints, accessible value text, generated counts and effort update together. Presets adjust every continuous knob's sampling while retaining physical ranges and switch labels. Every switch combination receives training and held-out settings; count and effort copy must reflect the actual entries. Plans bound combinations to 32 and recordings to 5,000. More than eight knobs use bounded axis boundary sweeps rather than exponential corners. These are functional limits, not promises of model accuracy; [planning source](parametric_mac/workflow.py) and [control metadata](parametric_mac/controls.py) own the algorithms.

Advanced starts collapsed. Manual edits show Custom; moving the slider restores a complete preset while retaining bounds and roles. After the first accepted take, a sticky lock disables edits even if captures are cleared. Locked copy directs the user to continue with saved settings or create a separate project in an empty directory. Prior source files remain intact.

### Physical knob target

Grouped read-only dial drawings show orientation, value, knob name and actual range endpoints. Exact target text includes named switch positions and fixed-control instructions. Accessible descriptions and a native checkbox support physical confirmation before recording. The preview queue follows the same pending-entry order as the capture engine. Selected-row rerecording displays that row's saved setting; a changed target clears confirmation. Cancellation, saved-take feedback and QA remain actual engine states.

### Training and review

Training offers full, one-epoch workflow-test and custom durations. Real process progress, metrics, log/error disclosure, stop and CPU retry provide recovery. Review separates export status, last logged validation ESR and per-run listening confirmation. It opens run/test folders, copies the actual model and links the compatible player. Last-epoch ESR is not a separate evaluation of the exported checkpoint. No built-in A/B player or simulated waveform is present.

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
- **Don't** copy browser font loading, phone breakpoints or example metrics into native truth.
- **Don't** imply a completed export has been listened to or validated on real hardware.
- **Don't** infer Mac/CoreAudio/MPS/VoiceOver verification from Linux offscreen screenshots.
