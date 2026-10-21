# UX redesign: "Console" theme and a five-page flow

Date: 2026-10-17
Status: approved by the user on 2026-10-17

Approved mockups (the visual reference for this document):

- `docs/design/2026-10-17-ux-redesign/visual-direction.png` — three styles. The user chose **C · Console**.
- `docs/design/2026-10-17-ux-redesign/flow.png` — two flows. The user chose **A · Five pages, one job each**.
- `docs/design/2026-10-17-ux-redesign/pages-start-gear-connect.png` (+ `.html`) — Start, Gear, Connect.
- `docs/design/2026-10-17-ux-redesign/pages-record-train-listen.png` (+ `.html`) — Record, Train, Listen.

The HTML files load fonts from Google Fonts. They are review artifacts only. The app must not load anything from the network. The PNG files are the reference: `visual-direction.html` and `flow.html` need the brainstorm frame (`.option` styles, `toggleSelect`), so they look broken when opened alone.

**Where a mockup and this document differ, this document wins.** Do not copy this mockup text word for word:
- Window 3b tells the user to turn the reamp box down and shows a **Check level** link (see 4.3, "A clipped take").
- Listen says "the model never heard these" (see 4.5 and 6.2).
- The Train cards show "~2 min / ~25 min" (see 4.4).
- The Start page shows "Rat 2 · Training 61%" (see 4.0b: saved state only).
- The Fast and Max cards show 12 and 96 takes (see 4.3: computed values).

## 1. Intent and the why

The user felt lost in the current app. Each screen shows many options at the same time, and the words are technical ("epochs", "architecture", "ESR", "held-out"). The current app also drifted from the approved mockups: Connect holds the project setup, the controls editor, and the channel numbers; Train has three buttons with no clear order; Review shows raw run IDs and paths.

The user wants a **generic, open-source** app that works with **any sound card**, not only the UMC22. The app must be **clear first** and **exciting to look at**. Users have different skill levels, so the default path must be very simple, and expert options must stay available but out of the way.

Success: a new user opens the app and always knows the next step. Each page asks for one main thing and has one main button.

## 2. Goals, non-goals, anti-goals

**Goals**

- A new five-step flow: **Gear → Connect → Record → Train → Listen**, plus a **Start** page.
- A new "Console" visual style (graphite surfaces, one lime accent), in dark and light, with an appearance switch.
- One main job and one main button on each page. All expert settings go behind one "Expert settings" disclosure on each page.
- Plain words in the main path. Technical words appear only in Expert settings.
- Three new features (approved by the user):
  1. **Find my connection** — the app finds the output and input channels for any sound card.
  2. **Match per test setting** — on Listen, each held-out setting shows how close the model is.
  3. **Playback** — on Listen, the user can play the saved test recordings.

**Non-goals**

- No new platform. The app stays a native Python + PySide6 desktop app.
- No change to the capture engine, the planner, the trainer, or the export formats.
- No signed installer.

**Anti-goals (a failure even if it works)**

- A page that shows more than one main button.
- A control that disappears with no stated reason (see section 5).
- Simpler words that are no longer true. The honesty rules in `PRODUCT.md` stay: coverage is not sound quality; a metric does not prove a good sound; the user must listen.
- Old projects that do not open any more.

## 3. Constraints

- Stack: Python 3.11–3.13, PySide6, the pinned upstream `nam.capture` package in `.upstream`. `MacWindow` subclasses the upstream `MainWindow`. Upstream widgets (for example `device_combo`, `route_test_button`, the channel spin boxes) must keep working, even when they are hidden.
- The user's coding rules: files of 200–400 lines, 800 maximum; functions under 50 lines; immutable data; explicit error handling; TDD with 80% coverage. `parametric_mac/gui.py` has 1549 lines now. It must be split (see section 8).
- Fonts load locally. Bundle **Geist** and **Geist Mono** (SIL OFL) as TTF files with their license in `parametric_mac/ui_assets/`, the same way as Inter now. Update `FONT-SOURCE.md` and `pyproject.toml` package data if needed.
- Remove every hard-coded UMC22 text from the UI: the route labels, the wiring note, and the loopback note ("Keep both routes on the UMC22"). The hardware guides in `docs/` can stay as examples.
- Project rules that stay the same: a project needs an empty folder; the plan and the gear lock after the first accepted take; a reopened project needs a new connection check before it records; one window per project during recording or training.

