# Split interfaces on Connect: one sound card, two macOS devices

Date: 2026-10-20
Status: approved by the user on 2026-10-20

Mockups: `docs/design/2026-10-20-split-interfaces/connect.png` (+ `.html`, made by `make_mockups.py` in the same folder), windows A–E, drawn on the real Phase 2 Connect layout. Where a mockup and this document differ, this document wins.

## 1. Intent and the why

The user wants a generic, open-source app that works with any sound card. Today Connect lists only devices that have both inputs and outputs (upstream `duplex_devices`). Some USB interfaces appear to macOS as **two devices with the same name**: one with only outputs and one with only inputs. On the user's Mac, the Behringer UMC22 shows as "USB Audio CODEC" twice (device 2: 0 in / 2 out; device 3: 2 in / 0 out). Connect therefore does not list it at all. The only workaround is an Aggregate Device in Audio MIDI Setup, which a normal user would never find.

Upstream's own message assumes the opposite ("On macOS, where CoreAudio makes every interface duplex, it just means nothing is plugged in"). That assumption is wrong for this class of interface.

What the user wants (confirmed in chat): the app shows such an interface as **one sound card**, by its name, like any other card. The user never has to think about input and output devices.

## 2. Goals, non-goals, anti-goals

**Goals**
- Connect lists a split interface as one entry, named like the interface ("USB Audio CODEC (Core Audio)"), in the same list as duplex devices (window A).
- Everything after the choice works as now: Find my connection, the level check, recording, the reopen rule, and training (window B).
- A reopened project finds the same card again.
- Clear messages for the new failure cases: two cards with the same name (window C), halves at different sample rates (window D), and a reopened project whose card is missing (window E).

**Non-goals**
- Mixing two different sound cards (one card's output with another card's input). Two cards run on two clocks, so the recording would drift slowly and quietly damage the captures. (User confirmed.)
- Windows or Linux behavior. The app is macOS only.
- Changes to the upstream package in `.upstream`.

**Anti-goals** (a failure even if it technically works)
- The app pairs the wrong halves, for example the input of one UMC22 with the output of another, identical UMC22.
- The app silently uses a different card than the one the user chose.
- The user still has to create an Aggregate Device for a common interface.

## 3. Constraints

