import sys
import pytest
from parametric_mac import device_rates
from parametric_mac.capture_cards import CaptureCard
from parametric_mac.ui.copy import card_rate_label, card_rate_message


def card(api="Core Audio"):
    return CaptureCard("USB", api, 3, 2, 2, 2, 44100, 48000, True)


def test_rates_use_each_half_and_fallback():
    assert device_rates.card_rates(card(), {}) == (44100, 48000)
    assert device_rates.card_rates(card(), {("USB", "input"): 96000.2}) == (96000, 48000)
    assert device_rates.card_rates(card(), {("USB", "output"): 88200}) == (44100, 88200)
    assert device_rates.card_rates(card("ASIO"), {("USB", "input"): 44100}) == (None, None)


def test_rate_messages():
    for rates, half in [((44100, 48000), "input"), ((48000, 44100), "output")]:
        assert card_rate_message(*rates, 48000) == (
            f"The {half} of your sound card runs at 44.1 kHz. Set it to 48 kHz in Audio MIDI Setup, then check again.")
    assert card_rate_message(48000, 48000, 48000) is None
    assert card_rate_message(None, None, 48000) is None
    assert card_rate_message(44100, 48000, None) is not None
    assert card_rate_message(44100, 44100, 48000).startswith("Your sound card runs at 44.1 kHz.")


@pytest.mark.parametrize("rates,label", [((48000, 48000), "48 kHz"),
    ((44100, 48000), "in 44.1 kHz · out 48 kHz"), ((None, None), ""), ((None, 48000), "")])
def test_rate_label(rates, label):
    assert card_rate_label(*rates) == label


def test_live_read_failures_are_empty(monkeypatch):
    monkeypatch.setattr(device_rates.sys, "platform", "darwin")
    def fail():
        raise OSError("CoreAudio unavailable")
    monkeypatch.setattr(device_rates, "_coreaudio_halves", fail)
    assert device_rates.live_half_rates() == device_rates.live_half_transports() == {}


def test_live_halves_share_walk(monkeypatch):
    monkeypatch.setattr(device_rates.sys, "platform", "darwin")
    monkeypatch.setattr(device_rates, "_coreaudio_halves", lambda: [("USB", "input", 44100, "usb "),
                                                                 ("USB", "output", 48000, "usb ")])
    assert device_rates.live_half_rates() == {("USB", "input"): 44100, ("USB", "output"): 48000}
    assert device_rates.live_half_transports() == {("USB", "input"): "usb ", ("USB", "output"): "usb "}


@pytest.mark.skipif(sys.platform != "darwin", reason="needs CoreAudio")
def test_coreaudio_smoke():
    for values in (device_rates.live_half_rates(), device_rates.live_half_transports()):
        assert isinstance(values, dict)
        assert all(isinstance(k[0], str) and k[1] in ("input", "output") for k in values)


def test_non_mac_reads_are_empty(monkeypatch):
    monkeypatch.setattr(device_rates.sys, "platform", "linux")
    assert device_rates.live_half_rates() == device_rates.live_half_transports() == {}
    assert device_rates._fourcc("usb ") == 0x75736220


def test_coreaudio_walk_checks_each_scope_and_decodes_transport(monkeypatch):
    import ctypes

    class FakeCoreAudio:
        def size(self, device, selector, scope="glob"):
            if selector == "dev#":
                return 2 * ctypes.sizeof(ctypes.c_uint32)
            assert selector == "stm#"
            return 4 if (device, scope) in {(2, "outp"), (3, "inpt")} else 0

        def read(self, device, selector, value, scope="glob"):
            if selector == "dev#":
                value[:] = [2, 3]
            elif selector == "nsrt":
                value.value = 48000 if device == 2 else 44100
            else:
                assert selector == "tran"
                value.value = device_rates._fourcc("usb ")

        def name(self, device):
            return "USB"

    monkeypatch.setattr(device_rates, "_CoreAudio", FakeCoreAudio)
    assert device_rates._coreaudio_halves() == [("USB", "output", 48000, "usb "),
                                               ("USB", "input", 44100, "usb ")]


@pytest.mark.parametrize("bad_selector", ["name", "nsrt", "tran", "stm#"])
def test_one_unreadable_device_does_not_hide_other_rates_or_bluetooth(monkeypatch, bad_selector):
    import ctypes
    class Core:
        def size(self, device, selector, scope="glob"):
            if selector == "dev#":
                return 3 * ctypes.sizeof(ctypes.c_uint32)
            if device == 1 and bad_selector == selector:
                raise OSError("unreadable device")
            return 4
        def read(self, device, selector, value, scope="glob"):
            if selector == "dev#":
                value[:] = [1, 2, 3]
            elif device == 1 and bad_selector == selector:
                raise OSError("unreadable device")
            else:
                value.value = 48000 if selector == "nsrt" else device_rates._fourcc("blue" if device == 3 else "usb ")
        def name(self, device):
            if device == 1 and bad_selector == "name":
                raise OSError("unreadable device")
            return {1: "Broken", 2: "USB", 3: "AirPods"}[device]
    monkeypatch.setattr(device_rates, "_CoreAudio", Core)
    monkeypatch.setattr(device_rates.sys, "platform", "darwin")
    rates = device_rates.live_half_rates()
    transports = device_rates.live_half_transports()
    assert rates[("USB", "input")] == rates[("AirPods", "output")] == 48000
    assert transports[("AirPods", "input")] == "blue"
    if bad_selector == "nsrt":
        assert ("Broken", "input") not in rates and transports[("Broken", "input")] == "usb "
    if bad_selector == "tran":
        assert rates[("Broken", "input")] == 48000 and ("Broken", "input") not in transports


def test_split_rates_block_without_project():
    message = card_rate_message(44100, 48000, None)
    assert message and "44.1 kHz" in message and "48 kHz" in message
