# UX Redesign Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current five-stage Qt shell with the approved Console design: a Start page, then Gear → Connect → Record → Train → Listen. Use dark and light themes with an appearance switch. Keep all current capture, check, train, and export behavior.

**Architecture:** `MacWindow` keeps subclassing the upstream `nam.capture.gui.main.MainWindow`. First, `gui.py` (1549 lines) is split into a `parametric_mac/ui/` package. Each page becomes one mixin class in its own file, so `self.<widget>` access and the existing tests keep working. Pages are addressed by a step key (`"start"`, `"gear"`, …), not by index, so that pages can be replaced one at a time. Pure logic (tokens, recent list, folder names, starter swap, quality mapping, changed controls, QA text, log parsing) lives in Qt-free modules with direct unit tests. Qt behavior is tested with the existing subprocess + offscreen pattern.

**Tech Stack:** Python 3.12 (`.venv`), PySide6 6.12 (QtWidgets, QtCore `QSettings`, QtGui `QStyleHints`), pytest 9, fontTools (build time only, for the font instances), the pinned upstream `nam` package in `.upstream`.

**Spec:** `docs/superpowers/specs/2026-10-17-ux-redesign-design.md`. Read it fully before you start a task. Mockups: `docs/design/2026-10-17-ux-redesign/*.png`. **Where a mockup and the spec differ, the spec wins** (spec, top section).

This plan covers spec **Phase 1** only (spec §9). Phases 2–4 (Find my connection, Match, Playback) get their own plans. In Phase 1, Listen shows no Match column values ("—") and no play buttons. Connect stage 2 uses the channel fallback (spec §4.2 "Phase 1 fallback").

## Global Constraints

- Run Python with `.venv/bin/python`. Run tests with `.venv/bin/python -m pytest`.
- Stack stays: Python 3.11–3.13, PySide6 `>=6.7,<7`, no new runtime dependency (spec §3).
- Files: 200–400 lines typical, **800 maximum**. Functions under 50 lines. Use frozen dataclasses or tuples for data. Type annotations on all new function signatures.
- **No color literals outside `parametric_mac/ui/tokens.py`.** All QSS and all painting take colors from a `Palette` (spec §4.0).
- Fonts load locally from `parametric_mac/ui_assets/`. The app must not load anything from the network (spec §3).
- Dark tokens (verbatim, spec §4.0): background `#101317`, side panel `#0c0f12`, raised `#161b21`, lines `#222830` / `#2a313b`, text `#e3e8ee`, muted `#7f8a97`, accent `#d4ff4f`, OK `#8de07a`, warning `#ffb547`, record/error `#ff4d4d`.
- Light tokens (verbatim, spec §4.0, provisional): background `#f4f5f2`, side panel `#ebede8`, raised `#ffffff`, lines `#d9dcd5` / `#c9cdc4`, text `#14171b`, muted `#5f6873`, accent fill `#d4ff4f` with text `#14171b` on it, accent for text and outlines `#4d6400`, OK `#2f7a24`, warning `#9a5b00`, record/error `#d42c2c`.
- All text colors meet WCAG AA (4.5:1) against the surfaces they sit on, in both modes.
- No hard-coded "UMC22" text anywhere in `parametric_mac/` (spec §3).
- One filled (primary) button per page state. Secondary actions are outline buttons or links (spec §4.0).
- Main-path copy uses "rounds", never "epochs"; Expert settings say "epochs (rounds)" (spec §4.4).
- Error text: says what happened and what to do next. No "Oops", no exclamation marks (spec §7).
- Project rules stay: an empty folder per project; plan and gear lock after the first accepted take; a reopened project needs a new level check before recording; one window per project during a job (spec §3).
- **Tests and scripts never touch the user's real settings or folders.** `MacWindow` reads `PARAMETRIC_SETTINGS_DIR` (if set, use INI-format `QSettings` in that directory) and `recent.projects_root()` reads `PARAMETRIC_PROJECTS_ROOT` (if set) at call time. `tests/gui_harness.run_gui` always sets both to fresh temporary directories.
- Coverage: the user's rule is 80%. Install `pytest-cov` in `.venv` and add it to a `[project.optional-dependencies] dev` list in `pyproject.toml` (Task 1). Pure modules (`recent.py`, `ui/tokens.py`, `ui/copy.py`, `workflow.py`, `ui/style.py` helpers) must reach 80% line coverage.
- GUI tests: one `run_gui` script per test file, with several checks in it (each run imports PySide6 and upstream again). Timeout 180 s.
- Commit messages: `<type>: <description>` (feat, fix, refactor, docs, test, chore). No attribution trailer.

## Review Focus

1. **Old projects** (created before this redesign, `workflow.json` with `quality` 1 or 4, `plan_locked: true`, `draft_controls`, `gear_kind`) must open, show the stored level name, and resume on Connect. → test in Task 6 and Task 9.
2. **Project names that are bad folder names** ("Fuzz/Face", "a:b", "  ", 300 characters, ".hidden") must give a safe default folder, never a path outside `~/Music/Parametric`. → test in Task 6.
3. **24 controls** must fit on Gear and on Record at 800×680 with no horizontal scroll. → test in Task 7 and Task 10.
4. **Appearance change during a running job** or a live macOS change must restyle at once and keep the job, the page, and the form values. → test in Task 3.
5. **Recent list entries** for a deleted folder or a corrupt `capture_project.json` must show a clear state and must not crash Start. → test in Task 6.
6. **Space pressed outside the Record page or inside a text field** must never start a recording (recording sends audio out of the sound card). → test in Task 10.

---

## File structure (end of Phase 1)

```
parametric_mac/
  gui.py                      # shim: from .ui.window import MacWindow, launch
  theme.py                    # install_typography(), icon() — fonts and icons only
  recent.py                   # NEW, Qt-free: recent-project registry + status
  ui/
    __init__.py
    tokens.py                 # NEW: Palette, DARK, LIGHT, resolve_mode, contrast_ratio
    style.py                  # NEW: build_style_sheet(palette), AppearanceController
    copy.py                   # NEW: plain-language text helpers (QA, check errors, levels)
    window.py                 # MacWindow: base wiring, mixin composition, launch()
    shell.py                  # StepBar, TopBar, Footer, STEPS, keyed navigation mixin
    jobs.py                   # JobsMixin: _start, _read_log, _finished, _stop, _retry_cpu
    project_io.py             # ProjectMixin: create/open/save details, workflow state
    widgets/
      __init__.py
      common.py               # label, button, link, disclosure, field, Card, AlertBox
      knobs.py                # KnobDial painter, GearDrawing, TargetControls
      meters.py               # LevelMeter, TrainingChart, ProgressStats
    pages/
      __init__.py
      start.py  gear.py  connect.py  record.py  train.py  listen.py
  ui_assets/  Geist-*.ttf  GeistMono-*.ttf  Geist-OFL.txt  (Inter files removed in Task 2)
tests/
  gui_harness.py              # run_gui(script) helper (subprocess, offscreen)
  test_tokens.py  test_style.py  test_recent.py  test_copy.py  test_shell.py
  test_ui_start.py  test_ui_gear.py  test_ui_connect.py  test_ui_record.py
  test_ui_train.py  test_ui_listen.py
  test_gui.py                 # kept; updated in each page task
```

