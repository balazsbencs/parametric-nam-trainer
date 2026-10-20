import numpy as np
import pytest
from nam.capture.latency import DEFAULT_BLIP_AMPLITUDE

from parametric_mac.find_route import (
    CLIP_DBFS, COARSE_REACH, FIND_AMPLITUDE, InputReturn, OutputScan, Route, analyse_input, choose_route,
    coarse_shift, find_playback, summarise,
)

RATE = 48000
PLAY, PRE = find_playback(RATE)


def simulate(playback, delay, gain, lowpass=False, noise_db=None, seed=1, fraction=0.0, cutoff=8000):
    """What an input records: the playback delayed (optionally by a fraction more), scaled, filtered, plus noise."""
    out = np.zeros(len(playback), dtype=np.float64)
    source = playback.astype(np.float64)
    if fraction:  # linear interpolation for a sub-sample delay
        source = (1 - fraction) * source + fraction * np.concatenate([[0.0], source[:-1]])
    out[delay:] = source[: len(playback) - delay] * gain
    if lowpass:  # a one-pole low-pass (8 kHz unless set), like the converters plus a pedal
        a = 1 - np.exp(-2 * np.pi * cutoff / RATE)
        out = np.convolve(out, a * (1 - a) ** np.arange(1024))[: len(out)]
    if noise_db is not None:
        out = out + np.random.default_rng(seed).normal(0, 10 ** (noise_db / 20), len(out))
    return out.astype(np.float32)


def ret(channel, detected=True, peak=-20.0, loopback=False):
    return InputReturn(channel, detected, 300 if detected else None, peak if detected else None, loopback)


def test_find_level_is_minus_20_dbfs_and_below_the_route_test():
    assert FIND_AMPLITUDE == pytest.approx(0.1)
    assert FIND_AMPLITUDE < DEFAULT_BLIP_AMPLITUDE
    assert np.max(np.abs(PLAY)) <= FIND_AMPLITUDE + 1e-6


# A reamp pad and low levels: -20 dBFS can come back near -60 dBFS. Big buffers give long round trips:
# 9,500 and 10,500 sit each side of COARSE_REACH, 20,000 is far into the coarse search (reach: 36,000).
@pytest.mark.parametrize("delay", [300, 3000, 9500, 10500, 12000, 20000])
@pytest.mark.parametrize("gain", [0.5, 0.03, 0.01])
def test_detection_works_at_the_find_level(delay, gain):
    r = analyse_input(simulate(PLAY, delay, gain, True, -90), 1, PLAY, PRE)
    assert r.detected and abs(r.delay - delay) <= 3 and not r.loopback, r


# A noisier rig (-80 dBFS floor): a -50 dBFS return must still be found, and the coarse search must not
# jump to a noise peak and cut away a short-delay click.
@pytest.mark.parametrize("delay", [300, 3000, 12000])
@pytest.mark.parametrize("seed", range(5))
def test_detection_holds_against_a_noisier_floor(delay, seed):
    rec = simulate(PLAY, delay, 0.03, True, -80, seed=seed)
    r = analyse_input(rec, 1, PLAY, PRE)
    assert r.detected and abs(r.delay - delay) <= 3, r
    if delay < COARSE_REACH:
        assert coarse_shift(rec, PRE) == 0


@pytest.mark.parametrize("delay", [1, 120, 3000, 12000])
def test_exact_copy_is_a_loopback(delay):
    assert analyse_input(simulate(PLAY, delay, 0.98), 3, PLAY, PRE).loopback


def test_clean_boost_near_unity_is_not_a_loopback():
    assert not analyse_input(simulate(PLAY, 300, 1.0, True, -90), 1, PLAY, PRE).loopback


def test_near_perfect_analog_path_is_not_a_loopback():
    # no low-pass, a 0.4-sample fractional delay and a -110 dBFS noise floor: the hardest real case
    assert not analyse_input(simulate(PLAY, 300, 1.0, False, -110, fraction=0.4), 1, PLAY, PRE).loopback


@pytest.mark.parametrize("noise_db", [-90, -60])
def test_noise_only_is_not_detected(noise_db):
    # Scaling a return for detection must not turn noise into an answer.
    r = analyse_input(simulate(np.zeros_like(PLAY), 0, 0.0, False, noise_db), 2, PLAY, PRE)
    assert not r.detected, r


def test_silence_is_not_detected():
    r = analyse_input(np.zeros_like(PLAY), 2, PLAY, PRE)
    assert not r.detected and r.peak_dbfs is None and not r.loopback


def test_choose_route_picks_the_loudest_usable_input():
    scan = OutputScan(2, (ret(1, peak=-20), ret(2, peak=-12), ret(3, peak=-6, loopback=True), ret(4, peak=-3)))
    route = choose_route(scan, frozenset({4}))
    assert (route.output_channel, route.input_channel, route.other_inputs) == (2, 2, (1,))


