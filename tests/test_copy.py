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
