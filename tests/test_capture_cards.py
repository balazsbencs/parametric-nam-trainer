import pytest
from nam.capture.audio import DeviceInfo

from parametric_mac.capture_cards import capture_cards, card_label


def dev(index, inputs, outputs, name="USB Audio CODEC", api="Core Audio", rate=48000):
    return DeviceInfo(index, name, api, inputs, outputs, rate)


def test_split_pair_and_label():
    card, = capture_cards([dev(2, 0, 2), dev(3, 2, 0)]).cards
    assert (card.input_index, card.output_index, card.split) == (3, 2, True)
    assert card.default_samplerate == 48000
    assert card_label(card) == "USB Audio CODEC (Core Audio) · 2 in · 2 out"


def test_duplex_and_order():
    cards = capture_cards([dev(4, 2, 2, "BlackHole"), dev(2, 0, 2), dev(3, 2, 0)]).cards
    assert [c.name for c in cards] == ["USB Audio CODEC", "BlackHole"]
    assert not cards[1].split and cards[1].input_index == cards[1].output_index == 4


@pytest.mark.parametrize("devices", [
    [dev(0, 2, 0)], [dev(0, 0, 2)],
    [dev(0, 2, 0), dev(1, 0, 2, api="Other")],
])
def test_unpaired_halves(devices):
    result = capture_cards(devices)
    assert result.cards == result.ambiguous == ()


@pytest.mark.parametrize("devices", [
    [dev(0, 2, 0), dev(1, 2, 0), dev(2, 0, 2), dev(3, 0, 2)],
    [dev(0, 2, 2), dev(1, 2, 0)], [dev(0, 2, 2), dev(1, 2, 2)],
])
def test_ambiguous_names(devices):
    result = capture_cards(devices)
    assert not result.cards and result.ambiguous == ("USB Audio CODEC",)


@pytest.mark.parametrize("direction,transport", [("input", "blue"), ("output", "blea")])
def test_bluetooth_is_not_listed(direction, transport):
    result = capture_cards([dev(0, 2, 0), dev(1, 0, 2)], {("USB Audio CODEC", direction): transport})
    assert result.cards == result.ambiguous == ()


def test_recording_resolves_each_half(monkeypatch, tmp_path):
    from nam.capture import audio
    from nam.capture.project import CaptureProject, AudioSettingsModel
    from nam.capture.session import CaptureSession
    monkeypatch.setattr(audio, "list_devices", lambda: [dev(2, 0, 2), dev(3, 2, 0)])
    project = CaptureProject(name="Test", knobs=[], audio=AudioSettingsModel(
        input_device="USB Audio CODEC", output_device="USB Audio CODEC", host_api="Core Audio"))
    assert CaptureSession(project, tmp_path)._resolve_devices() == {"output_device": 2, "input_device": 3}


def test_mixed_mac_device_table():
    devices = [dev(0, 1, 0, "MacBook Pro Microphone"), dev(1, 0, 2, "MacBook Pro Speakers"),
               dev(2, 0, 2), dev(3, 2, 0), dev(4, 1, 0, "AirPods Pro", rate=24000),
               dev(5, 0, 2, "AirPods Pro"), dev(6, 2, 2, "BlackHole 2ch"),
               dev(7, 0, 2, "Monitor"), dev(8, 0, 2, "HDMI"), dev(9, 4, 4, "Aggregate Device")]
    transports = {("AirPods Pro", "input"): "blue", ("AirPods Pro", "output"): "blue"}
    assert [c.name for c in capture_cards(devices, transports).cards] == [
        "USB Audio CODEC", "BlackHole 2ch", "Aggregate Device"]
