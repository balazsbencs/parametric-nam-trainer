# Split Interfaces on Connect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect lists an interface that macOS shows as two one-direction devices with one name (for example the UMC22, "USB Audio CODEC") as one sound card, and everything after the choice works as now.

**Architecture:** A pure module pairs PortAudio devices into "capture cards" and drops ambiguous names. Connect fills its list from it, reads each half's live sample rate separately, and never selects or saves a card the user did not choose. Find opens its stream with the input half and the output half. Upstream recording already resolves each direction by name, so `.upstream` stays unchanged.

**Tech Stack:** Python 3.12 `.venv`, PySide6 6.12, the pinned upstream `nam.capture` (`.upstream`), sounddevice/PortAudio, CoreAudio through `ctypes` (as upstream does), pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-split-interfaces-design.md` (approved 2026-10-20).

**Mockups:** `docs/design/2026-10-20-split-interfaces/connect.png` (+ `.html`, `make_mockups.py`), windows A–E.

**Branch:** implement on a branch from `feat/find-my-connection` (PR #6): Task 4 changes Find's scan target. Independent of the Phase 3–4 plans.

## Global Constraints

- Run with `.venv/bin/python`; tests with `.venv/bin/python -m pytest -q`. GUI tests use `tests/gui_harness.run_gui`, stub the device table, and must print "OK". No test plays or records sound.
- No new dependency. No change under `.upstream`. No color literals outside `ui/tokens.py`. Files ≤ 800 lines, functions < 50 lines, frozen dataclasses, type annotations; 80% coverage for `capture_cards.py` and the pure part of `device_rates.py`.
- **Pairing (spec §4.1):** a capture card is a duplex device, or exactly one input-only plus exactly one output-only device with the same name and host API. **A name must point to exactly one device in each direction** within its host API; otherwise none of its devices is listed. **A pair with a Bluetooth half (`'blue'` or `'blea'`) is never a card** (AirPods look exactly like a split interface).
- Mixing two different cards is out of scope (spec §2).
- **Copy (spec §4, verbatim):**
  - window C: "Two sound cards are called “{name}”, so the app cannot tell them apart. Unplug one, then press refresh."
  - window D: "The {input|output} of your sound card runs at {rate}. Set it to {file rate} in Audio MIDI Setup, then check again." (rates formatted like the existing `copy._khz`, for example "44.1 kHz")
  - window E: "This project used “{name}”, which is not connected. Plug it in, then press refresh, or choose another sound card."
  - list entry: "{name} ({host API}) · {n} in · {m} out"; empty selection placeholder: "Choose a sound card"; rate label when halves differ: "in 44.1 kHz · out 48 kHz".
  - "Show me how to fix it" gains: "Two sound cards with the same name: unplug one, then press refresh."
- The window C notice never blocks other cards (spec §4.1).
- A reopened project whose card is missing selects nothing, keeps Find and the level check off, and never overwrites the saved device (spec §4.3).
- Commits: `<type>: <description>`, no attribution trailer. Gate every commit on a green full suite.

## Review Focus

1. **Device indexes shift when hardware changes without a refresh.** A card built at the last refresh can hold indexes that now point to another device; Find would play on it. Find must resolve both indexes fresh at click time and refuse an ambiguous or missing name. → Task 4 test.
2. **A saved card is missing or became ambiguous on reopen** (unplugged, or a second identical card plugged in). Nothing is selected, nothing is saved, Find and the level check are off; a refresh with the card back selects it. → Task 3 tests.
3. **The halves run at different rates** while the label shows one. Find, the level check and Next stay off, and the message names the wrong half. → Tasks 2–3 tests.
4. **Recording uses the halves the user chose.** Upstream `CaptureSession._resolve_devices` must return the output half for "output" and the input half for "input". → Task 1 test.
5. **Two identical duplex cards that appear today disappear** and a project that used that name opens in window E's state, not on a random card. → Task 3 test.

---

### Task 1: `capture_cards.py` — pair the devices (no Qt)

**Files:**
- Create: `parametric_mac/capture_cards.py`
- Test: `tests/test_capture_cards.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class CaptureCard: name: str; host_api: str; input_index: int; output_index: int; max_input_channels: int; max_output_channels: int; input_default_rate: float; output_default_rate: float; split: bool` with property `default_samplerate -> float` (= `input_default_rate`; upstream GUI code reads it). It carries the fields upstream reads from the device combo's item data (`name`, `host_api`, `max_input_channels`, `max_output_channels`, `default_samplerate`), so upstream methods keep working with it.
  - `@dataclass(frozen=True) class CardList: cards: tuple[CaptureCard, ...]; ambiguous: tuple[str, ...]` — `ambiguous` holds names (sorted) dropped by the uniqueness rule.
  - `capture_cards(devices: Sequence[DeviceInfo], transports: Mapping[tuple[str, str], str] | None = None) -> CardList` — cards keep PortAudio's order (by the lower index of the pair). `transports` maps `(name, "input"|"output")` to a CoreAudio transport fourcc (Task 2 reads it); a split pair is dropped (not ambiguous, just not listed) when either half is `"blue"` or `"blea"`; unknown transports keep the normal rule.
  - `card_label(card: CaptureCard) -> str` → "{name} ({host_api}) · {n} in · {m} out".

- [ ] **Step 1: Write the failing tests** (build `nam.capture.audio.DeviceInfo` values by hand):

```python
def test_duplex_device_is_one_card(): ...                       # BlackHole 2ch 2/2 → split False, same index both ways
def test_split_pair_is_one_card():
    cards = capture_cards([out_half(2, "USB Audio CODEC"), in_half(3, "USB Audio CODEC")]).cards
    assert [(c.name, c.input_index, c.output_index, c.split) for c in cards] == [("USB Audio CODEC", 3, 2, True)]
