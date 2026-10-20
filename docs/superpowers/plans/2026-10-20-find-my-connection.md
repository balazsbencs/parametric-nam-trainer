# Find My Connection (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Connect, one button finds which sound card output feeds the reamp box and which input the gear returns on, for any sound card, and sets the channels for the user.

**Architecture:** A Qt-free analysis module (`find_route.py`) builds a quiet click signal, measures each input with upstream's own click detection, rejects digital loopbacks by a residual test, and chooses the route. A Qt-free scan module (`find_scan.py`) plays the clicks on one output at a time and records all inputs at once, through an injectable play-record function, so tests need no hardware. Connect runs the scan in upstream's existing worker (progress, cancel) and shows the result in plain words; the channel numbers move to Expert settings.

**Tech Stack:** Python 3.12, PySide6, numpy, sounddevice (already used by upstream), the pinned upstream `nam.capture` (`latency.BlipPreamble`, `latency.PlayedPreamble`, `latency.measure_delay`, `audio.find_device`, `audio.CaptureCancelled`, `audio._raise_on_dropout`, `audio._device_channels`).

**Spec:** `docs/superpowers/specs/2026-10-17-ux-redesign-design.md` — §4.2 stage 2 and §6.1. Phase 1 is in PR #2 (branch `feat/ux-redesign-console`).

**Branch:** `feat/find-my-connection`, created from `feat/ux-redesign-console` (Phase 1 is not merged yet). Rebase onto `main` after PR #2 merges.

## Global Constraints

- Run with `.venv/bin/python`; tests with `.venv/bin/python -m pytest -q`. GUI tests use `tests/gui_harness.run_gui` (offscreen, throwaway settings and projects).
- No new dependency. No color literals outside `parametric_mac/ui/tokens.py`. Files ≤ 800 lines, functions < 50 lines, frozen dataclasses for data, type annotations.
- **Safety (spec §6.1, verbatim intent):** Find is enabled only after the "monitoring off and speakers unplugged" checkbox; it plays on **one output at a time**; the user can **cancel at any time**; it never exceeds the route-test level.
- **Level (spec §6.1):** clicks at **−20 dBFS** (`FIND_AMPLITUDE = 0.1`). Task 1 proves upstream detection works at that level with synthetic signals; if it does not, use the lowest of `(0.1, 0.2, 0.45)` that works and write the level and the reason next to the constant. Never above `latency.DEFAULT_BLIP_AMPLITUDE` (0.9).
- **Loopback rejection (spec §6.1):** a return is a loopback only when, after delay alignment and gain matching, the residual is ≤ **−80 dB** relative to the signal (`LOOPBACK_RESIDUAL_DB = -80.0`). Delay and level are hints only, never the reason to reject.
- **Copy (spec §4.2, verbatim):** found: "Found: Output X → Input Y." · more than one input: "Found on inputs 1 and 2. Using input 1 (louder)." · none: "No signal came back. Check the cables, and check that the reamp box and the pedal have power." · loopback in Expert: "Input N looks like a loopback — ignored". Clipping reuses `copy.CLIP_TEXT`.
- **Several routes:** on a device with up to `FULL_SCAN_OUTPUTS = 8` outputs, Find scans every output and does not stop at the first answer, because a plugged-in timing cable (for example OUTPUT R → INST 2) also passes the residual test. When more than one output answers, the user picks: "More than one connection answered. Choose the one that goes through the reamp box and your gear." with one link per route ("Use Output X → Input Y"). On larger devices Find stops at the first route and says so in Expert settings ("Stopped at the first answer: this sound card has N outputs.").
- **Threads:** everything that reads widgets, settings or CoreAudio runs on the GUI thread in `_start_find`; the worker gets plain values only (as upstream `_on_route_test` does).
- Stage 2 is renamed "Find the connection" (spec §4.2, mockup window 2).
- Find does not gate Next. Stage 2 stays "done" when a device is selected and the sample rate is right (Phase 1 rule); the level check (stage 3) proves the route. Find is the main path; the channel numbers move under Expert settings for people who set them by hand.
- Commits: `<type>: <description>`, no attribution trailer. Gate every commit on a green full suite.