Final step keys and page order: `("start", "gear", "connect", "record", "train", "listen")`.

---

### Task 1: Theme tokens and contrast

**Files:**
- Create: `parametric_mac/ui/__init__.py` (empty), `parametric_mac/ui/tokens.py`
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Palette: bg, panel, raised, line, line_strong, text, muted, accent_fill, on_accent, accent_text, ok, warn, danger: str` (hex `#rrggbb`).
  - `DARK: Palette` — `accent_fill = accent_text = "#d4ff4f"`, `on_accent = "#101317"`, other values from Global Constraints.
  - `LIGHT: Palette` — values from Global Constraints (`on_accent = "#14171b"`).
  - `Appearance = Literal["system", "light", "dark"]`; `APPEARANCES: tuple[Appearance, ...] = ("system", "light", "dark")`.
  - `resolve_mode(choice: Appearance, system_is_dark: bool) -> Literal["light", "dark"]`.
  - `palette_for(mode: Literal["light", "dark"]) -> Palette`.
  - `contrast_ratio(foreground: str, background: str) -> float` (WCAG 2.x relative luminance).
  - `TEXT_PAIRS: tuple[tuple[str, str], ...]` — field-name pairs that must pass AA: `("text","bg"), ("text","panel"), ("text","raised"), ("muted","bg"), ("muted","panel"), ("muted","raised"), ("accent_text","bg"), ("accent_text","panel"), ("on_accent","accent_fill"), ("ok","bg"), ("ok","raised"), ("warn","bg"), ("warn","raised"), ("danger","bg"), ("danger","raised")`.

- [ ] **Step 1: Write the failing tests**

```python
from parametric_mac.ui.tokens import DARK, LIGHT, TEXT_PAIRS, contrast_ratio, resolve_mode, palette_for

def test_dark_tokens_match_spec():
    assert (DARK.bg, DARK.panel, DARK.raised, DARK.accent_fill, DARK.danger) == ("#101317", "#0c0f12", "#161b21", "#d4ff4f", "#ff4d4d")

def test_light_accent_text_differs_from_fill():
    assert LIGHT.accent_fill == "#d4ff4f" and LIGHT.accent_text == "#4d6400" and LIGHT.on_accent == "#14171b"

def test_contrast_ratio_known_values():
    assert round(contrast_ratio("#000000", "#ffffff"), 1) == 21.0
    assert round(contrast_ratio("#777777", "#ffffff"), 2) == 4.48

def test_all_text_pairs_pass_wcag_aa_in_both_modes():
    for palette in (DARK, LIGHT):
        for fg, bg in TEXT_PAIRS:
            assert contrast_ratio(getattr(palette, fg), getattr(palette, bg)) >= 4.5, (palette, fg, bg)

def test_resolve_mode():
    assert resolve_mode("system", True) == "dark"
    assert resolve_mode("system", False) == "light"
    assert resolve_mode("light", True) == "light"
    assert resolve_mode("dark", False) == "dark"
    assert palette_for("dark") is DARK
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m pytest tests/test_tokens.py -q` → `ModuleNotFoundError: parametric_mac.ui`.
- [ ] **Step 3: Implement `tokens.py`.** If a provisional light token fails AA, change only that light token to the nearest passing shade, and add a comment with the spec value and the reason.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5:** Install `pytest-cov` (`.venv/bin/python -m pip install "pytest-cov>=5,<7"`) and add `dev = ["pytest>=8", "pytest-cov>=5,<7"]` under `[project.optional-dependencies]` in `pyproject.toml`.
- [ ] **Step 6: Commit** — `feat: add Console theme tokens with contrast checks`

---

### Task 2: Geist fonts

**Files:**
- Create: `parametric_mac/ui_assets/Geist-Regular.ttf`, `Geist-Medium.ttf`, `Geist-SemiBold.ttf`, `GeistMono-Regular.ttf`, `GeistMono-Medium.ttf`, `Geist-OFL.txt`
- Delete: `parametric_mac/ui_assets/Inter-*.ttf`, `Inter-LICENSE.txt`
- Modify: `parametric_mac/theme.py` (`install_typography`), `parametric_mac/ui_assets/FONT-SOURCE.md`
- Test: `tests/test_assets.py` (add tests)

**Interfaces:**
- Produces: `install_typography() -> str` (returns the UI family name `"Geist"`); `MONO_FAMILY = "Geist Mono"` in `theme.py`; `mono_font(point_size: int) -> QFont` with tabular figures where Qt supports `QFont.setFeature` (PySide6 ≥ 6.7), else the plain mono font.

- [ ] **Step 1: Get the fonts.** Download `ofl/geist/Geist[wght].ttf`, `ofl/geistmono/GeistMono[wght].ttf`, and `ofl/geist/OFL.txt` from `https://github.com/google/fonts` at one fixed commit. Instance static weights 400, 500, 600 (Geist) and 400, 500 (Geist Mono) with `fontTools.varLib.instancer`, as was done for Inter. Install fontTools in a throwaway venv, not in `.venv`. Record the commit hash, the URLs, the SHA-256 of each output file, and the commands in `FONT-SOURCE.md`.
- [ ] **Step 2: Write the failing tests** in `tests/test_assets.py`:

```python
from pathlib import Path
ASSETS = Path("parametric_mac/ui_assets")

def test_geist_fonts_are_bundled_with_license():
    names = {"Geist-Regular.ttf", "Geist-Medium.ttf", "Geist-SemiBold.ttf", "GeistMono-Regular.ttf", "GeistMono-Medium.ttf", "Geist-OFL.txt"}
    assert names <= {p.name for p in ASSETS.iterdir()}
    assert not list(ASSETS.glob("Inter-*"))
```

  And a GUI test with `tests/gui_harness.py` (create it in this task):
  - `run_gui(script: str, timeout: int = 180) -> str` runs `script` with `sys.executable -c`, with `QT_QPA_PLATFORM=offscreen`, `PARAMETRIC_SETTINGS_DIR=<new tmp dir>`, and `PARAMETRIC_PROJECTS_ROOT=<new tmp dir>`, and returns stdout. It fails the test with stderr if the return code is not 0 or stdout lacks `"OK"`.
  - Script: `QApplication([])`, then `install_typography() == "Geist"`, then `QFontDatabase.families()` contains `"Geist Mono"`, then print `OK`.
- [ ] **Step 3: Run, expect FAIL.**
- [ ] **Step 4: Implement.** `install_typography` loads all five files and raises `RuntimeError("Could not load bundled font <file>")` if one fails. App font: Geist, pixel size 13.
- [ ] **Step 5: Run `tests/test_assets.py` → PASS.** `tests/test_gui.py` now fails on `font().family() == 'Inter'`. Change that assertion to `'Geist'` in this task.
- [ ] **Step 6: Run the full suite** `.venv/bin/python -m pytest -q` → PASS.
- [ ] **Step 7: Commit** — `feat: bundle Geist and Geist Mono fonts`

---

