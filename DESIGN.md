---
name: Parametric native desktop
description: A familiar light desktop utility for physical pedal capture and local training.
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
    fontSize: "18px"
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

The approved direction is a familiar light desktop utility: quiet working surfaces, blue actions, compact task labels and explicit state messages. Its signature is a read-only physical dial target paired with a numerical position and confirmation before recording. The interface makes the next physical task and its saved progress easy to find.

This document refreshes the earlier native-tab guidance after approval to implement the five-stage proposal and quality slider. It records the built Python/Qt interface in `parametric_mac/gui.py`; the historical [mockup design](docs/mockups/DESIGN.md) and [Plan proposal](docs/mockups/plan-quality.md) remain approved interaction references. Browser font, framing, breakpoints and synthetic metrics are not production tokens. Qt code remains the source of truth for these extracted values.

**Key Characteristics:**

- Five persistent stages: Connect, Plan, Capture, Train and Review.
- One initial capture-coverage decision; technical controls start collapsed.
- Physical targets, readiness, saved progress and recovery carry the task.
- Real run data and a compatible-player handoff keep review honest.

## Colors

### Primary

Action Blue marks the principal enabled action, selected stage, focus outline and physical dial pointer/value. Its darker variant identifies button hover; its pale companion identifies current navigation. Coverage track colors support the five-stop scale, whose labels and descriptions explain the meaning.

### Neutral

Paper is the working region; Sidebar separates navigation; Detail Surface groups tables and logs. Ink carries primary text and Muted carries supporting instructions and disabled labels. Divider separates regions, Field Border defines controls and the dial arc, and Hover Surface distinguishes available actions. Disabled primary/secondary surfaces and the gray slider handle distinguish unavailable controls.

### Status

Caution colors inherited device/sample-rate warnings, accompanied by explanatory text. Progress colors the native progress-bar fill. Existing upstream QA can provide additional native treatments; do not infer global status tokens from illustrative browser data.

**The State Meaning Rule.** Explain readiness and recovery in text; color alone must not imply successful recording, finished sound quality or completed listening.

## Typography

Use the Qt application's native system font. The wrapper sets no font family and loads no Inter. System selection and platform rendering remain authoritative. Frontmatter records explicit QSS and painter sizes without inventing line heights or letter spacing.

Headlines and the quality choice lead the task. Section text organizes forms, counts and status. Body text carries wrapping instructions and controls. The painted dial value is bold, followed by a body-size knob name. Painted stop labels carry names and short hints. Preserve native font metrics and focus semantics when adding controls.

## Layout

A fixed sidebar (172px), project header, independently scrollable stage pages and pinned stage-action row form the native shell. Sidebar insets are (12px horizontal, 24px top, 20px bottom); working-frame insets are (24px horizontal, 16px top, 12px bottom). Pages add insets (8px horizontal, 24px vertical) and gaps (16px). Pinned action rows use insets (8px sides/top, zero bottom).

The initial window is (1140 × 840px), with code minimum (760 × 580px). Current evidence covers (1140 × 900px) and (800 × 680px). Compact windows retain the sidebar and scroll content; there is no phone breakpoint or horizontal mobile navigation. Advanced tables scroll internally. Physical targets reflow into one to three columns at (170px per target), with rows (165px high).

**The Pinned Handoff Rule.** Keep the stage's next action outside its scrolling content and show why it is unavailable.

## Elevation & Depth

Flat surfaces, pale tonal separation, thin borders and spacing provide hierarchy without decorative shadows. Qt/platform style supplies native window chrome and control rendering. No browser shadow, Material elevation scale or animated transition is established. Progress and state update immediately without decorative layout animation.

## Shapes

Small rounded rectangles define buttons, fields, details and progress bars. Focused buttons, fields, selectors and the slider use a blue outline (2px). The slider has a rounded groove (8px high) and circular-looking handle (20px wide, 3px white border). Physical dials use an open arc (84px diameter) and rounded pointer. They are instruction diagrams.

## Components

### Buttons

Filled blue actions lead available tasks; white bordered buttons express secondary actions and disclosures. Primary labels are semibold. Hover and focus are visible. Disabled primary/secondary buttons use separate pale surfaces with muted labels. Preserve QSS state ordering when extending variants.

### Inputs / Fields

Native line edits, selectors and number fields retain labeled Qt semantics, minimum content height (22px), padding and focus outline. Technical routing, capture and training controls sit under checkable disclosures. Mutable inputs disable during jobs; navigation remains available.

### Navigation

Connect, Plan, Capture, Train and Review remain a persistent vertical sequence. The selected row uses a pale blue surface and semibold blue text; keyboard focus has its own outline. The header retains project identity and New/Open actions. Sidebar job status stays visible independently of the selected stage.

### Capture-quality plan

The keyboard-accessible native slider has five stops: Quick test, Decent, Good, Thorough and Overkill. Good is the initial recommendation. Descriptive accessible value text, visible hints, generated counts and effort update with the plan. Presets set per-knob sampling, tests and increments while preserving physical ranges and fixed controls. One-knob grid limits bound test allocation; counts come from deduplicated reachable entries rather than copied mockup totals.

Advanced starts collapsed and exposes physical ranges, steps, manual counts, corners and seed. Manual edits show Custom; moving the slider restores a complete preset while retaining bounds and roles. After the first accepted take, the sticky lock disables planning edits even if captures are subsequently cleared. Locked copy tells the user to continue with saved settings; the handle and groove visibly gray out. A separate project requires an empty directory and retains prior source files.

### Physical knob target

Read-only dial drawings show orientation and numbers; adjacent text names exact settings and fixed controls. Targets expose accessible name/description, and native confirmation gates recording. Selected-row rerecording uses that row's saved setting. A new target or changed selection clears confirmation. Cancellation, saved-take feedback and QA remain real engine states.

### Training and review

Training offers full, one-epoch workflow-test and custom durations, with advanced execution settings. Real process progress, metrics, log/error disclosure, stop and CPU retry provide recovery. Mutable inputs stay fixed while processes run. Runs retain configs, audio hashes, metrics and actual model exports.

Review separates export status, last logged validation ESR and per-run listening confirmation. It opens run/test folders, copies the actual model and links the compatible player. Last-epoch ESR is not a separate evaluation of the exported checkpoint. No built-in A/B player or simulated waveform is present.

## Do's and Don'ts

### Do:

- **Do** preserve native Qt control semantics and visible keyboard focus.
- **Do** keep physical targets, readiness and the next action easy to find.
- **Do** explain locked or unavailable actions with a concrete next step.
- **Do** derive counts, progress and review metrics from saved application data.
- **Do** retain separate projects and source files when capture settings change.

### Don't:

- **Don't** interpret capture coverage as a guaranteed sound-quality rating.
- **Don't** make the physical dial diagram appear interactive or automatic.
- **Don't** copy browser font loading, phone breakpoints or example metrics into native truth.
- **Don't** imply a completed export has been listened to or validated on real hardware.
- **Don't** infer Mac/CoreAudio/MPS/VoiceOver verification from Linux offscreen screenshots.
