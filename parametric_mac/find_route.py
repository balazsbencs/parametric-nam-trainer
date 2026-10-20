"""Find the capture route: which input answers a quiet click on an output. No Qt, no audio I/O.

The clicks and their detection are upstream's own (`nam.capture.latency`), at a lower level: Find plays
on outputs the user did not choose, so it must stay quiet (spec §6.1).
"""
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from nam.capture.latency import BlipPreamble, PlayedPreamble, measure_delay
from nam.capture.session import TAIL_SECONDS

# −20 dBFS. Synthetic tests show detection still works at this level for returns down to about −60 dBFS
# over a −90 dBFS noise floor, and −50 dBFS over −80. The clicks must stand about 30 dB above the noise.
FIND_AMPLITUDE = 0.1
# A digital loopback returns a near bit-exact copy; a real path through converters and a pedal never does.
LOOPBACK_RESIDUAL_DB = -80.0
# At or above this peak a return is too close to clipping (the rule the route test already used).
CLIP_DBFS = -1.0
# Up to this many outputs Find tries them all, so a second cable (a timing loopback) cannot win silently.
FULL_SCAN_OUTPUTS = 8
# Upstream's fine detection reaches this far by itself (its look-back minus look-ahead, in samples).
COARSE_REACH = 9_000
# How far the clicks must stand out from the median before a coarse shift is trusted (upstream: 5).
COARSE_CONTRAST = 5.0
# Samples left before the clicks after a coarse shift, so the fine step still sees the onset.
COARSE_MARGIN = 500
# Samples searched on each side of the measured delay when testing for a loopback.
ALIGN_SEARCH = 2
# Samples on each side of each click that the loopback test compares. The clicks are single samples, so
# a narrow window keeps channel noise from hiding a copy: at −20 dBFS a 24-bit dithered copy or one with
# −120 dBFS noise stays under −80 dB; a 16-bit dithered copy (about −60 dB) does not.
LOOPBACK_WINDOW = 16
# Detection tries the return as recorded, then doubled: upstream's trigger is a fixed level, so a dark,
# quiet path can sit under it while its clicks stand well above the noise. Doubling found the same
# returns as −14 dBFS clicks would (final review probe), without playing louder. A fallback only: it runs
# when the first try fails, and every click must still arrive.
DETECTION_BOOSTS = (1.0, 2.0)
_SILENCE = 1e-9

FindState = Literal["found", "several", "none"]


@dataclass(frozen=True)
class InputReturn:
    input_channel: int
    detected: bool
    delay: int | None
    peak_dbfs: float | None
    loopback: bool


@dataclass(frozen=True)
class OutputScan:
    output_channel: int
    inputs: tuple[InputReturn, ...]


@dataclass(frozen=True)
class Route:
    output_channel: int
    input_channel: int
    peak_dbfs: float
    other_inputs: tuple[int, ...]

    @property
    def clipping(self) -> bool:
        return self.peak_dbfs >= CLIP_DBFS


@dataclass(frozen=True)
class FindResult:
    state: FindState
    routes: tuple[Route, ...]
    loopbacks: tuple[int, ...]
    stopped_early: bool = False
    # Every input read exact digital zeros on every output: on macOS, no microphone access.
    silent: bool = False

    @property
    def route(self) -> Route | None:
        return self.routes[0] if self.state == "found" else None


def find_playback(sample_rate: int, amplitude: float = FIND_AMPLITUDE) -> tuple[np.ndarray, PlayedPreamble]:
    """The click preamble and a short tail, laid out like upstream `build_playback`, at a lower level."""
    rendered = BlipPreamble(sample_rate, amplitude)
    tail = np.zeros(int(TAIL_SECONDS * sample_rate), dtype=np.float32)
    playback = np.concatenate([rendered.render(), tail]).astype(np.float32)
    return playback, PlayedPreamble.from_playback(playback, rendered.n_samples, sample_rate)


def _peak_dbfs(recording: np.ndarray) -> float | None:
    peak = float(np.max(np.abs(recording))) if len(recording) else 0.0
    return 20 * math.log10(peak) if peak > _SILENCE else None


def is_loopback(recording: np.ndarray, playback: np.ndarray, delay: int, clicks: Sequence[int]) -> bool:
    """True when the return, aligned and gain-matched, differs from the playback by ≤ LOOPBACK_RESIDUAL_DB.

    Only the samples around each click count (LOOPBACK_WINDOW). Upstream's delay estimate can sit a
    sample or two from the integer shift, so the best of the nearby shifts decides.
    """
    return any(_residual_db(recording, playback, shift, clicks) <= LOOPBACK_RESIDUAL_DB
               for shift in range(delay - ALIGN_SEARCH, delay + ALIGN_SEARCH + 1))