def test_choose_route_returns_none_when_nothing_usable():
    scan = OutputScan(1, (ret(1, detected=False), ret(2, loopback=True)))
    assert choose_route(scan, frozenset()) is None


def test_a_loud_return_is_found_and_flagged_as_clipping():
    route = choose_route(OutputScan(1, (ret(1, peak=-0.5),)), frozenset())
    assert route.clipping and CLIP_DBFS == -1.0
    assert not choose_route(OutputScan(1, (ret(1, peak=-9.0),)), frozenset()).clipping


def test_summarise_states():
    a, b = Route(2, 1, -20.0, ()), Route(3, 4, -18.0, ())
    none = summarise([], [3], False)
    assert (none.state, none.route, none.loopbacks) == ("none", None, (3,))
    found = summarise([a], [], False)
    assert (found.state, found.route) == ("found", a)
    several = summarise([a, b], [], True)
    assert (several.state, several.route, several.stopped_early) == ("several", None, True)


def test_copy_uses_the_same_clip_rule():
    from parametric_mac.ui.copy import ROUTE_CLIP_DBFS
    assert ROUTE_CLIP_DBFS == CLIP_DBFS


# ---- final review: messier real-world signals -------------------------------------------------

def test_dc_offset_with_an_inverting_pedal_is_detected():
    # Cheap interfaces carry DC, and many pedals invert polarity.
    for dc in (0.001, 0.003):
        r = analyse_input(simulate(PLAY, 300, -0.03, True, -90) + np.float32(dc), 1, PLAY, PRE)
        assert r.detected and abs(r.delay - 300) <= 3, (dc, r)


@pytest.mark.parametrize("at", [26000, 77000, 92000])
def test_a_single_pop_is_not_a_return(at):
    rec = simulate(np.zeros_like(PLAY), 0, 0.0, False, -90)
    rec[at] += 0.05
    assert not analyse_input(rec, 2, PLAY, PRE).detected


def test_a_pop_on_another_input_does_not_win_the_route():
    real = analyse_input(simulate(PLAY, 300, 0.3, True, -90), 1, PLAY, PRE)
    noisy = simulate(np.zeros_like(PLAY), 0, 0.0, False, -90, seed=2)
    noisy[26000] += 0.05
    route = choose_route(OutputScan(1, (real, analyse_input(noisy, 2, PLAY, PRE))), frozenset())
    assert (route.input_channel, route.other_inputs) == (1, ()), route


def _copy(delay=64):
    return simulate(PLAY, delay, 1.0).astype(np.float64)


def test_a_24_bit_dithered_copy_is_a_loopback():
    tpdf = np.random.default_rng(5).triangular(-1, 0, 1, len(PLAY))
    rec = (np.round(_copy() * 2 ** 23 + tpdf) / 2 ** 23).astype(np.float32)
    assert analyse_input(rec, 3, PLAY, PRE).loopback


def test_a_copy_with_minus_120_dbfs_noise_is_a_loopback():
    rec = (_copy() + np.random.default_rng(6).normal(0, 1e-6, len(PLAY))).astype(np.float32)
    assert analyse_input(rec, 3, PLAY, PRE).loopback


def test_a_tiny_fractional_analog_delay_is_not_a_loopback():
    rec = simulate(PLAY, 300, 1.0, False, -120, fraction=0.05)
    r = analyse_input(rec, 1, PLAY, PRE)
    assert r.detected and not r.loopback, r


# A darker pedal at a low level: the clicks are spread out and fall under upstream's fixed trigger, although
# they stand well above the noise. The final review measured these two cells.
@pytest.mark.parametrize("cutoff, gain", [(3000, 0.01), (800, 0.03)])
@pytest.mark.parametrize("seed", range(5))
def test_dark_quiet_paths_are_found_at_the_find_level(cutoff, gain, seed):
    r = analyse_input(simulate(PLAY, 300, gain, True, -90, seed=seed, cutoff=cutoff), 1, PLAY, PRE)
    assert r.detected and abs(r.delay - 300) <= 3, r


# The doubled second try must not turn noise or mains hum into a return. The two clicks are 48,000 samples
# apart: a whole number of 50 Hz and 60 Hz periods, so hum lines up in both windows.
@pytest.mark.parametrize("noise_db", [-70, -60])
@pytest.mark.parametrize("seed", range(20))
def test_noise_sweep_is_never_a_return(noise_db, seed):
    rec = simulate(np.zeros_like(PLAY), 0, 0.0, False, noise_db, seed=seed)
    assert not analyse_input(rec, 2, PLAY, PRE).detected


@pytest.mark.parametrize("hz", [50, 60])
@pytest.mark.parametrize("amplitude", [0.003, 0.1])
def test_mains_hum_is_never_a_return(hz, amplitude):
    t = np.arange(len(PLAY)) / RATE
    hum = amplitude * np.sin(2 * np.pi * hz * t + 0.7) + np.random.default_rng(hz).normal(0, 1e-4, len(PLAY))
    assert not analyse_input(hum.astype(np.float32), 2, PLAY, PRE).detected