## 4. The design, page by page

### 4.0 Shell (all pages)

- **Top bar:** app name with a small lime dot on the left. In the center, the step bar: `1 Gear · 2 Connect · 3 Record · 4 Train · 5 Listen`. Done steps show a check mark. The current step is lime. On the right, the project name. The step bar is clickable, as the sidebar is now.
- The old left sidebar goes away. The old status bar ("0 of 40 recordings saved", "NAM engine v1.2.0") goes away. The engine version moves to an "About" item in the app menu.
- **Footer:** one short status text on the left, one main button on the right (lime, filled). Secondary actions are text links or outline buttons, never a second filled button.
- During a job (recording or training), the user can still click other steps. Controls that change the job inputs are disabled, as now.
- Visual tokens (from the mockups): background `#101317`, side panel `#0c0f12`, raised surface `#161b21`, lines `#222830` / `#2a313b`, text `#e3e8ee`, muted text `#7f8a97`, accent `#d4ff4f`, OK `#8de07a`, warning `#ffb547`, record/error `#ff4d4d`. Numbers use Geist Mono with tabular figures.
- **Light and dark (user decision):** by default the app follows the macOS light/dark setting and changes live when the setting changes.
- **Appearance switch (user decision):** a small appearance icon button at the right end of the top bar (next to the project name) opens a menu with three choices: **Match macOS** (default), **Light**, **Dark**. The same three choices are in the app menu under View → Appearance. The choice applies at once, with no restart, and is saved in `QSettings`. Do not use a sun/moon toggle: it cannot express "Match macOS".
- **Light tokens:** the dark tokens above are the approved design. The light version has no approved mockup yet. Starting tokens (provisional): background `#f4f5f2`, side panel `#ebede8`, raised surface `#ffffff`, lines `#d9dcd5` / `#c9cdc4`, text `#14171b`, muted text `#5f6873`, accent fill `#d4ff4f` with dark text `#14171b` on it, accent for text and outlines `#4d6400` (lime text on a light background fails contrast), OK `#2f7a24`, warning `#9a5b00`, record/error `#d42c2c`. All text must meet WCAG AA contrast in both modes. Keep all colors as theme tokens; no color literals in page code. Before Phase 1 ends, render every page in light mode and show the screenshots to the user for approval.

### 4.0b Start page (new)

Mockup: `pages-start-gear-connect.png`, window 0.

- Left: a short headline, a one-sentence description, the **New capture** button (main), and **Open folder…** (outline). A small line says what the user needs (sound card, reamp box, gear, about 45 minutes).
- Right: **Continue where you stopped** — the recent projects list. Each row shows the name, the saved state, and a tag: `Continue` (recording not complete), `Ready` (a model exists), or `Trained` / `Stopped` from saved run state.
- Show only saved state. Do not show a live training percent for a project that is not open in this window.
- A project whose folder is missing shows "Folder not found" and a **Remove from list** link.
- **Persistence:** keep the recent list in `QSettings` (path, display name, last opened time). Read the status from the project files each time the list shows.
- **Open folder…** opens any existing project folder, including old projects. This keeps the README promise.
- **Continue** on a project opens the **Connect** page if the project needs a new connection check (always after reopen, see 4.2). Otherwise it opens the first step that is not done.
- The window opens on Start when no project is open. `Train.command` still opens the app; it opens Start, and the user picks the project.

### 4.1 Gear

Mockup: window 1.