def _windows(signal: np.ndarray, starts: Sequence[int]) -> np.ndarray | None:
    span = 2 * LOOPBACK_WINDOW + 1
    if any(start < 0 or start + span > len(signal) for start in starts):
        return None
    return np.concatenate([signal[start:start + span] for start in starts]).astype(np.float64)


def _residual_db(recording: np.ndarray, playback: np.ndarray, delay: int, clicks: Sequence[int]) -> float:
    """Residual energy after gain matching, relative to the matched signal, in dB (+inf when undefined)."""
    sent = _windows(playback, [c - LOOPBACK_WINDOW for c in clicks])
    got = _windows(recording, [c + delay - LOOPBACK_WINDOW for c in clicks])
    if sent is None or got is None:
        return math.inf
    energy = float(sent @ sent)
    if energy <= 0:
        return math.inf
    gain = float(sent @ got) / energy
    signal = (gain ** 2) * energy
    if signal <= 0:
        return math.inf
    residual = float(np.sum((got - gain * sent) ** 2))
    return -math.inf if residual <= 0 else 10 * math.log10(residual / signal)


def analyse_input(recording: np.ndarray, input_channel: int, playback: np.ndarray,
                  preamble: PlayedPreamble) -> InputReturn:
    """Whether this input heard the clicks, with the delay, the peak and the loopback test."""
    recording = np.asarray(recording, dtype=np.float32).squeeze()
    peak = _peak_dbfs(recording)
    if peak is None:
        return InputReturn(input_channel, False, None, None, False)
    # Upstream compares |x| with the background, so a DC offset hides an inverted click; the peak above
    # stays the raw one, because clipping happens on the raw signal.
    centred = recording - np.float32(np.median(recording))
    for boost in DETECTION_BOOSTS:
        found = _detect(centred * np.float32(boost), preamble)
        if found is not None:
            delay, arrival = found
            loopback = is_loopback(centred, playback, arrival, preamble.blip_locations)
            return InputReturn(input_channel, True, delay, peak, loopback)
    return InputReturn(input_channel, False, None, peak, False)


def _detect(centred: np.ndarray, preamble: PlayedPreamble) -> tuple[int, int] | None:
    """(delay, arrival) when every click arrived and the clicks agree, else None."""
    shift = coarse_shift(centred, preamble)
    shifted = np.concatenate([centred[shift:], np.zeros(shift, dtype=np.float32)]) if shift else centred
    try:
        result = measure_delay(shifted, preamble)
    except ValueError:  # too short or unreadable: treat as no answer
        return None
    # Upstream accepts one click alone (nothing to disagree with); a single pop must not become a route.
    every_click = len(result.blip_delays) == len(preamble.blip_locations)
    if not result.ok or result.delay is None or not every_click:
        return None
    delay = int(result.delay) + shift
    # Upstream reports the averaged arrival minus a safety factor; the loopback test needs the arrival.
    return delay, delay + int(result.safety_factor)


def coarse_shift(recording: np.ndarray, preamble: PlayedPreamble) -> int:
    """A long round-trip delay to remove before upstream's fine detection, or 0.

    Same search as upstream's `_coarse_bulk_delay`, but with only its relative test (the clicks must
    stand out from the median). Upstream also needs each click above about −34 dBFS, which a quiet
    return through a reamp pad does not reach; its fine detection then sees an unscaled signal.
    """
    locs = preamble.blip_locations
    max_shift = min(preamble.blip_section_samples - locs[-1], len(recording) - locs[-1])
    if max_shift <= COARSE_REACH:
        return 0
    envelope = np.abs(recording)
    score = sum(envelope[loc:loc + max_shift] for loc in locs).astype(np.float64)
    best = int(np.argmax(score))
    if best <= COARSE_REACH or score[best] < COARSE_CONTRAST * (float(np.median(score)) + 1e-12):
        return 0
    return best - COARSE_MARGIN


def choose_route(scan: OutputScan, excluded_inputs: frozenset[int]) -> Route | None:
    """The loudest input that heard this output and is neither a loopback nor excluded."""
    usable = [r for r in scan.inputs
              if r.detected and not r.loopback and r.input_channel not in excluded_inputs and r.peak_dbfs is not None]
    if not usable:
        return None
    usable.sort(key=lambda r: r.peak_dbfs, reverse=True)
    best = usable[0]
    return Route(scan.output_channel, best.input_channel, best.peak_dbfs, tuple(r.input_channel for r in usable[1:]))


def summarise(routes: Sequence[Route], loopbacks: Sequence[int], stopped_early: bool,
              silent: bool = False) -> FindResult:
    state: FindState = "none" if not routes else "found" if len(routes) == 1 else "several"
    return FindResult(state, tuple(routes), tuple(sorted(set(loopbacks))), stopped_early, silent and not routes)
