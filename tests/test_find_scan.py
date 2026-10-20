import numpy as np
import pytest
from nam.capture.audio import AudioDropoutError, CaptureCancelled

from parametric_mac import find_scan
from parametric_mac.find_scan import ScanTarget, playback_frame, scan_outputs, scan_target

RATE = 48000
LOOPBACK_INPUT = 3


def _return(playback, delay, gain, noise_db, seed):
    """A path through converters and a pedal: delayed, scaled, low-passed near 8 kHz, plus noise."""
    out = np.zeros(len(playback))
    out[delay:] = playback[: len(playback) - delay] * gain
    a = 1 - np.exp(-2 * np.pi * 8000 / RATE)
    out = np.convolve(out, a * (1 - a) ** np.arange(64))[: len(out)]
    return out + np.random.default_rng(seed).normal(0, 10 ** (noise_db / 20), len(out))


class FakeRig:
    """A play-record stand-in: `route` is the reamp cable, input 3 a digital loopback of every output."""

    def __init__(self, outputs, inputs, route=(2, 1), extra_route=None, dropout_on=None):
        self.outputs, self.inputs = outputs, inputs
        self.route, self.extra_route, self.dropout_on = route, extra_route, dropout_on
        self.played = []

    def __call__(self, playback, sample_rate, output_channel):
        assert sample_rate == RATE and 1 <= output_channel <= self.outputs
        self.played.append(output_channel)
        if output_channel == self.dropout_on:
            raise AudioDropoutError("The audio stream could not keep up.")
        columns = [self._input(playback, output_channel, i) for i in range(1, self.inputs + 1)]
        return np.stack(columns, axis=1).astype(np.float32)

    def _input(self, playback, output_channel, input_channel):
        seed = output_channel * 100 + input_channel
        if (output_channel, input_channel) == self.route:
            return _return(playback, 300, 0.4, -75, seed)
        if (output_channel, input_channel) == self.extra_route:
            return _return(playback, 450, 0.15, -75, seed)
        if input_channel == LOOPBACK_INPUT:
            copy = np.zeros(len(playback))
            copy[32:] = playback[:-32]
            return copy
        return np.random.default_rng(seed).normal(0, 10 ** (-75 / 20), len(playback))


def test_scan_finds_the_rig_route_and_ignores_the_digital_loopback():
    result = scan_outputs(FakeRig(outputs=4, inputs=4), RATE, 4, frozenset())
    assert (result.state, result.route.output_channel, result.route.input_channel) == ("found", 2, 1)
    assert LOOPBACK_INPUT in result.loopbacks


def test_playback_frame_uses_exactly_one_output():
    frame = playback_frame(np.ones(10, np.float32), 6, 4)
    assert frame.shape == (10, 6) and np.flatnonzero(np.abs(frame).max(axis=0)).tolist() == [3]
    with pytest.raises(ValueError):
        playback_frame(np.ones(10, np.float32), 6, 7)
    with pytest.raises(ValueError):
        playback_frame(np.ones(10, np.float32), 6, 0)


def test_scan_plays_each_output_once_in_order():
    rig = FakeRig(outputs=4, inputs=4)
    scan_outputs(rig, RATE, 4, frozenset())
    assert rig.played == [1, 2, 3, 4]


def test_a_timing_cable_on_another_output_gives_several_routes():
    rig = FakeRig(outputs=4, inputs=4, extra_route=(3, 4))  # output 3 → input 4: an analog timing cable
    result = scan_outputs(rig, RATE, 4, frozenset())
    assert result.state == "several" and result.route is None
    assert {(r.output_channel, r.input_channel) for r in result.routes} == {(2, 1), (3, 4)}


def test_two_inputs_on_the_same_output_are_one_route():
    rig = FakeRig(outputs=4, inputs=4, extra_route=(2, 4))  # output 2 also reaches input 4, more quietly
    result = scan_outputs(rig, RATE, 4, frozenset())
    assert result.state == "found" and result.route.input_channel == 1 and result.route.other_inputs == (4,)


