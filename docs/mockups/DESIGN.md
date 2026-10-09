---
name: Parametric UX proposal
description: Extracted visual guidance for the synthetic capture and training mockups only.
colors:
  ink: "#252a32"
  muted: "#606773"
  line: "#e4e6e9"
  paper: "#ffffff"
  canvas: "#eceef1"
  side: "#f6f7f9"
  primary: "#175cd3"
  primary-hover: "#124db5"
  primary-soft: "#eaf1fe"
  success: "#27624c"
  success-soft: "#eef6f1"
  caution: "#925517"
  caution-soft: "#fff6e8"
  error: "#af3537"
  error-soft: "#fff0ee"
typography:
  headline:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "27px"
    fontWeight: 670
    lineHeight: 1.25
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "15px"
    fontWeight: 650
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "12px"
    fontWeight: 550
  knob-value:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "30px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.03em"
rounded:
  badge: "5px"
  field: "6px"
  control: "7px"
  container: "8px"
  target: "10px"
  window: "13px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "8px 10px"
  badge:
    backgroundColor: "{colors.side}"
    textColor: "{colors.muted}"
    rounded: "{rounded.badge}"
    padding: "5px 9px"
---

# Design System: Parametric UX proposal

## Overview

This document applies only to [the HTML interaction proposal](index.html) and [its overview](overview.html). [Root DESIGN.md](../../DESIGN.md) remains the authority for the native Python/Qt production application. These extracted tokens record what the proposal uses; they do not approve a replacement production identity. There is no approved raster composition or QUALITY BAR reference.

The proposal uses a familiar light desktop utility appearance: quiet surfaces, blue actions, compact labels and clear state messages. Its reusable signature is the large physical knob target, with a numerical position and an explicit confirmation before recording. The dial indicates where to turn the real pedal; it is not an interactive software control or an automatic knob actuator.

**Key Characteristics:**

- The physical task and next action lead; queue, readiness and saved progress support them.
- Error recovery keeps the user's task context visible.
- Example hardware, measurements, training and artifacts are explicitly synthetic.

## Colors

### Primary

Action Blue drives the principal enabled action, current stage, numerical progress and dial pointer. Its pale companion supports informational notices. Hover darkens the action without changing its meaning.

### Neutral

Paper is the working surface; Canvas frames the review artifact; Side separates navigation and modest supporting panels. Ink carries primary text; Muted carries descriptions and secondary status; Line divides sections and table rows.

### Status

Success green indicates an example check or saved take. Caution amber calls attention to missing hardware or the worst example review result. Error red identifies a recoverable failure. Each has a pale notice background. Visible text and icons accompany these colors.

**The State Meaning Rule.** Retain the same color meaning across setup, capture, training and review. A completion color must not imply that a model has been listened to or validated.

## Typography

The proposal loads the local Inter variable font from [assets](assets/InterVariable.woff2), with platform sans-serif fallbacks. This is a browser approximation; production retains system typography under the root design guidance.

Headlines establish the current task. Section titles organize dense utility content. Most descriptions, table content, controls and supporting labels use compact text (12px), while the body base is larger. Knob positions are the prominent numerical readout; tabular numerals also stabilize counts, settings and metrics. Diagnostic logs use a system monospace stack (12px, line height 1.8).

At the smallest breakpoint, the stage labels are reduced (11px) and headlines step down (24px). The overview's larger heading is presentation chrome, not the standard application headline. These values describe the proposal, not verified macOS font scaling.

## Layout

The browser window approximation has a maximum width (1296px), a project titlebar, a persistent stage sidebar and a main working region. The desktop sidebar is narrow (208px); the main region uses comfortable insets (33px 38px 26px). Supporting regions pair with the main task in two columns; capture reserves the larger region for knob targets and the recording action.

Observed responsive breakpoints are 1440px, 1350px, 1050px, 850px and 480px. Below 850px, navigation becomes a horizontal stage row, supporting regions stack and buttons grow vertically. Below 480px, setup selectors stack. The Plan table deliberately retains a readable internal minimum width (600px), with a first column (160px), inside its own horizontal scroller. Page overflow and internal table scrolling are distinct checks.

The 390px screenshots allow compact inspection of a desktop proposal. They do not establish a phone product, a supported production Qt minimum width or native touch-target compliance.

## Elevation & Depth

Depth primarily comes from pale surfaces, borders and spacing. The outer mock window uses an ambient shadow (`0 16px 45px #27344d1c`); the selected preset has a small shadow (`0 1px 4px #202b4020`). These separate the browser review frame and selected control; they do not establish native macOS window fidelity.

Progress updates immediately without animating layout properties. Training curves and waveforms illustrate state only; they are not measured device outputs.

## Shapes

Small rounded rectangles organize buttons, fields, notices and tables. Larger corners mark the capture target and outer review window. The dial's circular silhouette is reserved for the physical pedal instruction. Hairline borders keep related controls legible without wrapping every section in an elevated card.

## Components

### Buttons

Blue filled buttons express the main available action. Bordered buttons express secondary navigation or recovery. Standard buttons have a minimum height (38px), rising in compact layouts (42px); the capture action spans its target container with additional height (43px). Disabled states use gray surface, border and text. A visible focus outline (3px, offset 3px) covers buttons, links, fields, selectors and disclosures.

### Inputs / Fields

Visible labels name native browser selectors and text/number inputs. Physical range edits preserve focus on re-render and report invalid values. Routing edits invalidate the earlier simulated route check. Production must translate these contracts into native labels, validation and accessibility behavior.

### Navigation

Connect, Plan, Capture, Train and Review form a persistent task sequence. The active stage has a pale blue surface, stronger text and a blue numbered marker on desktop. The compact row retains stage names and hides secondary descriptions. Navigation deliberately keeps example state during the current page session.

### Notices / Badges

Notices explain a cause and next step in task language. Badges give short state labels; they supplement the action and message rather than carry readiness alone. Advanced settings and diagnostic logs stay available through disclosures.

### Physical knob target

Each Drive/Tone target pairs a circular orientation diagram with a prominent number, range bounds and physical-position label. The user confirms both real controls before Record becomes available. Accepting a take advances the target and clears that confirmation. Cancellation preserves the target and saved count. A clipped example retains its exact target for retry; changing gain starts a separate calibration example.

### Training and review

Presets distinguish a one-epoch setup test from a candidate-model run. Example progress shows only epochs already reached. Setup-test completion routes to full training; exported-candidate completion routes to review. Review displays held-out examples, the worst example error, listening checks and the compatible-player requirement. The A/B panel is a future interaction preview without audio playback. Download creates a labeled JSON example with no trained weights.

## Do's and Don'ts

- **Do** keep the real physical target and current action easy to find.
- **Do** show why an action is unavailable and how to become ready.
- **Do** preserve prior captures and separate changed calibration from the original session.
- **Do** retain standard native Qt control semantics when implementing the production proposal.
- **Do** label every synthetic measurement and artifact clearly.
- **Don't** infer real hardware readiness, Mac accessibility, MPS availability or model quality from the mockup.
- **Don't** treat navigation continuity in this in-memory prototype as durable reload/session persistence.
- **Don't** promote these browser token values over the incumbent root design without a separately scoped production decision.