def test_lone_half_is_not_listed(): ...                         # MacBook Pro Microphone (in only) → no card, not ambiguous
def test_identical_split_twins_are_ambiguous(): ...             # two in-halves + two out-halves named alike → no card, ambiguous
def test_duplex_plus_half_with_one_name_is_ambiguous(): ...
def test_identical_duplex_cards_are_ambiguous(): ...
def test_other_host_api_does_not_pair(): ...                    # in-half "X" Core Audio + out-half "X" other API → no card
def test_bluetooth_pair_is_not_a_card(): ...                    # AirPods in 24 kHz + out 48 kHz with transports 'blue' → no card
def test_this_macs_real_table():                                # the ten devices listed on 2026-10-20, AirPods 'blue'
    assert [c.name for c in capture_cards(MAC_TABLE, MAC_TRANSPORTS).cards] == ["USB Audio CODEC", "BlackHole 2ch", "Aggregate Device"]
def test_label():
    assert card_label(card) == "USB Audio CODEC (Core Audio) · 2 in · 2 out"
def test_recording_resolves_each_half(monkeypatch, tmp_path):   # Review Focus 4
    # monkeypatch nam.capture.audio.list_devices to the two halves; a CaptureSession whose project audio has
    # input_device = output_device = "USB Audio CODEC", host_api "Core Audio"
    assert session._resolve_devices() == {"output_device": 2, "input_device": 3}
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Group devices by `(name, host_api)`; per group count input-capable and output-capable devices (a duplex device counts in both); a group is usable only when each count is exactly 1.
- [ ] **Step 4: Run, expect PASS**; coverage ≥ 80%.
- [ ] **Step 5: Commit** — `feat: pair one-direction devices into capture cards`

---

### Task 2: `device_rates.py` — each half's live sample rate

**Files:**
- Create: `parametric_mac/device_rates.py`
- Modify: `parametric_mac/ui/copy.py`
- Test: `tests/test_device_rates.py`, `tests/test_copy.py`

**Interfaces:**
- Consumes: Task 1 `CaptureCard`.
- Produces:
  - `Direction = Literal["input", "output"]`.
  - `live_half_rates() -> dict[tuple[str, Direction], float]` — macOS only, through CoreAudio like upstream `_coreaudio_sample_rates` (`.upstream/nam/capture/audio.py:255`), keyed by `(name, direction)`: a CoreAudio device counts as input when its `kAudioDevicePropertyStreams` (`"stm#"`) in input scope (`"inpt"`) is non-empty, and as output for output scope (`"outp"`). Returns `{}` off macOS or on any CoreAudio error (log it at debug level).
  - `live_half_transports() -> dict[tuple[str, Direction], str]` — the same CoreAudio walk, reading `kAudioDevicePropertyTransportType` (`"tran"`, global scope) as a 4-character string (for example `"usb "`, `"blue"`, `"bltn"`, `"virt"`, `"grup"`); `{}` off macOS or on error. Share the device walk with `live_half_rates`.
  - `card_rates(card: CaptureCard, live: Mapping[tuple[str, Direction], float]) -> tuple[int | None, int | None]` — (input rate, output rate): the live value, else that half's default rate, rounded; `None` when the host API does not report a current rate (upstream `reports_current_sample_rate`).
  - `copy.card_rate_message(input_rate: int | None, output_rate: int | None, file_rate: int | None) -> str | None` — `None` when every known rate equals `file_rate`; else the window D text for the first wrong half (input first). Duplex cards pass the same rate twice and keep the existing `sample_rate_message` wording ("Your sound card runs at …").
  - `copy.card_rate_label(input_rate: int | None, output_rate: int | None) -> str` — "48 kHz" when equal, "in 44.1 kHz · out 48 kHz" when not, "" when unknown.