def test_excluded_inputs_are_never_chosen():
    result = scan_outputs(FakeRig(outputs=4, inputs=4), RATE, 4, frozenset({1}))
    assert result.state == "none"


def test_large_devices_stop_at_the_first_route():
    rig = FakeRig(outputs=12, inputs=4)
    result = scan_outputs(rig, RATE, 12, frozenset())
    assert result.state == "found" and result.stopped_early and rig.played == [1, 2]


def test_scan_reports_none_when_nothing_returns():
    assert scan_outputs(FakeRig(outputs=1, inputs=1, route=None), RATE, 1, frozenset()).state == "none"


def test_cancel_stops_the_scan():
    rig = FakeRig(outputs=4, inputs=4)
    with pytest.raises(CaptureCancelled):
        scan_outputs(rig, RATE, 4, frozenset(), cancel=lambda: True)
    assert rig.played == []


def test_progress_rises_to_one():
    seen = []
    scan_outputs(FakeRig(outputs=4, inputs=4, route=None), RATE, 4, frozenset(), progress=seen.append)
    assert seen == sorted(seen) and seen[-1] == 1.0


def test_progress_reaches_one_when_the_scan_stops_early():
    seen = []
    scan_outputs(FakeRig(outputs=12, inputs=4), RATE, 12, frozenset(), progress=seen.append)
    assert seen == sorted(seen) and seen[-1] == 1.0


def test_dropout_reaches_the_caller():
    with pytest.raises(AudioDropoutError):
        scan_outputs(FakeRig(outputs=2, inputs=2, dropout_on=1), RATE, 2, frozenset())


def test_a_recording_of_the_wrong_width_is_refused():
    def narrow(playback, sample_rate, output_channel):
        return np.zeros((len(playback), 1), np.float32)
    with pytest.raises(ValueError):
        scan_outputs(narrow, RATE, 2, frozenset(), input_channels=4)


def test_cancel_between_outputs_stops_before_the_next_one():
    rig = FakeRig(outputs=4, inputs=4)
    with pytest.raises(CaptureCancelled):
        scan_outputs(rig, RATE, 4, frozenset(), cancel=lambda: bool(rig.played))
    assert rig.played == [1]


def _fake_factory(monkeypatch, rig):
    calls = []

    def factory(*args):
        calls.append(args)
        return rig
    monkeypatch.setattr(find_scan, "sounddevice_play_record", factory)
    return calls


def test_scan_target_passes_the_device_values_in_order(monkeypatch):
    calls = _fake_factory(monkeypatch, FakeRig(outputs=6, inputs=2, route=(2, 1)))
    cancel = lambda: False  # noqa: E731
    result = scan_target(ScanTarget(7, 6, 2, RATE, 256, "low", frozenset()), None, cancel)
    assert calls == [(7, 6, 2, 256, "low", cancel)]
    assert (result.state, result.route.output_channel, result.route.input_channel) == ("found", 2, 1)


@pytest.mark.parametrize("outputs, inputs", [(0, 2), (2, 0)])
def test_device_without_inputs_or_outputs_is_none(monkeypatch, outputs, inputs):
    calls = _fake_factory(monkeypatch, FakeRig(outputs=2, inputs=2))
    target = ScanTarget(0, outputs, inputs, RATE, 0, "low", frozenset())
    assert scan_target(target, None, None).state == "none" and calls == []


def test_total_silence_on_every_input_is_reported_as_silent():
    # macOS gives exact digital zeros when the app has no microphone access.
    def silent(playback, sample_rate, output_channel):
        return np.zeros((len(playback), 2), np.float32)
    result = scan_outputs(silent, RATE, 2, frozenset())
    assert result.state == "none" and result.silent
    assert not scan_outputs(FakeRig(outputs=2, inputs=2, route=None), RATE, 2, frozenset()).silent