## Review Focus

1. **Cancel during a scan** must leave the channels, the saved audio settings and the level check unchanged. → Task 2 and Task 3 tests.
2. **A device with one output or one input**, or an input count of 0, must give a clear result (none) and never crash. → Task 2 test.
3. **The sound card changes or a job starts while Find runs** must be impossible (device and Find button locked as other job inputs). → Task 3 test.
4. **Audio dropouts or a device error** during the scan must show a plain message and keep the old channels. → Task 2 and Task 3 tests.
5. **A found return that clips at −20 dBFS** (a very loud pedal) must still set the channels and show the clip text, so the user lowers the level before the level check. → Task 1 and Task 3 tests.
6. **A plugged-in timing cable** answers on another output: Find must not silently pick it. → Task 2 test (two routes → "several") and Task 3 test (the user picks).

---

### Task 1: Route analysis (no audio, no Qt)

**Files:**
- Create: `parametric_mac/find_route.py`
- Test: `tests/test_find_route.py`

**Interfaces:**
- Produces:
  - `FIND_AMPLITUDE: float = 0.1`, `LOOPBACK_RESIDUAL_DB: float = -80.0`, `CLIP_DBFS: float = -1.0`, `FULL_SCAN_OUTPUTS: int = 8`. `CLIP_DBFS` is the one clip rule: `ui/copy.ROUTE_CLIP_DBFS` becomes `from ..find_route import CLIP_DBFS as ROUTE_CLIP_DBFS` (UI imports core, never the other way).
  - `find_playback(sample_rate: int, amplitude: float = FIND_AMPLITUDE) -> tuple[np.ndarray, PlayedPreamble]` — `BlipPreamble(sample_rate, amplitude).render()` followed by `session.TAIL_SECONDS` of silence; preamble via `PlayedPreamble.from_playback(playback, rendered.n_samples, sample_rate)` (the same layout as upstream `build_playback`, with a lower amplitude).
  - `@dataclass(frozen=True) class InputReturn: input_channel: int; detected: bool; delay: int | None; peak_dbfs: float | None; loopback: bool`.
  - `analyse_input(recording: np.ndarray, input_channel: int, playback: np.ndarray, preamble: PlayedPreamble) -> InputReturn` — `latency.measure_delay(recording, preamble)`; `detected = result.ok`; `peak_dbfs = 20·log10(max|recording|)` (None for silence); `loopback = is_loopback(recording, playback, result.delay)` when detected.
  - `is_loopback(recording: np.ndarray, playback: np.ndarray, delay: int) -> bool` — align by `delay`, least-squares gain match over the click section, residual energy / signal energy in dB ≤ `LOOPBACK_RESIDUAL_DB`.
  - `@dataclass(frozen=True) class OutputScan: output_channel: int; inputs: tuple[InputReturn, ...]`.
  - `@dataclass(frozen=True) class Route: output_channel: int; input_channel: int; peak_dbfs: float; other_inputs: tuple[int, ...]`; property `clipping -> bool` (`peak_dbfs >= CLIP_DBFS`).
  - `@dataclass(frozen=True) class FindResult: state: Literal["found", "several", "none"]; routes: tuple[Route, ...]; loopbacks: tuple[int, ...]; stopped_early: bool = False`; property `route -> Route | None` (the only route when "found").
  - `choose_route(scan: OutputScan, excluded_inputs: frozenset[int]) -> Route | None` — `None` when this output reached no usable input; otherwise the loudest detected, non-loopback, non-excluded input, with the other usable inputs in `other_inputs`.
  - `summarise(routes: Sequence[Route], loopbacks: Sequence[int], stopped_early: bool) -> FindResult` — 0 routes → "none", 1 → "found", more → "several".