### Task 3: Style sheet and appearance switch

**Files:**
- Create: `parametric_mac/ui/style.py`
- Modify: `parametric_mac/theme.py` (remove `STYLE` and `style_sheet()`; keep `icon()`), `parametric_mac/gui.py` (use the new style; temporary until Task 4)
- Test: `tests/test_style.py`

**Interfaces:**
- Consumes: Task 1 `Palette`, `resolve_mode`, `palette_for`, `Appearance`.
- Produces:
  - `build_style_sheet(palette: Palette, assets: Path) -> str`. Keep the current selectors (`QLabel[role=title|section|quality|muted]`, `QPushButton[primary]`, `[quiet]`, `[nav]`, `[profile]`, `QToolButton[disclosure]`) and add `QPushButton[outline]`, `QPushButton[link]`, `QFrame[card]`, `QFrame[card][selected="true"]`, `QFrame[alert="error"]`, `QFrame[stage]`, `QWidget#topBar`, `QWidget#footer`, `QWidget#aside`.
  - `SETTINGS_KEY = "ui/appearance"`.
  - `class AppearanceController(QObject)` with `__init__(app: QApplication, settings: QSettings)`, `choice() -> Appearance`, `set_choice(choice: Appearance) -> None` (saves, then applies), `palette() -> Palette`, `on_system_scheme_changed() -> None` (public so tests can call it; offscreen cannot emit the signal), and the signal `changed = Signal(object)` (emits the `Palette`). An unknown saved value falls back to `"system"`.
  - **Native controls:** QSS does not reach macOS combo popups, menus, and scroll bars. So for "light"/"dark" call `app.styleHints().setColorScheme(Qt.ColorScheme.Light/Dark)`; for "system" call `unsetColorScheme()` first, then read `colorScheme()`. Guard both calls with `hasattr` (they need Qt 6.8; the pin allows 6.7). The handler for `colorSchemeChanged` must ignore the signal caused by its own `setColorScheme` call (a re-entry flag). Then it applies the style sheet and a matching `QPalette`.
  - `settings_from_env() -> QSettings` — INI `QSettings` in `PARAMETRIC_SETTINGS_DIR` if set, else `QSettings("Parametric", "Parametric")`.

- [ ] **Step 1: Write the failing tests**

```python
import re
from pathlib import Path
from parametric_mac.ui.style import build_style_sheet
from parametric_mac.ui.tokens import DARK, LIGHT

def test_style_sheet_uses_only_palette_colors():
    for palette in (DARK, LIGHT):
        css = build_style_sheet(palette, Path("x"))
        used = set(re.findall(r"#[0-9a-fA-F]{6}\b", css))
        assert used <= {v.lower() for v in vars(palette).values()} | {v.upper() for v in vars(palette).values()}

# Files that still hold old literals; later tasks delete or convert them and shrink this set to empty (Task 12 asserts empty).
LEGACY_COLOR_FILES = {"parametric_mac/gui.py", "parametric_mac/control_editor.py"}
COLOR = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b|QColor\(\s*\d")

def test_no_color_literals_outside_tokens():
    for path in Path("parametric_mac").rglob("*.py"):
        if path.name != "tokens.py" and str(path) not in LEGACY_COLOR_FILES:
            assert not COLOR.search(path.read_text()), path
```

  GUI test (`run_gui`):
  - Use a `QSettings` on a temporary INI file.
  - `set_choice("dark")`: a new controller on the same settings reads back `"dark"`.
  - `set_choice("light")`: `app.styleSheet()` contains `LIGHT.bg` at once, and `changed` fired once.
  - A saved value `"purple"` reads back `"system"`.
  - With choice "system", calling `on_system_scheme_changed()` re-applies the style sheet once; with choice "dark", it changes nothing.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `style.py`.** Wire `MacWindow.__init__` to create the controller as `self.appearance` **before** `super().__init__()` (upstream `MainWindow.__init__` calls `_build_ui` at `.upstream/nam/capture/gui/main.py:438`, and the pages read the palette while they build) (later tasks read `self.appearance.palette()` and connect to `self.appearance.changed` to repaint custom-painted widgets) (with `QSettings("Parametric", "Parametric")`) and replace `style_sheet()`. Use `LIGHT`/`DARK` `bg` for the `QPalette` window color.
- [ ] **Step 4: Run the new tests and the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: add token-based style sheet and appearance controller`

---

### Task 4: Split gui.py into the ui package (pure move)

No behavior change. Every existing test must pass without edits, except imports.

**Files:**
- Create: `parametric_mac/ui/window.py`, `shell.py`, `jobs.py`, `project_io.py`, `widgets/__init__.py`, `widgets/common.py`, `widgets/knobs.py`, `widgets/meters.py`, `pages/__init__.py`, `pages/connect.py`, `pages/plan.py`, `pages/capture.py`, `pages/train.py`, `pages/review.py`
- Modify: `parametric_mac/gui.py` → a shim
- Test: existing `tests/test_gui.py`

**Interfaces:**
- Produces:
  - `parametric_mac/ui/window.py`: `class MacWindow(ShellMixin, ProjectMixin, JobsMixin, ConnectPageMixin, PlanPageMixin, CapturePageMixin, TrainPageMixin, ReviewPageMixin, MainWindow)` and `launch(train_tab: bool = False) -> int`.
  - Each page mixin has `_build_<key>_page(self) -> QWidget` plus the methods of that page. Use the scout map of `gui.py`: `_connect_page` 477–597 with `_mirror_controls`…`_save_details`; `_plan_page` 599–670 with `_apply_quality`…`_refresh_corner_count` and `_commit_plan`; `_capture_page` 672–726 with `_show_selected_target`, `_begin_capture`, `_on_capture_*`; `_train_page` 728–808 with `_set_duration`, `_show_duration`, `_save_architecture`; `_review_page` 810–844 with `_refresh_runs`…`_open_recordings`.
  - `JobsMixin`: `_busy`, `_start`, `_read_log`, `_finished`, `_process_error`, `_reset_process`, `_retry_cpu`, `_stop`, `_run_worker`.
  - `ProjectMixin`: `_on_new_project`, `_create_project`, `_on_open_project`, `_open_project`, `_route_ready`, `_on_route_test*`, `_refresh_sample_rate_warning`.
  - `ShellMixin`: `_build_ui`, `_page`, `go_to`, `_refresh_all`, `_refresh_status_bar`, `_sync_states`, `closeEvent`.
  - `widgets/common.py`: `label`, `button`, `disclosure`, `field`, `Columns`, `PageScroll`, `StageButton`, `TrainingProfiles`. `widgets/knobs.py`: `KnobTargets`. `pages/plan.py` keeps `CoverageSlider`, `QualityStops` (deleted in Task 9).
  - `parametric_mac/gui.py`: `from .ui.window import MacWindow, launch  # noqa: F401`.