- [ ] **Step 1: Write the failing tests:**
  - `card_rates` uses live values per direction, falls back per half, returns `None` for ASIO.
  - `card_rate_message(44100, 48000, 48000)` == "The input of your sound card runs at 44.1 kHz. Set it to 48 kHz in Audio MIDI Setup, then check again."; `(48000, 44100, 48000)` names "output"; `(48000, 48000, 48000)` is `None`; a duplex card at 44.1 kHz keeps today's text.
  - `card_rate_label` cases above.
  - On macOS, `live_half_rates()` and `live_half_transports()` return dicts whose keys are `(str, "input"|"output")` tuples (smoke test; skip off macOS).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Keep the `ctypes` code in one function under 50 lines by reusing small helpers; mark only the CoreAudio calls `# pragma: no cover - needs CoreAudio`.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat: read the sample rate of each half of a sound card`

---

### Task 3: Connect lists capture cards (mockup windows A, C, D, E)

**Files:**
- Create: `parametric_mac/ui/pages/connect_cards.py` (`ConnectCardsMixin`; `ConnectPageMixin` inherits it, like `ConnectFindMixin`)
- Modify: `parametric_mac/ui/pages/connect.py` (rate state and label, help text), `parametric_mac/ui/copy.py`
- Test: `tests/test_ui_cards.py`, `tests/test_ui_connect.py`

**Interfaces:**
- Consumes: Task 1 `capture_cards`, `card_label`, `CardList`; Task 2 `live_half_rates`, `card_rates`, `card_rate_message`, `card_rate_label`.
- Produces (overrides of upstream `MainWindow` methods, same names):
  - `_populate_device_combo(self, combo, devices) -> None` — for `device_combo`, ignore upstream's duplex list: fill from `capture_cards(self._devices, live_half_transports())` with `card_label` text and the `CaptureCard` as item data; store `self._card_list`; set the placeholder "Choose a sound card".
  - `_refresh_devices` (existing override) sets `no_devices_label` from `self._card_list` only: the existing `NO_DEVICE_TEXT` when it has no cards, hidden otherwise. Upstream's duplex-only message never shows next to a listed split card.
  - `_select_combo_by_name(self, combo, name) -> None` — select the card with that name; if the name is not listed, set the index to −1 and remember `self._missing_card = name` (else `None`).
  - `_save_audio_settings(self) -> None` — when no card is selected, do nothing (the saved device stays); else upstream's save.
  - `_device_rate(self, device, live) -> int | None` — for a `CaptureCard`, the half whose rate differs from the project file rate, else the input half's rate (uses `card_rates` and `self._live_half_rates`); keeps upstream `_current_sample_rate_warnings` correct.
  - `_update_live_device_rates(self) -> None` — also refreshes `self._live_half_rates = live_half_rates()`.
  - Widgets: `card_notice` (warn label under the list: window C text for each ambiguous name, then window E text when `_missing_card`); the rate label uses `card_rate_label`; the stage message uses `card_rate_message`.
- Behavior:
  - Window C's notice does not change `_has_device()` or any enable rule for other cards.
  - Window E: `_has_device()` is false, so Find, Check level and Next stay off (existing rules); choosing a card clears `_missing_card` and saves.
  - Window D: the existing rate rule (`_rate_problem`) uses `card_rate_message`, so Find, Check level and Next stay off.

- [ ] **Step 1: Write the failing tests** (`run_gui`; stub `nam.capture.gui.main._list_devices` — or the method that fills `self._devices` — to return fixed `DeviceInfo` lists; stub `live_half_rates`):
  - A: devices = BlackHole (duplex), "USB Audio CODEC" out-half 2 + in-half 3, MacBook Pro Microphone (in only) → the list holds exactly two entries, "BlackHole 2ch (Core Audio) · 2 in · 2 out" and "USB Audio CODEC (Core Audio) · 2 in · 2 out"; choosing the codec saves `input_device == output_device == "USB Audio CODEC"`.
  - A2 (only a split interface): devices = the two codec halves, MacBook Pro Microphone and MacBook Pro Speakers → the codec is the only entry and `no_devices_label` is hidden.
  - C: two identical codec pairs → no codec entry; `card_notice` has the window C text with the name; BlackHole chosen, wire check on → `find_button` enabled.
  - D: live rates `{("USB Audio CODEC","input"): 44100, ("USB Audio CODEC","output"): 48000}` and a project at 48 kHz → the message names "input", the label reads "in 44.1 kHz · out 48 kHz", `find_button`, `check_level_button` and `connect_button` disabled.
  - E (Review Focus 2, 5): a project saved with "USB Audio CODEC", reopened with only BlackHole present → `device_combo.currentIndex() == -1`, the window E text, Find off, and the project file still names "USB Audio CODEC"; refresh with the codec back → selected, notice gone.
  - E after twins: same project, two identical codec pairs present → window E state (plus the window C notice).
  - Help text contains the new line.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** to match windows A, C, D and E of `connect.png`.
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: list split interfaces as one sound card on Connect`