- Title: "What are you capturing?" Sub-title: add only the knobs you want to turn later.
- **Name** field and a **Pedal / Amp** segmented control.
- **Knobs and switches to capture:** each control is a tile with a small knob or switch icon, its name, and its range (knobs) or position names (switches). A × on the tile removes it. Tiles `+ Knob` and `+ Switch` add one. A click on a name or range opens the existing range / position editor (reuse `control_editor.py` logic).
- **Other controls stay where they are:** the existing "Keep fixed" text field.
- Right panel: a drawing of the gear that updates when the user adds or removes controls (fixed controls are dimmed). Below it, the live effort estimate for the **Good** level: "~N recordings · ~M min to record" from `quality_settings` and `recording_minutes`.
- **Pedal / Amp toggle:** it sets the gear type (this changes the wiring on Connect). If the control list is still the untouched starter list, the toggle also swaps in the other starter (Pedal: Drive + Tone; Amp: six knobs + Bright). If the user changed the list, the toggle does not touch it. *(Builder's call recorded here; the old "Pedal starter" / "Amp starter" buttons go away.)*
- **Footer:** "Saved in `~/Music/Parametric/<name>` · Change". Main button: **Next: Connect →**. The project folder is created when the user presses Next.
  - Default folder: `~/Music/Parametric/<name>`. If that folder exists, use `<name> 2`, `<name> 3`, and so on. A folder from "Change" must be empty, as now; if not, show an inline error.
- **After the first accepted take:** Gear is read-only. A note says: "Locked after the first take. Your recordings depend on these controls." A link **Start a new capture with these controls** creates a new project with the same gear (this replaces "Create a separate project").

### 4.2 Connect

Mockup: window 2. Three stages, top to bottom. Each stage shows a check mark when done. The footer button **Next: Record →** is enabled only when all three are done.

**Stage 1 · Wire it up**
- A horizontal cable chain drawing.
  - Pedal: Sound card output → Reamp box → Pedal (In → Out) → Sound card input.
  - Amp: Sound card output → Reamp box → Amp input; Amp speaker output → Load box → Sound card input. A warning, before the chain: "Never connect the amp's speaker output to the sound card. Use a load box." (From `docs/hardware-amps.md`.)
- One checkbox: "Monitoring is off and speakers are unplugged from the sound card." This replaces the old three checkboxes. The level check (stage 3) replaces the "headroom" checkbox. The "gear is connected and powered" item moves to the right panel list.

**Stage 2 · Find the connection**
- The sound card dropdown (the upstream `device_combo`) with a small refresh icon (replaces "Refresh interfaces"). Next to it: the current sample rate, for example "48 kHz".
- **Find my connection** button (outline). It is enabled only after the stage 1 checkbox is on, because it sends sound out of outputs the user did not pick.
- **How Find works:** for each output channel of the device, one at a time, play the upstream route-test click preamble (`build_playback` with empty audio) at a **reduced level** (see 6.1), and record **all** input channels at the same time. Detect the clicks on each input with the same detection the route test uses. Stop at the first output that gives a clean result. This needs a small new helper in this repo (the upstream recorder takes one input channel). It must support cancel and progress, and run in the existing worker pattern.
- **Result:** "Found: Output X → Input Y." Then the app sets the upstream output and input channel values and saves them in the project audio settings.
- **States:**
  - *No device:* "No sound card found. Plug it in, then press refresh." Blocks Next.
  - *Sample rate is not the rate of the input files (48 kHz):* "Your sound card runs at 44.1 kHz. Set it to 48 kHz in Audio MIDI Setup, then press Find again." Add a button **Open Audio MIDI Setup**. Blocks Next.
  - *No signal found:* "No signal came back. Check the cables, and check that the reamp box and the pedal have power." Buttons: **Try again**, link **Choose channels myself** (opens Expert settings).
  - *Signal on more than one input:* pick the input with the highest clean peak, and say so: "Found on inputs 1 and 2. Using input 1 (louder). Change". Ignore the loopback channels if the loopback is on.
  - *Too close to clipping:* reuse the current message ("Signal is too close to clipping…").
- **Phase 1 fallback:** before Find exists (section 9), stage 2 shows the device dropdown and the two channel numbers with plain labels: "Output channel (where the cable to the reamp box starts)" and "Input channel (where the cable from the pedal comes back)".

**Stage 3 · Check the loudest level**
- Text: "Turn every knob on the pedal to its loudest setting. Then press Check."
- A horizontal level meter (green to −18 dB, yellow to −6 dB, red above).
- **Check level** button. This runs the existing upstream route test on the found channels. It uses the returned `peak` for the meter.
- OK result: "Peak −9 dB · good. Do not touch the sound card gain from now on." This sets the same "connection tested" state that the old **Test connection** set.
- Bad result: show the current route-test messages in plain words, with **Check again**.

**Right panel:** "What you need" (sound card with one output and one input; reamp box; the gear's own power supply; for Amp: a load box). At the bottom: **Show me how to fix it** (opens a short help text or the hardware guide) and **Expert settings ▸**.

**Expert settings (Connect):** output channel, input channel, timing loopback (on/off, loopback output and input channels), buffer size, stream latency. Same widgets as now.

**Reopen rule:** for a reopened project, stages 1 and 2 show the saved device and channels, but the stage 1 checkbox is off and stage 3 is not done. The user must confirm and run **Check level** again before recording. This keeps the current safety rule.

### 4.3 Record

Mockups: windows 3a and 3b.

**First visit (before the first accepted take):** "How detailed should the capture be?" Three cards: **Fast**, **Good** (Recommended, selected), **Max**. Each card shows the take count and the minutes from `quality_settings` and `recording_minutes`, and one sentence. Text: "You cannot change this after the first take." Main button: **Start recording →**.

- Mapping to the current `QUALITIES` tuple (my call): **Fast = "Quick test" (index 0)**, **Good = "Good" (index 2)**, **Max = "Thorough" (index 3)**.
- **Expert settings (Record):** "More levels" (Decent, Overkill), the manual counts (training settings, test settings), the seed, and corners. Same logic as the current Plan "Advanced" section.
- Old projects: `workflow.json` keeps the stored index. A locked project with index 1 or 4 shows that level's name ("Decent", "Overkill") on the locked card. No data migration is needed.
- The 12 / 40 / 96 numbers in the mockup are placeholders. Use the computed values.

**Recording loop:**
- Left: "SETTING 19 / 40", title "Set your pedal like this", the target controls, the **Record** button (outline lime with a red dot), "or press Space".
- **Target controls layout:** up to 4 controls in a row. Size: large (104 px) for 1–2 controls; medium for 3–6; a compact grid of small tiles for 7–24. A switch shows its position name in large text with a switch icon (for example "Bright · ON"). Controls that changed since the last take get a lime "Changed" mark, so the user turns only those. *(The "Changed" mark is my call.)*
- The old checkbox "The knobs and switches match these positions" goes away. Pressing **Record** is the confirmation. *(My call: the checkbox added a click to every take. The "Changed" mark and the large values do the same job.)*
- During a take: the Record button becomes **Cancel** (replaces the always-visible "Cancel recording").
- **After a take:** the QA result shows in the right panel ("Good take" or the problem). A failed take shows a red box with a plain instruction, and the button becomes **Record again**. Map each current QA flag to a plain message.
- **A clipped take (correction to mockup 3b).** The levels stay fixed for the whole project, as now. The app must **not** tell the user to change the reamp box or sound card level during recording, and Record has no **Check level** link. Mixed levels would put different-sounding takes in one dataset. The message is: "This take clipped. Record it again. If it clips again, the level is too high for this pedal. Start a new capture and set a lower level on Connect." with **Record again** and the link **Start a new capture with these controls** (see 4.1). The take stays saved with its QA flag, as now.
- Right panel: progress bar, "About N minutes left · saved after every take", last-take bars with the result tag, and **Up next** (two settings).
- **All takes ▸** opens the full queue. Select a row, then **Record this one again**. This replaces "Queue and recording details" and the "Advanced capture tools".
- When all takes are done: "All 40 takes are saved." Main button: **Next: Train →**.

### 4.4 Train

Mockups: windows 4a and 4b.

**Before:** title "Train your model". Two cards: **Quick test** ("Checks that everything works. The model will not sound good yet.") and **Full training** (Recommended; "The real model. Makes a Standard and a Nano size in one file."). Main button: **Start training →**.

- Do not show time estimates on the cards: the app has no estimate before a run. Show the size of the job instead ("1 round" / "200 rounds per size"). After training starts, show "~N min left" from the measured epoch time. *(This replaces the "~2 min / ~25 min" in the mockup.)*
- **Check and train are one action.** **Start training** first runs the existing recording check, then trains. If the check fails, training does not start, and the page shows a red box with the check problems in plain words and a link **Go to Record** (for missing or bad takes).
- Recording not complete: the cards are disabled and the text says "Finish recording first: 18 of 40 takes saved." with a link **Go to Record**.
- **Expert settings (Train):** model type (the 7 entries of `ARCHITECTURES`, default "NAM A2 · Standard + Nano"), custom number of epochs, device (Automatic / Apple GPU / CPU), batch size, **Training log**.
- Wording: the main path says "rounds", not "epochs". Expert settings say "epochs (rounds)".

**While it runs:** title "Training · Standard size", "Step 1 of 2. The Nano size comes next." (only for dual models). Stats: percent done, minutes left, rounds done. A progress bar. A line chart "Difference from the real pedal, on test settings — lower is better". It plots the validation value from each "Epoch N finished. …" log line. **Stop training** (outline).

- **Failure:** a red box with a plain message. For GPU or memory errors: "Training stopped: not enough graphics memory. Your recordings are safe." Button **Try again on CPU** (the current retry, which also sets batch size 1). Link **Show log**.
- When done: go to Listen automatically, or show "Your model is ready" with **Next: Listen →**. *(Builder's call.)*

### 4.5 Listen

Mockup: window 5. Title "Your model is ready". Sub-title: "Listen to it before you share it. A good number does not always mean a good sound."

- **Model file card:** the file name (project name + `.nam`), the type, the controls, the training time, and the main button **Save model…** (copies the real `model_parametric.nam`, as now).
- **Test settings table** (the held-out settings): label "Test settings — not used to train the model". One row per setting with the control values, a **Match** column, and play buttons.
- **Right panel:** "Use it in a player" (Ardor; the normal NAM player cannot open it), **How to load it ▸** (Ardor steps; NamParametricPlugin link for concat exports — this replaces "Get concat player"), the listening checklist (two checkboxes), and at the bottom **Earlier models ▸** and **Open project folder**.
- The listening status is saved per run, as now. The run counts as "listened" when both checkboxes are on.
- **Earlier models ▸** lists older runs with date, model type, status, and **Open run folder**. This replaces the run-ID dropdown. The newest run with an export is the default.
- **Expert settings (Listen):** last logged validation ESR per size, with the current honest text ("last epoch, not a fresh evaluation"), and the per-setting ESR numbers.

## 5. Control disposition table

| Current control | New place | Reason |
|---|---|---|
| Header **New project** / **Open project** | Start page: **New capture**, **Open folder…** | One place to start or continue. |
| Sidebar steps | Top step bar | Same function, less space. |
| Sidebar "No job running" / status bar | Footer status text; engine version in About | Less noise. |
| Name, Gear type, Keep fixed | Gear | Gear facts belong together. |
| Controls editor (add knob, add switch, remove, range / position editor) | Gear tiles | Same logic, new look. |
| Pedal starter / Amp starter buttons | Pedal / Amp toggle on Gear | One control in place of three. |
| Audio interface dropdown | Connect stage 2 | — |
| Refresh interfaces | Small refresh icon next to the dropdown | — |
| Send · output / Return · input numbers | Connect Expert settings (Phase 1: stage 2 with plain labels) | Find my connection sets them. |
| Signal route list (UMC22 rows) | Cable chain drawing, generic | Remove UMC22 text. |
| Three "Before audio starts" checkboxes | One checkbox + level check + "What you need" list | Fewer clicks; the level check replaces the headroom checkbox. |
| Test connection | **Check level** (stage 3) | Same route test, clear purpose. |
| Loopback, buffer size, stream latency | Connect Expert settings | Expert only. |
| Quality slider (5 levels) | Record first visit: 3 cards; Decent and Overkill in Expert | Fewer choices. |
| Manual training / test counts, seed, corners | Record Expert settings | Expert only. |
| View saved capture plan | Record **All takes ▸** | One list. |
| "Knobs and switches match these positions" checkbox | Removed | Record is the confirmation; "Changed" marks help. |
| Record this setting | **Record** / **Record again** | — |
| Cancel recording | Shows only during a take | — |
| Queue and recording details; Advanced capture tools | **All takes ▸** with **Record this one again** | — |
| Continue to training | **Next: Train →** | — |
| Model architecture | Train Expert settings | Good default exists. |
| Full / Quick / Custom segments | Two cards; custom epochs in Expert | — |
| Advanced training settings (device, epochs, batch) | Train Expert settings | — |
| Check recordings | Part of **Start training** | One action. |
| Start training / Stop training | **Start training →** before; **Stop training** during | Only one shows at a time. |
| Retry on CPU | **Try again on CPU** in the failure box | — |
| Training log and errors | **Show log** (failure box) and Train Expert | — |
| Review saved runs | **Next: Listen →** | — |
| Run selector dropdown | **Earlier models ▸** | Newest run is the default. |
| Open run folder | Earlier models list and **Open project folder** | — |
| Open test recordings | ▶ play buttons (Phase 4); file access in Listen Expert | — |
| Get concat player | **How to load it ▸** | — |
| "I listened and checked unseen settings" | Two-item listening checklist | Same saved status. |
| Save model… | Main button on Listen | — |

## 6. The three new features

### 6.1 Find my connection
See 4.2, stage 2. Safety rules:
- Enable it only after the "monitoring off and speakers unplugged" confirmation.
- **Level (my call):** the upstream route-test clicks use `DEFAULT_BLIP_AMPLITUDE = 0.9` (about −1 dBFS). Find sends sound to outputs the user did not pick, so it plays the clicks at **−20 dBFS**. First, test with synthetic signals that the upstream click detection still works at that level. If it does not, use the lowest level that works, and write the level and the reason in the code. Never exceed the route-test level.
- **Reject false matches (my call):** a digital loopback input (inside many sound cards) returns a near bit-exact copy of the output. The main test: gain-match the return to the sent signal (after delay alignment) and compute the residual. If the residual is very small (for example −80 dB or lower relative to the signal), mark the input as a loopback. A real path through the converters, a reamp box, and a pedal always adds noise and filtering. Delay and level are hints only, never the reason to reject: a digital loopback also passes through the driver buffers, and a clean boost pedal can return near the sent level. Show rejected inputs in Expert settings as "Input N looks like a loopback — ignored". Put the threshold in one named constant, and test it with synthetic signals (an exact copy, a copy with noise and filtering).
- Play on one output at a time.
- The user can cancel at any time.

### 6.2 Match per test setting
- After training (and for an old run, on request with a **Check match** link), run a new **evaluate** job in a separate process, like the check and train jobs. For each held-out setting, it runs the exported model on that setting's input audio and computes the ESR against the saved capture. For dual exports, evaluate each size.
- Save the results in the run folder (for example `match.json`), so Listen does not compute them again.
- Display (provisional thresholds, marked in code as provisional and in one place): ESR ≤ 0.01 → "Close" (3 bars); ≤ 0.05 → "Fair" (2 bars); > 0.05 → "Check by ear" (1 bar, warning color). Show the Standard size by default. Expert settings show both sizes and the numbers.
- The text near the table stays honest: "A good number does not always mean a good sound."
- **Honesty note (my call):** the trainer uses the held-out settings to pick the best checkpoint (`monitor="val_loss"` in `.upstream/nam/train/parametric.py`). So these settings are not fully unseen, and the Match values are a little optimistic. Do not write "the model never heard these". Use "not used to train the model". Listen Expert settings add one line: "These settings also chose the best training round, so the match can look better than on new settings." The trainer stays unchanged (section 2).
- If evaluation is not possible (for example, the export type is not supported by the evaluation code), the Match column shows "—" and the reason in Expert settings.

### 6.3 Playback
- ▶ **Real pedal** plays the saved held-out capture for that row (the 7-second validation capture, 48 kHz).
- ▶ **Model** plays the model's output for the same setting (user decision). `evaluate.py` (Phase 3) saves this audio in the run folder next to `match.json`, for each test setting and each size. Listen plays the Standard size by default; Expert settings can switch to Nano. Before Phase 3 exists, the ▶ Model button does not show.
- Both clips play at the same playback gain with no normalization, so the comparison is fair.
- **Playback device (user decision):** a small "Play through" picker on Listen, with the output devices from Qt Multimedia (`QMediaDevices`). The default is the Mac's built-in output (or connected headphones), never the capture device. If the user picks the capture device, show a warning: "This sound card also feeds your reamp box. You may hear nothing, and the sound goes into the pedal." Save the choice in `QSettings`.
- Use Qt Multimedia (part of PySide6), so no new dependency is needed.
- One sound plays at a time. A second click stops it.

## 7. States and errors summary

Each page must define: empty state, working state, done state, and error state. The required error messages are listed in section 4. All error text is plain, says what happened, and says what to do next. No "Oops", no exclamation marks.

## 8. Code structure

- Split `parametric_mac/gui.py` into a package, for example:
  - `parametric_mac/ui/window.py` — `MacWindow` (subclass of the upstream `MainWindow`), the shell, navigation, job state.
  - `parametric_mac/ui/shell.py` — top step bar, footer.
  - `parametric_mac/ui/pages/start.py`, `gear.py`, `connect.py`, `record.py`, `train.py`, `listen.py`.
  - `parametric_mac/ui/widgets/` — knob drawing, tiles, cards, level meter, chart, alert box.
  - `parametric_mac/recent.py` — the recent projects registry.
  - `parametric_mac/find_route.py` — the Find helper (no Qt).
  - `parametric_mac/evaluate.py` — the per-setting match (no Qt), with a CLI entry like the check and train jobs.
- Keep `gui.py` as a thin import shim if launchers or tests import from it.
- Rewrite `theme.py` for the Console tokens and Geist fonts.
- Keep upstream widgets alive and hidden where the new UI does not show them.

## 9. Phases (one spec, four deliveries)

1. **New flow and theme on the current features.** Start, Gear, Connect (with the Phase 1 channel fallback), Record, Train, Listen; the Console theme in dark and light (light tokens from 4.0); the appearance switch (Match macOS / Light / Dark); light-mode screenshots of every page, approved by the user; the Geist fonts; the code split; the control table in section 5; the recent list; the default folder; the quality mapping. This phase fixes "I got lost" by itself.
2. **Find my connection.**
3. **Match per test setting.**
4. **Playback.**

Each phase ends with passing tests and fresh screenshots.

## 10. Tests, scripts, and docs

- Follow TDD and the 80% coverage rule for new non-Qt modules (`recent.py`, `find_route.py`, `evaluate.py`, the quality mapping).
- Update `tests/test_gui.py` for 6 pages, the new controls, and the quality mapping (for example `quality_slider.value() == 2` becomes a check on the selected card).
- Update `tests/test_quality.py` if the mapping changes any expected value.
- Add tests for: the appearance switch (the saved choice is restored at start, and a change applies at once with no restart), the reopen rule, the lock after the first take, the Pedal/Amp starter swap rule, the default folder naming, the Find result parser (with recorded synthetic signals), the Match thresholds, and the training-log chart parser.
- Update `scripts/render_native.py` for the new pages and states. Retire or retarget `scripts/verify_mockups.py` (it checks the old HTML mockups).
- Update `README.md` (the flow is now Gear → Connect → Record → Train → Listen), `PRODUCT.md`, and `DESIGN.md` (Console tokens, Geist).
- Mark `docs/mockups/` as superseded by `docs/design/2026-10-17-ux-redesign/`.

## 11. Left to the builder

- Exact spacing, sizes, and animation, inside the mockup style.
- The exact plain-language text for each QA flag and check problem.
- Whether Train goes to Listen automatically when done.
- How Find detects clicks on many inputs, as long as it reuses the upstream detection logic where possible.

## 12. Decisions from the user (builder check round)

1. ▶ **Model** playback on Listen: **yes** (section 6.3).
2. Listen playback device: **a "Play through" picker with a safe default** (section 6.3).
3. Theme: **follow the macOS light/dark setting** (section 4.0). The light version needs user approval of screenshots before Phase 1 ends.
4. Add a **light/dark switch** with Match macOS / Light / Dark (section 4.0, user request at approval).

## 13. Calls made by the designer (check these)

- Pedal/Amp toggle swaps the starter controls only if the list is untouched (4.1).
- Default folder `~/Music/Parametric/<name>` with a number suffix (4.1).
- Quality mapping: Fast = Quick test, Good = Good, Max = Thorough; Decent and Overkill in Expert (4.3).
- The "positions match" checkbox is removed; a "Changed" mark shows which controls to turn (4.3).
- A clipped take does not allow a level change; the user records again or starts a new capture (4.3).
- No time estimates on the Train cards before a run (4.4).
- Find plays at −20 dBFS and rejects an input as a loopback only when the return is a near bit-exact copy (residual test) (6.1).
- Test settings text: "not used to train the model", with an Expert note about checkpoint selection (6.2).
- Provisional Match thresholds: 0.01 and 0.05 ESR (6.2).
- Light-mode color tokens (4.0).