- [ ] **Step 1:** Run `.venv/bin/python -m pytest -q` and record the pass count (baseline).
- [ ] **Step 2:** Move the code. The mixin order matters: overrides of upstream methods must sit in a mixin that comes before `MainWindow` in the class bases. Each file must be ≤ 800 lines. The only allowed change: moved code that has color literals (for example the route symbol `setStyleSheet('border: 1px solid #d2ddec; …')` and the `QColor` values in `KnobTargets`, `CoverageSlider`, `QualityStops`, `StageButton`) takes them from the palette instead. Mixins read `self.appearance.palette()`. Painted widgets (`KnobTargets`, `CoverageSlider`, `QualityStops`, `StageButton`) get `set_palette(palette: Palette) -> None` (stores it, calls `update()`), set at creation and connected to `self.appearance.changed`. Then remove `parametric_mac/gui.py` from `LEGACY_COLOR_FILES`.
- [ ] **Step 2b:** Re-point patches. `tests/test_gui.py:72` assigns `gui.FILES`; after the move this misses the module that uses `FILES`. Patch the new module (`parametric_mac.ui.project_io.FILES`). Grep `tests/` and `scripts/` for every other `gui.<name> =` assignment and re-point it too. A missed patch can open a modal dialog offscreen and hang until the timeout.
- [ ] **Step 3:** Run the full suite → same pass count as Step 1. Also run `wc -l parametric_mac/ui/**/*.py parametric_mac/ui/*.py` → no file above 800.
- [ ] **Step 4: Commit** — `refactor: split gui.py into ui package mixins`

---

### Task 5: Shell — top bar, step bar, footer, keyed navigation

**Files:**
- Modify: `parametric_mac/ui/shell.py`, `parametric_mac/ui/window.py`
- Test: `tests/test_shell.py`, `tests/test_gui.py` (navigation calls)

**Interfaces:**
- Consumes: Task 3 `AppearanceController`.
- Produces (in `shell.py`):
  - `@dataclass(frozen=True) class Step: key: str; title: str; numbered: bool`.
  - `STEPS: tuple[Step, ...]`. The transitional value in this task is `start` (unnumbered), `connect`, `plan`, `capture`, `train`, `review`. Each later page task edits this one tuple. The final value is `start, gear, connect, record, train, listen`.
  - `class StepBar(QWidget)` with `set_states(states: Mapping[str, Literal["todo", "current", "done"]])` and the signal `selected = Signal(str)`. Numbered steps only. Done steps show "✓".
  - `class TopBar(QWidget)` (`objectName "topBar"`): brand on the left, `StepBar` in the center, project name on the right, then an appearance `QToolButton` with a `QMenu` of exclusive actions "Match macOS", "Light", "Dark".
  - `class Footer(QWidget)` (`objectName "footer"`) with `set_status(text: str)` and `set_primary(text: str, callback: Callable[[], None] | None, enabled: bool = True)`. `callback=None` hides the button. It is the only filled button in the shell.
  - `ShellMixin.go_to_step(key: str) -> None`, `ShellMixin.current_step() -> str`, `ShellMixin.step_states() -> dict[str, str]`. Keep `go_to(index)` as a thin wrapper for old callers.
  - App menu: View → Appearance (the same three actions, kept in sync with the top bar menu) and an About item that shows the engine version (from upstream `version_label`).
- Removes: the left sidebar, `StageButton`, and the visible status bar (keep the upstream `status_bar` widget hidden).
- Before a project exists, only `start` and `gear` are enabled in the step bar; the other steps are disabled (todo). Test this.
- Start page in this task: a placeholder page with the title "Parametric" and the existing **New project** / **Open project** actions. Task 6 replaces it.