---

### Task 4: Find plays on the output half and listens on the input half (window B)

**Files:**
- Modify: `parametric_mac/find_scan.py`, `parametric_mac/ui/pages/connect_find.py`
- Test: `tests/test_find_scan.py`, `tests/test_ui_find.py`

**Interfaces:**
- Consumes: Task 1 `CaptureCard`; upstream `nam.capture.audio.find_device`.
- Produces (changes to Phase 2 names):
  - `ScanTarget` field `device_index: int` becomes `input_index: int; output_index: int` (same position, so `ScanTarget(input_index, output_index, output_channels, input_channels, sample_rate, blocksize, latency, excluded_inputs)`).
  - `sounddevice_play_record(input_index: int, output_index: int, output_channels: int, input_channels: int, blocksize: int, latency, cancel) -> PlayRecord` — `sd.playrec(..., device=(input_index, output_index), ...)`.
  - `scan_target` passes both indexes.
  - `_find_target()` resolves both indexes **fresh** with `find_device(card.name, kind=…, host_api=card.host_api)`; if either lookup fails, or `capture_cards(list_devices())` no longer lists that name, it returns `None` and Find shows `FIND_FAILED_TEXT` with **Try again** (no scan starts).

- [ ] **Step 1: Write the failing tests:**
  - `test_scan_target_passes_the_device_values_in_order` (Phase 2) updated: `ScanTarget(3, 2, 2, 2, RATE, 256, "low", frozenset())` → the factory receives `(3, 2, 2, 2, 256, "low", cancel)`.
  - Review Focus 1: the card in the combo holds `input_index=3, output_index=2`, but the stubbed fresh device table now has the halves at 5 and 4 → the recorded `ScanTarget` has `(5, 4)`; with the halves gone → no scan, the failure text.
  - Window B: a split card chosen, a found result → "Found: Output 1 → Input 1." as before.
  - Update the Phase 2 `tests/test_ui_find.py` `SETUP` (and the second fake device in its device-change block): it adds `DeviceInfo` values straight to `device_combo`, which the fresh lookup cannot find. Stub the device table instead and let the combo fill from it; assert on `target.input_index` / `target.output_index` where it asserted `device_index`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite → PASS.**
- [ ] **Step 5: Commit** — `feat: find the connection on a split interface`

---

### Task 5: Docs, screenshots and the hardware check

**Files:**
- Modify: `scripts/render_native.py` (its stub sound card becomes a `CaptureCard`; add a `connect-split` shot of window A's list state), `README.md` (troubleshooting row: "Your interface is missing from the list"), `docs/hardware-umc22.md` (the UMC22 appears as "USB Audio CODEC"; no Aggregate Device), `docs/validation.md` (dated entry), `docs/screenshots/native/`.

- [ ] **Step 1:** Update `render_native.py`; render offscreen; compare Connect with windows A and B in both themes.
- [ ] **Step 2:** Update the docs.
- [ ] **Step 3:** Full suite → PASS. Commit — `docs: describe split interfaces on Connect`
- [ ] **Step 4 (the user, with hardware):** UMC22 plugged in, no Aggregate Device: it appears as "USB Audio CODEC (Core Audio) · 2 in · 2 out"; Find returns Output 1 → Input 1; the level check passes; one take records with no dropout. Write the result in `docs/validation.md`.

---

## Self-review notes

- **Spec coverage:** §4.1 pairing and uniqueness → Task 1; §4.2 list and counts → Tasks 1, 3; §4.3 saving, reopening, missing card → Tasks 1 (recording resolution), 3; §4.4 per-half rates → Tasks 2–3; §4.5 Find → Task 4; §4.6 help and docs → Tasks 3, 5; §6 verification → Tasks 1–5.
- **Interfaces:** Task 4 renames Phase 2's `ScanTarget.device_index`; every Phase 2 caller (`scan_target`, `_find_target`, tests, `render_native.py`) is listed in Tasks 4–5.