- [ ] **Step 1: Write the failing tests.** Build signals with a helper `simulate(playback, delay, gain, lowpass=False, noise_db=None) -> np.ndarray` in the test file (shift by `delay`, scale, optional one-pole low-pass at ~8 kHz, optional white noise). Tests:

```python
@pytest.mark.parametrize("gain", [0.5, 0.03, 0.01])     # a reamp pad + low levels: −20 dBFS can return near −60 dBFS
def test_detection_works_at_the_find_level(gain):         # amplitude FIND_AMPLITUDE, low-pass, noise −90 dBFS
    r = analyse_input(simulate(play, 300, gain, True, -90), 1, play, pre)
    assert r.detected and r.delay == pytest.approx(300, abs=2) and not r.loopback

def test_exact_copy_is_a_loopback():                     # gain 0.98, no filter, no noise
    assert analyse_input(simulate(play, 120, 0.98), 3, play, pre).loopback

def test_clean_boost_near_unity_is_not_a_loopback():     # gain 1.0, low-pass, noise -90 dB
    assert not analyse_input(simulate(play, 300, 1.0, True, -90), 1, play, pre).loopback

def test_silence_is_not_detected():
    r = analyse_input(np.zeros_like(play), 2, play, pre)
    assert not r.detected and r.peak_dbfs is None

def test_choose_route_picks_the_loudest_usable_input():
    # inputs: 1 at -20 dB, 2 at -12 dB, 3 loopback, 4 excluded (timing loopback)
    route = choose_route(scan, frozenset({4}))
    assert (route.input_channel, route.other_inputs) == (2, (1,))

def test_choose_route_returns_none_when_nothing_usable():  # only a loopback and silence
    assert choose_route(scan_with_only_loopback, frozenset()) is None

def test_a_loud_return_is_found_and_flagged_as_clipping():  # Review Focus 5: peak -0.5 dB
    assert choose_route(loud_scan, frozenset()).clipping

def test_summarise_states():
    assert summarise([], [3], False).state == "none"
    assert summarise([route_a], [], False).state == "found"
    assert summarise([route_a, route_b], [], False).state == "several"
```

- [ ] **Step 2: Run, expect FAIL** — `.venv/bin/python -m pytest tests/test_find_route.py -q` → `ModuleNotFoundError: parametric_mac.find_route`.
- [ ] **Step 3: Implement `find_route.py`.** The padded cases (gain 0.03 and 0.01) decide the level: if detection fails at 0.1 only because of the level, raise `FIND_AMPLITUDE` to the lowest of `(0.1, 0.2, 0.45)` that passes all three gains, and write the level and the reason in a comment beside it. Change `ui/copy.py` to import the clip rule from `find_route`.
- [ ] **Step 4: Run, expect PASS.** Also run the coverage check: `.venv/bin/python -m pytest tests/test_find_route.py --cov=parametric_mac.find_route --cov-report=term-missing -q` → ≥ 80%.
- [ ] **Step 5: Commit** — `feat: analyse sound card returns to find the capture route`

---

### Task 2: Output scan (injectable audio, no Qt)

**Files:**
- Create: `parametric_mac/find_scan.py`
- Test: `tests/test_find_scan.py`

