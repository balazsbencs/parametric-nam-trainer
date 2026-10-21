---
name: Parametric Console
description: A dark-first desktop app for capturing physical gear and training a controllable model, with a matching light theme.
colors:
  dark:
    bg: "#101317"
    panel: "#0c0f12"
    raised: "#161b21"
    line: "#222830"
    line-strong: "#2a313b"
    text: "#e3e8ee"
    muted: "#7f8a97"
    accent-fill: "#d4ff4f"
    on-accent: "#101317"
    accent-text: "#d4ff4f"
    ok: "#8de07a"
    warn: "#ffb547"
    danger: "#ff4d4d"
    hover: "#1d232b"
    accent-surface: "#2a3312"
    ok-surface: "#18251a"
    warn-surface: "#2e2414"
    danger-surface: "#1e1414"
    danger-border: "#5a2a2a"
  light:
    bg: "#f4f5f2"
    panel: "#ebede8"
    raised: "#ffffff"
    line: "#d9dcd5"
    line-strong: "#c9cdc4"
    text: "#14171b"
    muted: "#5f6873"
    accent-fill: "#d4ff4f"
    on-accent: "#14171b"
    accent-text: "#4d6400"
    ok: "#2f7a24"
    warn: "#9a5b00"
    danger: "#d42c2c"
    hover: "#e7eae3"
    accent-surface: "#eef6cf"
    ok-surface: "#ebf5e7"
    warn-surface: "#f8ecd6"
    danger-surface: "#fdf1f1"
    danger-border: "#efb4b4"
typography:
  ui: { family: "Geist", weights: [400, 500, 600] }
  numbers: { family: "Geist Mono", weights: [400, 500], features: [tnum] }
  sizes: { body: 13, muted: 12, section: 13, title: 28, level-number: 28, value-large: 32 }
rounded: { control: 7, card: 10, tile: 9, tag: 4, segment: 6 }
spacing: { page-margin: 38, stage-gap: 12, card-gap: 12, tile: [118, 140], tile-gap: 10 }
---

# Design System: Parametric Console

## Overview

**Creative North Star: "Your pedal, captured."**

Console is the approved redesign of 2026-10-17 ([spec](docs/superpowers/specs/2026-10-17-ux-redesign-design.md), [mockups](docs/design/2026-10-17-ux-redesign/)). It replaces the earlier light Inter utility, whose mockups remain in [docs/mockups](docs/mockups/README.md) as history. Graphite surfaces and one lime accent make the app feel like studio gear; the structure keeps it clear: a Start page, then **Gear → Connect → Record → Train → Listen**, with one job and one main button per page.

The tokens live in [`parametric_mac/ui/tokens.py`](parametric_mac/ui/tokens.py), the only file that may hold color literals; a test enforces this. [`ui/style.py`](parametric_mac/ui/style.py) builds the whole style sheet and the Qt palette from a palette, and recolors the bundled SVG icons to match.

**Key characteristics:**

- A top bar with the step bar, the project name and the appearance menu; a footer with one status line and the page's main button.
- One main job per page; everything technical sits under **Expert settings**.
- Plain words on the main path ("rounds", not "epochs"); technical words only under Expert settings.
- Painted widgets for physical things: the gear drawing, knob targets, the level meter, the cable chain and the training chart.

## Colors

Dark is the approved base. Light was approved from screenshots on 2026-10-19. The app follows the macOS setting by default; **View → Appearance** offers Match macOS, Light and Dark, and the choice applies at once without a restart.

- **Accent fill** (lime) marks the one main button, the current step, selected cards and progress.
- **Accent text** is lime in dark mode and olive in light mode, because lime text on a light background is unreadable.
- **OK, warning and danger** have a matching tinted surface for tags and alerts.
- Every text color passes WCAG AA (4.5:1) on the surfaces it sits on, in both modes ([test](tests/test_tokens.py)).

**The State Meaning Rule.** Explain readiness and recovery in words; color alone never implies a good recording, a finished model or completed listening.

## Typography

Geist for the interface and Geist Mono with tabular figures for numbers that change in place (take numbers, knob values, progress). The foundry's static files ship unchanged in `parametric_mac/ui_assets/` ([source](parametric_mac/ui_assets/FONT-SOURCE.md)); nothing loads from the network.

## Layout

- The window starts at 1140 × 840 and works down to 800 × 680. Pages scroll; the top bar and footer stay.
- Pages use a main column and, where useful, a side panel (`#aside`) for reference material: what you need, progress, how to load a model.
- Page margins are 38 px. Long project names shorten with "…" in the top bar so the bar always fits.
- Gear tiles wrap; Record targets use three sizes (large for 1–2 controls, medium for 3–6, compact for 7–24, at most 4 per row).

**The One Main Button Rule.** Each page state shows exactly one filled button; secondary actions are outline buttons or links ([test](tests/test_shell.py)).

**The Pinned Handoff Rule.** The page's next action stays in the footer, outside the scrolling content, and the page says why it is not available yet.

## Components

- **Step bar:** numbered circles; done steps show a check mark; the current step is lime. Before a project exists, only Start and Gear are open.
- **Choice cards:** title, optional "Recommended" tag, a big number with its unit, one sentence. Used for the detail level and the training mode.
- **Stages:** numbered frames on Connect that turn into a check mark when done.
- **Alert box:** a tinted box with a title, one plain instruction and its actions (Record again, Try again on CPU, Keep this take and continue).
- **Gear tiles:** a glyph, an editable name, a range link and ×; dashed tiles add a knob or a switch.
- **Painted widgets** take their palette through `Themed` and repaint when the appearance changes.
- **Runtime property changes** go through `set_style_property`, so the style sheet updates at once.

## Do's and Don'ts

### Do:

- **Do** keep one main job and one filled button per page state.
- **Do** keep native Qt semantics and visible keyboard focus.
- **Do** derive counts, times, progress and metrics from saved project data and the real planner.
- **Do** show switch position names and real dial ranges.
- **Do** explain locked or unavailable actions with a concrete next step.
- **Do** start a new capture, never change levels, when a take clips.

### Don't:

- **Don't** put a color literal outside `tokens.py`.
- **Don't** present capture coverage or a validation number as proof of a good sound.
- **Don't** write "the model never heard these": the test settings also chose the best training round.
- **Don't** load fonts or anything else from the network.
- **Don't** infer Mac, CoreAudio, MPS or VoiceOver behavior from offscreen screenshots.
