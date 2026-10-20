import re
from pathlib import Path

from parametric_mac.ui.copy import ROUTE_CLIP_DBFS, level_message, sample_rate_message

T = ROUTE_CLIP_DBFS


def test_sample_rate_message():
    text = sample_rate_message(44100, 48000)
    assert "44.1 kHz" in text and "48 kHz" in text
    assert sample_rate_message(48000, 48000) is None
    assert sample_rate_message(None, 48000) is None
    assert sample_rate_message(96000, None) is None


def test_level_message_uses_the_route_test_threshold():
    assert T == -1.0
    assert level_message(T + 0.1, T)[0] == "clip"
    assert level_message(T, T)[0] == "clip"
    state, text = level_message(-9.2, T)
    assert state == "ok" and text.startswith("Peak −9.2 dB")
    assert "Do not touch the sound card gain" in text


def test_no_umc22_text_in_the_app():
    root = Path(__file__).resolve().parents[1] / "parametric_mac"
    for path in root.rglob("*.py"):
        assert "umc22" not in path.read_text().lower(), path


def test_take_messages_never_suggest_changing_levels():
    from parametric_mac.ui.copy import CLIPPED_BODY, take_message
    clipped = take_message(True, ["Clipping detected"])
    assert clipped.kind == "clipped"
    assert clipped.body == ("This take clipped. Record it again. If it clips again, the level is too high for this pedal. "
                            "Start a new capture and set a lower level on Connect.") == CLIPPED_BODY
    assert take_message(False, []).kind == "ok"
    warning = take_message(False, ["Delay disagreement between loopback and return"])
    assert warning.kind == "warning" and "Delay disagreement" in warning.body
    for message in (clipped, take_message(False, []), warning):
        assert "reamp box output down" not in message.body.lower()
        assert not re.search(r"\bgain\b", message.body.lower()), message.body


def test_parse_epoch_finished_lines():
    from parametric_mac.ui.copy import EpochPoint, parse_epoch_finished
    assert parse_epoch_finished("Epoch 3 finished. ESR=0.0123, MSE=0.0001") == EpochPoint("", 3, 0.0123)
    assert parse_epoch_finished("Epoch 203 finished. nano: ESR=0.02, MSE=1e-05") == EpochPoint("nano", 203, 0.02)
    assert parse_epoch_finished("Epoch 3 finished. standard: val_loss=0.5") == EpochPoint("standard", 3, 0.5)
    assert parse_epoch_finished("Epoch 3/200 started") is None
    assert parse_epoch_finished("Epoch 4 finished. ") is None


def test_check_errors_and_minutes_left():
    from parametric_mac.ui.copy import check_errors, minutes_left
    assert check_errors("x\nERROR: Missing take 3\nWARNING: y\nERROR: Clipped take 9") == ("Missing take 3", "Clipped take 9")
    assert check_errors("Ready for training.") == ()
    assert minutes_left([60.0], 5) is None
    assert minutes_left([60.0, 66.0, 54.0], 10) == 10
    assert minutes_left([30.0, 30.0], 3) == 2


def test_check_errors_reads_cli_exceptions():
    from parametric_mac.ui.copy import check_errors
    assert check_errors("Error: capture_project.json is missing\n") == ("capture_project.json is missing",)


def test_metric_lines_keep_the_honest_wording():
    from parametric_mac.ui.copy import CHECKPOINT_NOTE, metric_lines
    single = metric_lines({"epoch": 2, "ESR": 0.031})
    assert single[0] == "Last logged validation ESR: 0.031 · epoch 2"
    assert any("not a separate evaluation" in line for line in single)
    tiers = metric_lines({"tiers": {"standard": {"epoch": 2, "ESR": 0.021}, "nano": {"epoch": 2}}})
    assert tiers[0] == "Standard: last validation ESR 0.021 · epoch 2"
    assert tiers[1] == "Nano: no validation ESR recorded"
    assert metric_lines({}) == ("No validation metric recorded for this run. Inspect training.log for details.",)
    assert CHECKPOINT_NOTE == "These settings also chose the best training round, so the match can look better than on new settings."


def test_find_messages_are_the_spec_copy():
    from parametric_mac.find_route import FindResult, Route
    from parametric_mac.ui.copy import (
        CLIP_TEXT, find_message, loopback_note, route_choice_text, several_routes_text, stopped_early_note,
    )
    found = FindResult("found", (Route(2, 1, -18.0, ()),), ())
    assert find_message(found) == "Found: Output 2 → Input 1."
    two = FindResult("found", (Route(2, 1, -18.0, (2,)),), ())
    assert find_message(two) == "Found: Output 2 → Input 1.\nFound on inputs 1 and 2. Using input 1 (louder)."
    three = FindResult("found", (Route(2, 3, -18.0, (4, 1)),), ())
    assert "Found on inputs 1, 3 and 4. Using input 3 (louder)." in find_message(three)
    none = FindResult("none", (), (3,))
    assert find_message(none) == ("No signal came back. Check the cables, and check that the reamp box and "
                                  "the pedal have power.\nIf your gear is quiet or dark, turn its volume or the "
                                  "sound card input gain up a little, then try again.")
    silent = FindResult("none", (), (), silent=True)
    assert find_message(silent) == ("Every input recorded total silence. Allow microphone access for the app that "
                                    "opened Parametric (usually Terminal or Python) in System Settings › Privacy & "
                                    "Security › Microphone, then try again.")
    # Spec §4.3: once recording has started the levels stay fixed, so no hint to turn anything up.
    assert find_message(none, levels_locked=True) == ("No signal came back. Check the cables, and check that the "
                                                      "reamp box and the pedal have power.")
    clipping = FindResult("found", (Route(2, 1, -0.5, ()),), ())
    assert find_message(clipping) == "Found: Output 2 → Input 1.\n" + CLIP_TEXT
    several = FindResult("several", (Route(2, 1, -18.0, ()), Route(3, 4, -30.0, ())), ())
    assert find_message(several) == several_routes_text() == (
        "More than one connection answered. Choose the one that goes through the reamp box and your gear.")
    assert route_choice_text(Route(3, 4, -30.0, ())) == "Use Output 3 → Input 4"
    assert loopback_note((3, 5)) == "Input 3 looks like a loopback — ignored\nInput 5 looks like a loopback — ignored"
    assert loopback_note(()) == ""
    assert stopped_early_note(12) == "Stopped at the first answer: this sound card has 12 outputs."
    early = FindResult("found", (Route(2, 1, -18.0, ()),), (), True)
    assert find_message(early, 12) == ("Found: Output 2 → Input 1.\nStopped at the first answer: this sound card "
                                       "has 12 outputs. Check that Output 2 goes to the reamp box.")