**Interfaces:**
- Consumes: Task 1 `find_playback`, `analyse_input`, `OutputScan`, `choose_route`, `FindResult`.
- Produces:
  - `PlayRecord = Callable[[np.ndarray, int, int], np.ndarray]` — `(playback, sample_rate, output_channel) -> recording` with shape `(frames, input_channels)`.
  - `playback_frame(playback: np.ndarray, output_channels: int, output_channel: int) -> np.ndarray` — shape `(frames, output_channels)`, zeros except the 1-based `output_channel` column. Raises `ValueError` for a channel outside `1…output_channels`.
  - `sounddevice_play_record(device_index: int, output_channels: int, input_channels: int, blocksize: int, latency, cancel: Callable[[], bool] | None) -> PlayRecord` — builds the output with `playback_frame` and makes the same full-width `sd.playrec` call as upstream `SounddeviceRecorder.playrec`, but returns the whole recording matrix. Poll `cancel` and raise `audio.CaptureCancelled`; call `audio._raise_on_dropout` after the stream.
  - `@dataclass(frozen=True) class ScanTarget: device_index: int; output_channels: int; input_channels: int; sample_rate: int; blocksize: int; latency: object; excluded_inputs: frozenset[int]` — plain values read on the GUI thread.
  - `scan_outputs(play_record: PlayRecord, sample_rate: int, output_channels: int, excluded_inputs: frozenset[int], progress=None, cancel=None) -> FindResult` — for output 1…N: check `cancel` (raise `CaptureCancelled`), play, analyse every input, `choose_route`. With `output_channels <= FULL_SCAN_OUTPUTS` scan every output and `summarise` all routes; with more, stop at the first route (`stopped_early=True`). Call `progress(k / N)` after each output.
  - `scan_target(target: ScanTarget, progress, cancel) -> FindResult` — 0 inputs or 0 outputs → "none" without playing; else builds `sounddevice_play_record` and calls `scan_outputs`. It reads nothing from Qt or CoreAudio.

- [ ] **Step 1: Write the failing tests** with a `FakeRig` play-record: output 2 → input 1 through a low-pass with gain 0.4 and noise −75 dB; input 3 is a digital loopback that copies whatever plays on any output; every other input gets noise only.

```python
def test_scan_finds_the_rig_route_and_ignores_the_digital_loopback():
    result = scan_outputs(FakeRig(outputs=4, inputs=4), 48000, 4, frozenset())
    assert (result.state, result.route.output_channel, result.route.input_channel) == ("found", 2, 1)
    assert 3 in result.loopbacks

def test_playback_frame_uses_exactly_one_output():
    frame = playback_frame(np.ones(10, np.float32), 6, 4)
    assert frame.shape == (10, 6) and np.flatnonzero(np.abs(frame).max(axis=0)).tolist() == [3]
    with pytest.raises(ValueError):
        playback_frame(np.ones(10, np.float32), 6, 7)

def test_scan_plays_each_output_once_in_order():
    rig = FakeRig(outputs=4, inputs=4); scan_outputs(rig, 48000, 4, frozenset())
    assert rig.played == [1, 2, 3, 4]

def test_a_timing_cable_on_another_output_gives_several_routes():   # Review Focus 6
    rig = FakeRig(outputs=4, inputs=4, extra_route=(3, 4))          # output 3 → input 4: an analog timing cable
    result = scan_outputs(rig, 48000, 4, frozenset())
    assert result.state == "several"
    assert {(r.output_channel, r.input_channel) for r in result.routes} == {(2, 1), (3, 4)}

def test_two_inputs_on_the_same_output_are_one_route():
    rig = FakeRig(outputs=4, inputs=4, extra_route=(2, 4))          # output 2 also reaches input 4, more quietly
    result = scan_outputs(rig, 48000, 4, frozenset())
    assert result.state == "found" and result.route.input_channel == 1 and result.route.other_inputs == (4,)

def test_large_devices_stop_at_the_first_route():
    rig = FakeRig(outputs=12, inputs=4); result = scan_outputs(rig, 48000, 12, frozenset())
    assert result.state == "found" and result.stopped_early and rig.played == [1, 2]

def test_scan_reports_none_when_nothing_returns():          # Review Focus 2: 1 output, 1 input, no cable
    assert scan_outputs(FakeRig(outputs=1, inputs=1, route=None), 48000, 1, frozenset()).state == "none"

def test_cancel_stops_the_scan():                           # Review Focus 1
    with pytest.raises(CaptureCancelled):
        scan_outputs(FakeRig(outputs=4, inputs=4), 48000, 4, frozenset(), cancel=lambda: True)

def test_progress_rises_to_one():
    seen = []; scan_outputs(FakeRig(outputs=4, inputs=4, route=None), 48000, 4, frozenset(), progress=seen.append)
    assert seen == sorted(seen) and seen[-1] == 1.0

def test_dropout_reaches_the_caller():                      # Review Focus 4
    with pytest.raises(AudioDropoutError):
        scan_outputs(FakeRig(outputs=2, inputs=2, dropout_on=1), 48000, 2, frozenset())

def test_device_without_inputs_or_outputs_is_none():        # Review Focus 2
    target = ScanTarget(0, 0, 2, 48000, 0, "low", frozenset())
    assert scan_target(target, None, None).state == "none"
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `find_scan.py`.** `sounddevice_play_record` is not unit-tested (it needs hardware); keep it a thin copy of the upstream call shape around the tested `playback_frame`, and mark it `# pragma: no cover` with a one-line reason.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat: scan sound card outputs one at a time to find the capture route`