- Stack: Python 3.12 `.venv`, PySide6 6.12, the pinned upstream `nam.capture` in `.upstream` (unchanged). `MacWindow` subclasses the upstream `MainWindow`; the change lives in `parametric_mac` overrides, as Phase 1 and Phase 2 did.
- The user's coding rules: files 200–400 lines (800 max), functions under 50 lines, frozen dataclasses, explicit error handling, TDD with 80% coverage for new non-Qt modules.
- Branching: this work depends on Phase 2 (Find my connection, PR #6), because Find's scan target changes. It does not depend on Phases 3–4.
- Measured on this Mac: PortAudio opens a stream with the UMC22 input half and output half as two devices (input latency about 99 ms, output about 66 ms, not started, nothing played). The app already measures the round-trip delay on every take and refuses a take with a dropout.

## 4. The design (decided)

### 4.1 Which devices form one card
- A **capture card** is either a duplex device (as now) or a **split pair**.
- A split pair is exactly one input-only device and exactly one output-only device with the **same name and the same host API**, where no duplex device has that name.
- **A name must point to exactly one device in each direction** (within the host API). The reason: the project saves only the name and the host API, and upstream recording finds each direction with `find_device(name, kind, host_api)`, which returns the first match. If a name has two input devices or two output devices — two identical interfaces, a duplex card plus a one-way device with the same name, or two identical duplex cards — recording could use a different device than the one Find and the level check tested. *(Designer's call, from the anti-goal "the app silently uses a different card":)* such a name is **not listed at all**, and Connect shows (window C): "Two sound cards are called “{name}”, so the app cannot tell them apart. Unplug one, then press refresh." This also hides two identical duplex cards, which today appear twice but cannot be told apart by recording.
- The window C message is a notice only. It does not block other cards: the user can choose and use any listed card (window C shows BlackHole 2ch chosen, with Find on).
- An input-only or output-only device with no partner is not listed (as now).
- *(Designer's call, found while planning:)* **a Bluetooth pair is never a capture card.** AirPods appear to macOS exactly like a split interface ("AirPods Pro" input-only at 24 kHz and output-only at 48 kHz). Listing them would let Find and the level check play into the user's ears. A pair is dropped when either half has the CoreAudio transport type Bluetooth (`'blue'`) or Bluetooth LE (`'blea'`); when the transport type is unknown, the normal rule applies.
- Existing Aggregate Devices stay in the list as ordinary duplex devices.

### 4.2 The list
- One entry per capture card, labeled like now ("{name} ({host API})"). *(Designer's call:)* each entry also shows its channel counts ("2 in · 2 out"), so two cards are easy to tell apart. For a split pair, the input count comes from the input half and the output count from the output half.
- The "No sound card found" message shows only when the list of capture cards is empty. Upstream's own message ("nothing is plugged in") looks only at duplex devices, so with only a split interface plugged in it would wrongly show; Connect replaces it.

### 4.3 Saving and reopening
- The project saves the card's name in both `input_device` and `output_device` and its host API in `host_api`, exactly as now. Upstream `CaptureSession` already resolves each direction by name **and** direction (`audio.find_device(name, kind="input"|"output", host_api=…)`), so recording uses the correct half with no upstream change. A test must prove this for a split pair.
- On reopen, Connect selects the entry with that name (as now).
- *(Designer's call, from the anti-goals:)* **if the saved name is not in today's list** (the card is unplugged, or the name is now ambiguous), Connect selects **no** card, shows (window E) "This project used “{name}”, which is not connected. Plug it in, then press refresh, or choose another sound card.", keeps Find and the level check off, and does **not** overwrite the saved device until the user chooses a card. Today upstream quietly keeps the first card in the list selected, and the next save overwrites the project's device; that must stop. A refresh that brings the card back selects it again.

### 4.4 Sample rates
- Each half has its own rate in Audio MIDI Setup. Both halves must equal the capture signals' rate (48 kHz) before Connect is ready (the existing Phase 1 rule).
- If one half differs, the existing rate message names that half (window D): "The input of your sound card runs at 44.1 kHz. Set it to 48 kHz in Audio MIDI Setup, then check again." ("output" for the other half), with the existing **Open Audio MIDI Setup** button.
- The rate label next to the list shows one rate when both halves agree, and "in 44.1 kHz · out 48 kHz" when they differ.
- Upstream reads live rates into a dictionary keyed by **name** (`current_device_sample_rates`), so two halves with one name collide. The app must read the live rate of each half separately (for example by CoreAudio device ID and scope). The exact method is the builder's call; falling back to PortAudio's `default_samplerate` per half is acceptable when live rates are not available.

### 4.5 Find my connection
- Find's scan target carries the input device index and the output device index separately. The stream opens with `device=(input_index, output_index)` and the same full channel widths as now. One output at a time, −20 dBFS, cancel at any time: all Phase 2 rules stay.

### 4.6 Help text and docs
- "Show me how to fix it" on Connect gains one line for window C's case.
- The UMC22 guide (`docs/hardware-umc22.md`) no longer suggests an Aggregate Device; it says the UMC22 appears as "USB Audio CODEC".
- README troubleshooting: "Your interface is missing from the list" → press refresh; if two identical interfaces are plugged in, unplug one.

## 5. Left to the builder
- How the live per-half rate is read (§4.4).
- How the pairing result is represented (a new frozen dataclass that carries both halves is expected), and how it is shown in the combo box, inside the mockup style.
- Where the device index each direction needs is looked up, as long as it is resolved fresh at use time (indexes shift when hardware changes).
- Test structure, inside the user's TDD and coverage rules.

## 6. Verification
- Unit tests for the pairing rules: a duplex device; a split pair; twins; a lone half; a name shared by a duplex device and a half; different host APIs.
- A test that a project saved with a split pair resolves to the input half and the output half through upstream `find_device`.
- Unit tests for the uniqueness rule: two identical split interfaces; a duplex card plus a one-way device with its name; two identical duplex cards.
- GUI tests for windows A–E with a stubbed device list, including: the saved card is missing on reopen → nothing selected, nothing saved, Find off; refresh with the card back → selected again.
- Hardware check on the user's Mac with the UMC22 (not automated): it appears in Connect, Find returns Output 1 → Input 1, the level check passes, and one take records with no dropout.