- [ ] **Step 1: Write the failing GUI tests** (`run_gui`):
  - `window.pages.count() == len(STEPS)`.
  - `go_to_step("train")`: `current_step() == "train"`, and the train page is the current widget.
  - A click on a step emits `selected` and navigates.
  - On each page, the whole window has exactly one visible `QPushButton` with `primary == True` (Start's **New capture** in the page body counts; the footer button is hidden there).
  - The appearance menu has 3 checkable actions. Checking "Light" changes `app.styleSheet()` and checks the View → Appearance "Light" action too.
  - **Review Focus 4:** start a fake job (set `window.process` to a dummy `QProcess` started on `sys.executable -c "import time; time.sleep(5)"`), go to "train", type into a `QLineEdit` on another page, switch the appearance to Dark, then to Light. Assert that `current_step()` is unchanged, `window.process` is the same object and still running, and the field text is kept. Then kill the process.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** `test_gui.py`: replace index-based `go_to(n)` calls with `go_to_step(key)` and `pages.count() == 5` with `len(STEPS)`. `launch(train_tab)`: opens Start (spec §4.0b); `train_tab` is accepted and ignored. Add a docstring line about this.
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: add Console shell with step bar, footer and appearance menu`

---

### Task 6: Recent projects, default folder, Start page

**Files:**
- Create: `parametric_mac/recent.py`, `parametric_mac/ui/pages/start.py`
- Modify: `parametric_mac/ui/project_io.py`, `shell.py` (`STEPS`), `window.py`
- Test: `tests/test_recent.py`, `tests/test_ui_start.py`

**Interfaces:**
- Produces (`recent.py`, Qt-free):
  - `@dataclass(frozen=True) class RecentProject: path: str; name: str; opened_at: float`.
  - `parse_recent(raw: object) -> tuple[RecentProject, ...]` (from a JSON string kept in QSettings key `"recent/projects"`; it ignores bad entries), `dump_recent(items) -> str`.
  - `remember(items, path: Path, name: str, now: float, limit: int = 12) -> tuple[RecentProject, ...]` — new tuple, newest first, no duplicates by resolved path.
  - `forget(items, path: Path) -> tuple[RecentProject, ...]`.
  - `ProjectState = Literal["missing", "unreadable", "new", "recording", "recorded", "ready", "stopped"]`. `new` = the project has no plan entries yet (the folder is created at Gear → Next, the plan only at Record → Start recording); `recording` = 0 < captured < total, or captured == 0 < total; `recorded` = all takes saved and no run with a model; `ready` and `stopped` as below.
  - `@dataclass(frozen=True) class ProjectStatus: state: ProjectState; detail: str; captured: int; total: int`.
  - `project_status(path: Path) -> ProjectStatus`. It reads `capture_project.json` (with `load_project`), the captured count, and `outputs/*/status.json` and `model_parametric.nam`. `ready` = a run with a model; `stopped` = the newest run has status failed/stopped with no model; `recording` = captured < total. Missing folder → `missing`, "Folder not found". Any read error → `unreadable`, "Cannot read this project".
  - `projects_root() -> Path` — `Path(os.environ["PARAMETRIC_PROJECTS_ROOT"])` if set, else `Path.home() / "Music" / "Parametric"`. Read at call time, never at import.
  - `safe_folder_name(name: str) -> str` — replaces `/ \ : * ? " < > |` and control characters with `-`, trims spaces and dots at both ends, cuts to 80 characters, and gives `"Untitled capture"` for an empty result.
  - `default_project_dir(root: Path, name: str) -> Path` — `root / safe_folder_name(name)`; if it exists, `"<name> 2"`, `"<name> 3"`, …. The result's parent is always `root`.
  - `resume_step(status: ProjectStatus) -> str` — after a reopen: `"connect"` for `new` (total == 0) and `recording`; `"listen"` for `ready`; `"train"` for `recorded` and `stopped`. (Spec §4.0b: reopen always needs a connection check before recording.)
- Produces (`StartPageMixin` in `pages/start.py`): `_build_start_page() -> QWidget`, `_refresh_recent() -> None`. Rows have a tag by state: `new`/`recording` → `Continue`, `recorded` → `Recorded`, `ready` → `Ready`, `stopped` → `Stopped`, `missing` → "Folder not found", `unreadable` → "Cannot read this project"; the last two get a **Remove from list** link.
- `ProjectMixin._open_project` and `_create_project` call `remember(...)` and save to QSettings. **Open folder…** uses the current open flow.

- [ ] **Step 1: Write the failing unit tests** (`tests/test_recent.py`), including:

```python
def test_safe_folder_name_review_focus_2():
    assert safe_folder_name("Fuzz/Face") == "Fuzz-Face"
    assert safe_folder_name("a:b") == "a-b"
    assert safe_folder_name("   ") == "Untitled capture"
    assert safe_folder_name(".hidden") == "hidden"
    assert len(safe_folder_name("x" * 300)) == 80

def test_default_project_dir_never_escapes_root(tmp_path):
    for name in ("../evil", "/abs", "Fuzz/Face", ".."):
        assert default_project_dir(tmp_path, name).parent == tmp_path

def test_default_project_dir_numbers_existing(tmp_path):
    (tmp_path / "Rat").mkdir()
    assert default_project_dir(tmp_path, "Rat").name == "Rat 2"

def test_status_missing_and_corrupt_review_focus_5(tmp_path):
    assert project_status(tmp_path / "gone").state == "missing"
    (tmp_path / "capture_project.json").write_text("{not json")
    assert project_status(tmp_path).state == "unreadable"

def test_remember_is_immutable_and_deduplicates(tmp_path): ...
def test_parse_recent_ignores_bad_entries(): ...
def test_resume_step_for_old_project_review_focus_1(project_with_locked_quality_4): ...
```

  Also: `resume_step(ProjectStatus("new", "", 0, 0)) == "connect"`.
  For Review Focus 1, build a fixture project with `workflow.json` = `{"quality": 4, "plan_locked": true, "gear_kind": "Pedal", "fixed_notes": "Level at 5"}` and 1 captured entry of 40. Expect `resume_step(...) == "connect"`.
- [ ] **Step 2: GUI test** (`tests/test_ui_start.py`): a new window shows Start. Write a recent list with one good project, one deleted folder, and one corrupt project into a temporary INI QSettings. Start shows 3 rows: the good row has the correct tag; the other two show "Folder not found" and "Cannot read this project"; no exception. **Remove from list** removes the row and saves.
- [ ] **Step 3: Run, expect FAIL.**
- [ ] **Step 4: Implement.** Start page layout per mockup window 0. Copy: headline "Turn your pedal into a model you can still turn the knobs on.", main button **New capture** (goes to Gear), outline **Open folder…**, the needs line. Show saved state only (spec §4.0b).
- [ ] **Step 5: Run the full suite → PASS.**
- [ ] **Step 6: Commit** — `feat: add Start page with recent projects and safe default folders`

---

### Task 7: Gear page

**Files:**
- Create: `parametric_mac/ui/pages/gear.py`
- Modify: `parametric_mac/control_editor.py` (add the tile view), `parametric_mac/ui/widgets/knobs.py` (`GearDrawing`), `parametric_mac/ui/pages/connect.py` (remove the gear section), `shell.py` (`STEPS`: insert `gear` after `start`)
- Test: `tests/test_ui_gear.py`, `tests/test_controls.py` (starter swap), `tests/test_gui.py`

**Interfaces:**
- Produces:
  - In `control_editor.py`: `is_untouched_starter(controls: tuple) -> bool` and `swap_starter(controls: tuple, amp: bool) -> tuple` (returns `starter(amp)` if `is_untouched_starter(controls)`, else returns `controls` unchanged).
  - `ControlEditor` gets a `layout_mode` of `"tiles"`: a `QGridLayout` of tiles (118 px wide, wrapping), `+ Knob` / `+ Switch` tiles, and × on each tile. It keeps the same `controls`, `commit`, `rename`, `add_control`, `remove`, `edit`, and `changed` API.
  - `GearDrawing(QWidget).set_gear(name: str, controls: tuple, fixed_notes: str, palette: Palette)` — enclosure, LED, knob row (wrapping), fixed controls dimmed, name in capitals.
  - `GearPageMixin._build_gear_page()`, `_gear_next()` (creates the project at the folder in the footer line, then `go_to_step("connect")`), `_gear_locked() -> bool`, `_new_capture_from_gear()`.
- Widgets keep their names for tests: `pedal_name`, `gear_kind` (now a 2-button segmented control that exposes `currentText()`), `fixed_notes`, `control_editor`, `effort_label`.

- [ ] **Step 1: Write the failing tests**
  - Unit: `swap_starter(starter(False), True) == starter(True)`; for a changed list it returns the same tuple; it never mutates the input.
  - GUI (`run_gui`):
    - A new window has `gear_kind.currentText() == "Pedal"` and controls Drive + Tone.
    - Click Amp → 7 controls. Add a knob, then click Pedal → still 8 controls.
    - `effort_label` text starts with `"~40 recordings"` for the Pedal starter.
    - The footer line shows `<projects_root()>/My pedal` (the harness sets `PARAMETRIC_PROJECTS_ROOT`; the display uses `~` only for the real home path).
    - "Change" to a non-empty folder (stub the folder dialog) shows the inline error "Choose an empty folder." and keeps the old path.
    - `_new_capture_from_gear()` on a locked project creates a new folder with equal controls and `fixed_notes`, opens it, and leaves the old `capture_project.json` byte-identical.
    - Next creates the folder, and the current step becomes `"connect"`.
    - After a fake accepted capture (reuse the existing test approach with `_on_capture_success`), the Gear inputs are disabled and the "Locked after the first take" note is visible.
    - **Review Focus 3:** with 24 controls at 800×680, the page has no horizontal scroll bar.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.1 and mockup window 1. Remove the Pedal starter / Amp starter buttons. Move the existing `test_gui.py` assertions about `_use_starter`, `wiring_note`, and the controls editor to their new widgets.
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: add Gear page with control tiles and live gear drawing`

---

### Task 8: Connect page (Phase 1 fallback)

**Files:**
- Modify: `parametric_mac/ui/pages/connect.py` (rewrite), `parametric_mac/ui/widgets/meters.py` (`LevelMeter`), `parametric_mac/ui/project_io.py` (reopen rule), `parametric_mac/ui/copy.py`
- Test: `tests/test_ui_connect.py`, `tests/test_copy.py`, `tests/test_gui.py`

**Interfaces:**
- Produces:
  - `copy.py`: `sample_rate_message(device_rate: int | None, file_rate: int) -> str | None` — returns `None` when equal **or when `device_rate is None`** (unknown current rate: upstream treats it as no meaningful rate; show it as a non-blocking note, not a block), else "Your sound card runs at 44.1 kHz. Set it to 48 kHz in Audio MIDI Setup, then check again." (rates formatted as kHz with at most one decimal). Get the rates from the upstream `_current_sample_rate_warnings()` logic, not a new probe.
  - `copy.py`: `level_message(peak_dbfs: float, clip_threshold: float) -> tuple[Literal["ok", "clip"], str]`. Use the **same clip threshold that `_on_route_test_success` applies now** (pass it in; do not invent a new one). At or above it → `clip`, with the current "too close to clipping" text in plain words. Otherwise → `ok`: "Peak −9 dB · good. Do not touch the sound card gain from now on." (with the real value). No new "low" block in Phase 1.
  - `LevelMeter(QWidget).set_peak(dbfs: float | None)`, zones at −18 and −6 dB, colors from the palette.
  - `ConnectPageMixin`: stage widgets `wire_check` (the one checkbox), `device_combo` (upstream, re-parented), a refresh icon button that calls upstream `_refresh_devices`, `sample_rate_label`, the Phase 1 channel fields (upstream `output_channel_spin` / `input_channel_spin` with the plain labels from spec §4.2), `check_level_button` (calls the existing `_on_route_test`), `level_meter`, `level_result`; `_connect_ready() -> bool`.
  - Expert settings disclosure holds the upstream loopback, buffer, and latency widgets.
- Readiness: `_connect_ready()` is True only when `wire_check` is on, a device is selected, `sample_rate_message(...) is None`, and the last level check was `ok` for the current route fingerprint (reuse `_route_fingerprint`). Next: Record is enabled only then. `_route_ready()` (used by capture) returns `_connect_ready()`.
- The reopen rule (spec §4.2): `_open_project` restores the device and channels, sets `wire_check` off, and clears the level result.
- Amp mode: the chain shows the load box and the warning text from spec §4.2 before the chain. The right panel adds "A load box".
- Remove `reamp_check`, `monitor_check`, `level_check`, `confirm_knobs`'s connect role, `wiring_note`, `route_caption`, and every "UMC22" string.

- [ ] **Step 1: Write the failing tests**
  - Unit (`test_copy.py`): `sample_rate_message(44100, 48000)` contains "44.1 kHz" and "48 kHz"; `sample_rate_message(48000, 48000) is None`; `sample_rate_message(None, 48000) is None`; with the current threshold `T`, `level_message(T + 0.1, T)[0] == "clip"` and `level_message(-9.2, T)[1].startswith("Peak −9.2 dB")`.
  - GUI:
    - Next is disabled until the checkbox is on and a fake `_on_route_test_success` result with peak −9 dBFS arrives.
    - Change the input channel → Next is disabled again (the fingerprint changed).
    - Reopen the project → the checkbox is off and Next is disabled.
    - Gear = Amp → the chain shows "Load box" and the warning label is visible.
    - **Show me how to fix it** opens the help text (a disclosure with short steps for: no device, wrong sample rate, no signal, clipping) and links `docs/hardware-umc22.md` / `docs/hardware-amps.md` as examples.
    - `grep -ri umc22 parametric_mac/` finds nothing (add this as a Python test that walks `parametric_mac/**/*.py`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.2 (Phase 1 fallback) and mockup window 2. The **Open Audio MIDI Setup** button runs `QProcess.startDetached("open", ["-a", "Audio MIDI Setup"])`. If that fails, show "Open Audio MIDI Setup from Applications › Utilities."
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: rebuild Connect as three guided stages`

---

### Task 9: Record page, part 1 — detail level and plan

Merges the old Plan page into Record.

**Files:**
- Create: `parametric_mac/ui/pages/record.py` (start it), `parametric_mac/ui/widgets/common.py` (`ChoiceCard`)
- Modify: `parametric_mac/workflow.py` (mapping), `shell.py` (`STEPS`: replace `plan` + `capture` with `record`)
- Delete: `parametric_mac/ui/pages/plan.py` (`CoverageSlider`, `QualityStops`)
- Test: `tests/test_quality.py`, `tests/test_ui_record.py`, `tests/test_gui.py`

**Interfaces:**
- Produces:
  - `workflow.py`: `MAIN_LEVELS: tuple[tuple[str, int], ...] = (("Fast", 0), ("Good", 2), ("Max", 3))`, `RECOMMENDED_LEVEL = 2`, `level_label(index: int) -> str` (returns "Fast", "Good", "Max" for 0/2/3, and the `QUALITIES[index].name` for 1 and 4).
  - `ChoiceCard(QFrame)`: `set_content(title: str, number: str, unit: str, body: str, tag: str | None)`, `set_selected(bool)`, signal `clicked`.
  - `RecordPageMixin._build_record_page()`. The page has two states in a `QStackedWidget`: `record_choose` and `record_loop` (Task 10). `quality_cards: tuple[ChoiceCard, ChoiceCard, ChoiceCard]`, `_select_level(index: int)` (calls the existing `_apply_quality`), `_start_recording()` (calls the existing `_commit_plan`, then shows `record_loop`).
  - Expert settings (Record): "More levels" buttons for Decent (1) and Overkill (4), and the existing `n_train_spin`, `n_validation_spin`, `seed_spin`, `include_corners_check`, `knob_table`.
- Locked plan: the cards are disabled; the selected card shows `level_label(stored index)` plus "Locked after the first take."

- [ ] **Step 1: Write the failing tests**
  - Unit: `[level_label(i) for i in range(5)] == ["Fast", "Decent", "Good", "Max", "Overkill"]`; `MAIN_LEVELS` indexes map to `QUALITIES` names "Quick test", "Good", "Thorough".
  - GUI:
    - A new project's Record page shows the choose state with "Good" selected, and the Good card text contains "40" (the same plan as `test_good_two_knob_plan_matches_approved_effort`).
    - Every card shows the **plan entry count** (the same number as the current `effort_label` / `_preview`, which includes corners). In the test, compute the expected values with `quality_settings` + `make_plan` for levels 0, 2, 3; Good must be 40, and Fast must equal the 14 entries that the existing level-0 commit assertion in `test_gui.py` expects. Do not hard-code the mockup's 12 or 96.
    - Start recording → `_workflow["quality"] == 2` is persisted and the loop state shows.
    - **Review Focus 1:** open the old-project fixture with quality 4 and a lock. The cards are disabled and the selected card title is "Overkill".
  - Update `test_gui.py`: `quality_slider.value() == 2` → the Good card is selected; `effort_label` checks move to the Good card text.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.3 (first visit) and mockup window 3a. The card numbers are computed (spec, top section: the mockup numbers are wrong).
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: choose capture detail on Record with three level cards`

---

### Task 10: Record page, part 2 — recording loop

**Files:**
- Modify: `parametric_mac/ui/pages/record.py`, `parametric_mac/ui/widgets/knobs.py` (`TargetControls`), `parametric_mac/ui/copy.py`
- Delete: `parametric_mac/ui/pages/capture.py` (after its logic moves)
- Test: `tests/test_copy.py`, `tests/test_ui_record.py`, `tests/test_gui.py`

**Interfaces:**
- Produces:
  - `copy.py`: `@dataclass(frozen=True) class TakeMessage: kind: Literal["ok", "clipped", "warning"]; title: str; body: str` and `take_message(clipping: bool, messages: Sequence[str]) -> TakeMessage`. Clipped body, verbatim from spec §4.3: "This take clipped. Record it again. If it clips again, the level is too high for this pedal. Start a new capture and set a lower level on Connect." No message may suggest changing the reamp box or sound card level.
  - `knobs.py`: `changed_controls(previous: Mapping[str, float] | None, current: Mapping[str, float]) -> frozenset[str]` (all names when `previous is None`); `size_tier(count: int) -> Literal["large", "medium", "compact"]` (1–2 large, 3–6 medium, 7–24 compact); `TargetControls(QWidget).set_targets(entry, controls, changed: frozenset[str], palette: Palette)` — at most 4 per row, switches as "Name · POSITION", a "Changed" mark on changed names.
  - `RecordPageMixin`: `record_button` (states "Record" → "Cancel" during a take → "Record again" after a failed take; `setFocusPolicy(Qt.NoFocus)` so Space never triggers it twice), a `Space` `QShortcut` on the Record page widget with `Qt.WidgetWithChildrenShortcut`, whose handler does nothing unless the Record loop is visible and `QApplication.focusWidget()` is not a `QLineEdit`, `QPlainTextEdit`, `QTextEdit`, or `QAbstractSpinBox`, `take_alert` (`AlertBox`), `progress_bar`, `time_left_label`, `last_take_label`, `up_next_list`, an **All takes ▸** disclosure with the upstream `capture_table` and a **Record this one again** button (the existing selected-entry capture path), and **Start a new capture with these controls** in the clipped alert (calls `_new_capture_from_gear` from Task 7).
- Removes: `confirm_knobs` (spec §5; pressing Record confirms), the always-visible Cancel button, and the "Advanced capture tools" disclosure.
- Done state: "All N takes are saved." and the footer **Next: Train →**.

- [ ] **Step 1: Write the failing tests**
  - Unit:
    - `take_message(True, [...]).kind == "clipped"`, and its body equals the spec text.
    - For all outputs of `take_message`, the body does not contain "reamp box output down" or "gain".
    - `changed_controls({"Drive": 2.5, "Tone": 7}, {"Drive": 6, "Tone": 7}) == {"Drive"}`; `changed_controls(None, {...})` returns all names.
    - `size_tier(2) == "large"`, `size_tier(6) == "medium"`, `size_tier(24) == "compact"`.
  - GUI:
    - With a ready route, the Record button is enabled with no checkbox.
    - A fake `_begin_capture` changes the button text to "Cancel".
    - A fake clipped QA result shows the alert and "Record again".
    - A fake ok QA result advances "SETTING n / N".
    - **Review Focus 3:** 24 controls at 800×680 → no horizontal scroll.
    - **Review Focus 6:** replace `_begin_capture` with a counter. Space typed in the Gear name field, Space on the Train page, and Space in a Record Expert spin box → counter 0. Space on the Record loop with no text focus → counter 1 (not 2).
  - Update `test_gui.py` assertions that used `confirm_knobs`, `queue_rows`, `knob_targets`, `capture_hint`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.3 and mockup window 3b, with the clipped-take correction. Keep the upstream calls (`_next_pending_entry`, `_begin_capture`, `_on_capture_*`).
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: rebuild the recording loop with change marks and plain take feedback`

---

### Task 11: Train page

**Files:**
- Modify: `parametric_mac/ui/pages/train.py` (rewrite), `parametric_mac/ui/jobs.py`, `parametric_mac/ui/widgets/meters.py` (`TrainingChart`), `parametric_mac/ui/copy.py`
- Test: `tests/test_copy.py`, `tests/test_ui_train.py`, `tests/test_gui.py`

**Interfaces:**
- Produces:
  - `copy.py`: `@dataclass(frozen=True) class EpochPoint: tier: str; epoch: int; value: float` and `parse_epoch_finished(line: str) -> EpochPoint | None`. It reads `Epoch N finished. [tier: ]...` lines (format at `parametric_mac/training.py:204`), with `tier = ""` when there is no prefix, and the `ESR` value, else `val_loss`. `check_errors(log: str) -> tuple[str, ...]` returns the text after `ERROR: ` lines (format in `checks.py` `Report.text`). `minutes_left(epoch_seconds: Sequence[float], epochs_left: int) -> int | None` returns `None` with fewer than 2 samples, else the median × left, rounded up to whole minutes.
  - `TrainingChart(QWidget)`: `clear()`, `add_point(point: EpochPoint)`, `set_total(epochs: int)`, `set_palette(palette)`, log-scale y, one series per tier; only the current tier's series is drawn. The page title "Training · Standard size" / "Step 1 of 2. The Nano size comes next." comes from the tier of the newest point (dual models only).
  - `TrainPageMixin`: `mode_cards` (Quick test = 1 epoch, Full training = 200 epochs; copy from spec §4.4 with "1 round" / "200 rounds per size"), the Expert disclosure with `model_architecture`, `epochs`, `device`, `batch`, `train_log`; `train_button` (= the footer primary **Start training →**), `stop_button` (outline, visible only while running), the `train_alert` failure box with **Try again on CPU** (the existing `_retry_cpu`) and **Show log**.
  - `JobsMixin`: `_start_training_flow()` runs `_start("check")`. When the check finishes with exit code 0, `_finished` starts `"train"`. On a non-zero check, it shows `check_errors(...)` in `train_alert` with a **Go to Record** link, and training does not start.
- Removes: the **Check recordings** button (spec §5), `TrainingProfiles`, and the Custom segment (custom epochs are in Expert).
- Not complete recording: the cards are disabled, with "Finish recording first: n of N takes saved." and **Go to Record**.

- [ ] **Step 1: Write the failing tests**
  - Unit:
    - `parse_epoch_finished("Epoch 3 finished. ESR=0.0123, MSE=1e-4") == EpochPoint("", 3, 0.0123)`.
    - `parse_epoch_finished("Epoch 203 finished. nano: ESR=0.02") == EpochPoint("nano", 203, 0.02)`.
    - `parse_epoch_finished("Epoch 3 finished. standard: val_loss=0.5") == EpochPoint("standard", 3, 0.5)`.
    - Before writing these, read `training.py:176-206` and confirm the real metric formatting (`", ".join(metrics)`); adjust the test strings to the real format, not the other way round.
    - `parse_epoch_finished("Epoch 3/200 started") is None`.
    - `check_errors("x\nERROR: Missing take 3\nWARNING: y") == ("Missing take 3",)`.
    - `minutes_left([60.0], 5) is None`; `minutes_left([60.0, 66.0, 54.0], 10) == 10`.
  - GUI:
    - With all takes saved, **Start training** runs `check` first: `window.command == "check"`.
    - A finished check with code 0 starts `"train"` (stub `QProcess` start with a fake `_start`).
    - A finished check with code 1 and log `ERROR: Missing take 3` shows the alert with "Missing take 3" and does not start train.
    - Feeding `Epoch 1 finished. ESR=0.5` and `Epoch 2 finished. ESR=0.2` to `_read_log` adds 2 chart points.
    - No visible widget text on the main path contains "epoch" (search visible `QLabel`/`QPushButton` texts outside the Expert disclosure).
  - Update `test_gui.py` assertions for `training_mode`, `training_profiles`, the Check button, and the log toggle.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.4 and mockups 4a/4b, with the corrections (no time estimate before a run; "rounds").
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: rebuild Train with one start action, live chart and plain failures`

---

### Task 12: Listen page

**Files:**
- Create: `parametric_mac/ui/pages/listen.py`
- Delete: `parametric_mac/ui/pages/review.py` (after its logic moves)
- Modify: `shell.py` (`STEPS`: `review` → `listen`), `parametric_mac/ui/copy.py`
- Test: `tests/test_ui_listen.py`, `tests/test_copy.py`, `tests/test_gui.py`

**Interfaces:**
- Produces:
  - `copy.py`: `metric_lines(metrics: Mapping) -> tuple[str, ...]` (the current `_show_run` ESR text, unchanged in meaning, for Expert) and `CHECKPOINT_NOTE = "These settings also chose the best training round, so the match can look better than on new settings."`
  - `ListenPageMixin`: `model_card` (file name `<project name>.nam`, type, controls, trained time) with the footer primary **Save model…** (the existing `_save_model`); `test_table` (one row per held-out entry, label "Test settings — not used to train the model", Match column "—" in Phase 1); `listen_checks: tuple[QCheckBox, QCheckBox]` ("The test settings sound like the real pedal", "Knob moves sound smooth, with no clicks"); an **Earlier models ▸** list (date, model type, status, **Open run folder**); **How to load it ▸** (Ardor steps and the NamParametricPlugin link from the current review text); **Open project folder**; an Expert disclosure with `metric_lines(...)`, `CHECKPOINT_NOTE`, and **Open test recordings** (the existing `_open_recordings`; spec §5).
  - Saved state: `review.json` = `{"listened": bool, "checks": [bool, bool]}`. `listened` is True only when both checks are on. Reading an old `{"listened": true}` without `checks` sets both checks on.
- The newest run with a model is the default. There is no run-ID dropdown in the main view.

- [ ] **Step 1: Write the failing tests**
  - GUI, with the existing synthetic run fixture from `test_gui.py`:
    - Listen shows the model card, and **Save model…** is enabled.
    - Checking one box writes `{"listened": false, "checks": [true, false]}`; checking both writes `listened: true`.
    - An old `review.json` `{"listened": true}` shows both checked.
    - No visible text contains "never heard".
    - The Expert text contains `CHECKPOINT_NOTE`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.5 and mockup window 5 (without the Match values and play buttons, which come in Phases 3–4).
- [ ] **Step 4: Run the full suite → PASS.** Check that `STEPS` is now the final tuple: `start, gear, connect, record, train, listen`. Convert any color literal left in `control_editor.py` and set `LEGACY_COLOR_FILES = set()`; the color test must still pass.
- [ ] **Step 5: Commit** — `feat: add Listen page with model card and listening checklist`

---

### Task 13: Screenshots in both modes and user approval of light mode

**Files:**
- Modify: `scripts/render_native.py`
- Delete: `scripts/verify_mockups.py` (it drives the superseded HTML mockups with a Linux-only browser path; spec §10)
- Output: `docs/screenshots/native/<step>-<state>-<mode>.png`

**Interfaces:**
- `render_native.py --run-project PATH [--out DIR]`. It renders every step in `STEPS` at 1140×900 and 800×680, in `dark` and `light`. It adds these states: Connect not ready / ready, Record choose / loop / clipped, Train before / running (feed fake log lines) / failed, Listen with a run. It writes `evidence.json` with the file list.

- [ ] **Step 1:** Update the script. Use `go_to_step` and the `AppearanceController`.
- [ ] **Step 2:** Build a lasting synthetic run project (the pytest one is deleted): add `scripts/make_demo_project.py OUT_DIR` that writes the `tests/test_workflow.py` `project` fixture files into `OUT_DIR` and runs `python -m parametric_mac train OUT_DIR --device cpu --epochs 1 --architecture auto`. Run it into the scratch area, then `PARAMETRIC_SETTINGS_DIR=<tmp> PARAMETRIC_PROJECTS_ROOT=<tmp> .venv/bin/python scripts/render_native.py --run-project OUT_DIR`. Expected: about 40 PNG files and no exception.
- [ ] **Step 3:** Look at every image. Check that nothing overflows and that no text is clipped, in both modes. Fix any problem in the owning page file, then re-run.
- [ ] **Step 4: User checkpoint (spec §4.0). Lead session only** — a subagent cannot wait for the user. Show the light-mode screenshots to the user and wait for approval. Apply the requested token changes in `tokens.py` only, and re-run Task 1's tests.
- [ ] **Step 5: Commit** — `test: render Console screenshots in dark and light`

---

### Task 14: Documentation

**Files:**
- Modify: `README.md`, `PRODUCT.md`, `DESIGN.md`, `docs/mockups/README.md`

- [ ] **Step 1:** In `README.md`, change the flow to Start → Gear → Connect → Record → Train → Listen. Rewrite the "Your first pedal capture" steps for the new pages. Remove UMC22-only wording from the steps (keep the link to the UMC22 guide as one example). Mention the appearance switch. Replace the screenshot with `docs/screenshots/native/record-loop-dark.png`.
- [ ] **Step 2:** In `DESIGN.md`, replace the Inter tokens with the Console tokens (both modes) and Geist. Link the spec and `docs/design/2026-10-17-ux-redesign/`.
- [ ] **Step 3:** In `PRODUCT.md`, update the capabilities paragraph (five pages plus Start, 3 levels plus 2 in Expert, appearance switch). Keep every honesty statement.
- [ ] **Step 4:** At the top of `docs/mockups/README.md`, add "Superseded by `docs/design/2026-10-17-ux-redesign/` (2026-10-17)."
- [ ] **Step 5:** Run the full suite → PASS. Run `grep -rn "Inter\b" parametric_mac DESIGN.md` → no font references.
- [ ] **Step 5b:** Run `.venv/bin/python -m pytest --cov=parametric_mac.recent --cov=parametric_mac.ui.tokens --cov=parametric_mac.ui.copy --cov=parametric_mac.workflow --cov-report=term-missing -q` → each module ≥ 80%. Add tests where it is lower.
- [ ] **Step 6: Commit** — `docs: describe the Console redesign`

---

## Self-review notes

- **Spec coverage:** §4.0 shell and appearance (Tasks 3, 5, 13), §4.0b Start (6), §4.1 Gear (7), §4.2 Connect Phase 1 (8), §4.3 Record (9, 10), §4.4 Train (11), §4.5 Listen without Phase 3–4 parts (12), §5 control table (Tasks 5–12 remove or move each control), §7 errors (`copy.py` tests), §8 structure (4), §10 tests, scripts, docs (13, 14). §6 features → later plans.
- **Out of Phase 1:** Find my connection, Match values, ▶ Real pedal / ▶ Model playback, and the "Play through" picker.