---

### Task 3: Connect — the Find button

**Files:**
- Modify: `parametric_mac/ui/pages/connect.py`, `parametric_mac/ui/copy.py`, `parametric_mac/ui/shell.py` (`_mutating`)
- Test: `tests/test_ui_find.py`, `tests/test_copy.py`, `tests/test_ui_connect.py` (channel fields moved)

**Interfaces:**
- Consumes: Task 1 `FindResult`; Task 2 `device_scan`.
- Produces:
  - `copy.find_message(result: FindResult) -> str` — the verbatim copy from Global Constraints; for "found" with `other_inputs`, the "Found on inputs …" sentence; append `CLIP_TEXT` on a new line when `result.clipping`.
  - `copy.several_routes_text() -> str` ("More than one connection answered. Choose the one that goes through the reamp box and your gear.") and `copy.route_choice_text(route) -> str` ("Use Output X → Input Y").
  - `ConnectPageMixin`: `find_button` (outline; "Find my connection", and **Cancel search** while a scan runs), `find_result` (label), `find_try_again` and `find_manual` links ("Try again", "Choose channels myself"), `find_route_links` (a row of links, one per route, for "several"), `find_loopback_note` (in Expert settings), `_start_find()`, `_find_target() -> ScanTarget` (GUI thread: device, channel counts, live rate else `default_samplerate`, blocksize, latency, excluded loopback input when the loopback is on), `_scan_outputs(target, progress, cancel) -> FindResult` (the seam tests replace; calls `scan_target`), `_on_find_success(result)`, `_on_find_failure(message)`, `_on_find_cancelled()`, `_use_route(route)`.
- Behavior:
  - `find_button` is enabled only when `wire_check` is on, a device is selected, `_rate_problem() is None`, and nothing is busy.
  - `_start_find` reads `_find_target()` on the GUI thread, then runs `lambda progress, cancel: self._scan_outputs(target, progress, cancel)` through `self._run_worker(...)`, with `on_progress` driving `route_test_progress` (shown while running) and `disable=[self.check_level_button]`. While the worker runs, `find_button` reads **Cancel search**, stays enabled while a cancel token exists, and a click calls `self._cancel_token.cancel()` (spec §6.1: cancel at any time).
  - Success "several": show `several_routes_text()` and one link per route; a link calls `_use_route(route)` (the same as a single "found").
  - Success "found": set `output_channel_spin` / `input_channel_spin`, call `_save_audio_settings()`, clear the level check (`_route_fingerprint = None`, `_show_level(None)`), show `find_message`; list `loopbacks` in `find_loopback_note` ("Input N looks like a loopback — ignored", one per line; hidden when empty).
  - Success "none": show the none copy plus `find_try_again` and `find_manual`; channels unchanged.
  - Failure (device error, dropout): plain message "The sound card stopped during the search. Check that nothing else uses it, then try again." with **Try again**; channels unchanged. Cancel: "Search cancelled." channels unchanged.
  - `find_manual` opens the Connect Expert disclosure, which now holds the two channel fields (moved from stage 2, same plain labels).
  - Add `self.find_button` to `_mutating`; the device combo is already there.

- [ ] **Step 1: Write the failing tests** (`run_gui`, `_has_device`/`_device_sample_rate` stubbed as in `test_ui_connect.py`):
  - Unit (`test_copy.py`): `find_message` for found (2 → 1), for found with `other_inputs=(2,)`, for none, and for a clipping result (contains `CLIP_TEXT`).
  - GUI (`tests/test_ui_find.py`):
    - `find_button` is disabled until `wire_check` is on; disabled again with a sample-rate problem.
    - Replace `window._scan_outputs` with a function returning a found `FindResult(output 2, input 1, loopbacks (3,))`; click `find_button`; wait with `QTest.qWait` until `window._worker is None` (≤ 5 s). Then the spins read 2 and 1, `window._current_audio_settings().output_channel == 2`, `find_result.text().startswith("Found: Output 2 → Input 1.")`, the Expert note says "Input 3 looks like a loopback — ignored", and the level check is cleared.
    - A "none" result keeps the old channels and shows **Try again** and **Choose channels myself**; clicking the latter opens Expert settings and shows the channel fields.
    - Review Focus 1: a scan that raises `CaptureCancelled` leaves the channels and the saved audio settings unchanged and shows "Search cancelled."
    - Review Focus 4: a scan that raises `AudioDropoutError` shows the plain failure text and keeps the channels.
    - Review Focus 3: while a fake scan blocks on a `threading.Event`, `device_combo` and `check_level_button` are disabled and `find_button` reads "Cancel search" and is enabled; clicking it ends the scan with "Search cancelled." Set the event in a `finally` so a failed assertion cannot hang the test.
    - Review Focus 6: a "several" result shows two route links; clicking "Use Output 3 → Input 4" sets the spins to 3 and 4.
    - The worker seam receives a `ScanTarget`, not widgets (assert the type in the fake).
    - Review Focus 5: a found result with `peak_dbfs=-0.5` sets the channels and shows `CLIP_TEXT`.
  - Update `test_ui_connect.py` for the channel fields under Expert settings.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** per spec §4.2 stage 2 and mockup window 2: rename the stage to "Find the connection", add the found line, move the channel fields under Expert settings, and remove the Phase 1 fallback labels from stage 2.
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: find the sound card route from Connect`

---

### Task 4: Docs and screenshots

**Files:**
- Modify: `README.md` (walkthrough step 3 and troubleshooting), `scripts/render_native.py` (Connect with a found route), `docs/validation.md` (dated Phase 2 entry), `docs/screenshots/native/` (re-render)

- [ ] **Step 1:** README step 3, stage 2: "Click **Find my connection**. The app plays a quiet click on each output, one at a time, and listens on every input. It sets the channels for you and ignores inputs that only copy the output (a digital loopback). You can still set the channels by hand under **Expert settings**." Troubleshooting: "Find my connection finds nothing → check cables, power and that the checkbox steps are done; then use **Choose channels myself**."
- [ ] **Step 2:** `render_native.py`: replace `_scan_outputs` with a stub that returns a found result before the `connect-ready` shot, so the image shows "Found: Output 1 → Input 1."; re-render with `QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/render_native.py` and look at the Connect images in both modes.
- [ ] **Step 3:** Add a dated "Find my connection (Phase 2)" entry to `docs/validation.md`: tests, the level used, the loopback threshold, and "not yet verified on real sound cards".
- [ ] **Step 4:** Full suite → PASS. Commit — `docs: describe Find my connection`

---

## Self-review notes

- **Spec coverage:** §4.2 stage 2 (button, result, states: none, more than one input, too close to clipping, loopback ignored; Expert channels) → Tasks 1–3; §6.1 safety (checkbox gate, −20 dBFS, one output at a time, cancel), loopback residual test with one named constant and synthetic tests → Tasks 1–3; no-device and sample-rate states already exist from Phase 1 and stay.
- **Interfaces:** `FindResult` fields are used the same way in Tasks 1–3; `_scan_outputs(progress, cancel)` matches the upstream worker call shape `lambda progress, cancel: …`.
- **Not in this plan:** Match per test setting (Phase 3), playback (Phase 4).
