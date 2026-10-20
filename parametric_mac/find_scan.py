"""Scan a sound card's outputs one at a time for the capture route. No Qt.

The audio call is injected (`PlayRecord`), so the scan runs on synthetic rigs in tests and on the real
interface through `sounddevice_play_record`. Spec §6.1: one output at a time, at the Find level.
"""
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from nam.capture.audio import CaptureCancelled, _raise_on_dropout

from .find_route import (
    FULL_SCAN_OUTPUTS, FindResult, OutputScan, Route, analyse_input, choose_route, find_playback, summarise,
)

# (playback, sample_rate, output_channel) -> recording, shape (frames, input_channels)
PlayRecord = Callable[[np.ndarray, int, int], np.ndarray]
Progress = Callable[[float], None]
Cancel = Callable[[], bool]

# How often the stream is checked for a cancel, in milliseconds (upstream polls at the same rate).
POLL_MS = 50


@dataclass(frozen=True)
class ScanTarget:
    """Plain values read on the GUI thread, so the scan never touches Qt or CoreAudio."""
    device_index: int
    output_channels: int
    input_channels: int
    sample_rate: int
    blocksize: int
    latency: object
    excluded_inputs: frozenset[int]


def playback_frame(playback: np.ndarray, output_channels: int, output_channel: int) -> np.ndarray:
    """A full-width output buffer, silent except the 1-based `output_channel` column."""
    if not 1 <= output_channel <= output_channels:
        raise ValueError(f"Output {output_channel} is outside 1…{output_channels}.")
    frame = np.zeros((len(playback), output_channels), dtype=np.float32)
    frame[:, output_channel - 1] = playback
    return frame


def sounddevice_play_record(device_index: int, output_channels: int, input_channels: int, blocksize: int,
                            latency, cancel: Cancel | None = None) -> PlayRecord:  # pragma: no cover - needs a sound card
    """The same full-width `sd.playrec` call as upstream `SounddeviceRecorder.playrec`, keeping every input."""
    def play_record(playback: np.ndarray, sample_rate: int, output_channel: int) -> np.ndarray:
        import sounddevice as sd

        recording = sd.playrec(
            playback_frame(playback, output_channels, output_channel), samplerate=sample_rate,
            device=(device_index, device_index), channels=input_channels, dtype="float32",
            blocksize=blocksize, latency=latency, blocking=False,
        )
        try:
            stream = sd.get_stream()
            while stream.active:
                if cancel is not None and cancel():
                    raise CaptureCancelled()
                sd.sleep(POLL_MS)
            sd.wait()
        except BaseException:
            sd.stop()
            raise
        _raise_on_dropout(sd.get_status(), latency=latency, blocksize=blocksize)
        return np.asarray(recording, dtype=np.float32)

    return play_record


def _as_matrix(recording: np.ndarray, input_channels: int | None) -> np.ndarray:
    matrix = np.asarray(recording, dtype=np.float32)
    matrix = matrix.reshape(-1, 1) if matrix.ndim == 1 else matrix
    if matrix.ndim != 2 or (input_channels is not None and matrix.shape[1] != input_channels):
        raise ValueError(f"Expected a recording with {input_channels} inputs; got shape {matrix.shape}.")
    return matrix


def scan_outputs(play_record: PlayRecord, sample_rate: int, output_channels: int, excluded_inputs: frozenset[int],
                 progress: Progress | None = None, cancel: Cancel | None = None,
                 input_channels: int | None = None) -> FindResult:
    """Play the clicks on each output in turn and keep the route each one gives.

    Up to FULL_SCAN_OUTPUTS outputs are all tried, so a second cable shows as "several"; on bigger
    devices the scan stops at the first route.
    """
    playback, preamble = find_playback(sample_rate)
    routes: list[Route] = []
    loopbacks: list[int] = []
    stop_at_first = output_channels > FULL_SCAN_OUTPUTS
    stopped_early = False
    heard_anything = False
    for output_channel in range(1, output_channels + 1):
        if cancel is not None and cancel():
            raise CaptureCancelled()
        recording = _as_matrix(play_record(playback, sample_rate, output_channel), input_channels)
        scan = _scan_one(recording, output_channel, playback, preamble)
        loopbacks.extend(r.input_channel for r in scan.inputs if r.loopback)
        heard_anything = heard_anything or any(r.peak_dbfs is not None for r in scan.inputs)
        route = choose_route(scan, excluded_inputs)
        if route is not None:
            routes.append(route)
        if progress is not None:
            progress(output_channel / output_channels)
        if route is not None and stop_at_first and output_channel < output_channels:
            stopped_early = True
            break
    if stopped_early and progress is not None:
        progress(1.0)
    return summarise(routes, loopbacks, stopped_early, silent=not heard_anything)


def _scan_one(recording: np.ndarray, output_channel: int, playback: np.ndarray, preamble) -> OutputScan:
    inputs = tuple(analyse_input(recording[:, i], i + 1, playback, preamble) for i in range(recording.shape[1]))
    return OutputScan(output_channel, inputs)


def scan_target(target: ScanTarget, progress: Progress | None, cancel: Cancel | None) -> FindResult:
    """Scan the real interface `target` names; a device with no inputs or no outputs gives "none"."""
    if target.output_channels < 1 or target.input_channels < 1:
        return summarise([], [], False)
    play_record = sounddevice_play_record(
        target.device_index, target.output_channels, target.input_channels, target.blocksize, target.latency, cancel,
    )
    return scan_outputs(play_record, target.sample_rate, target.output_channels, target.excluded_inputs,
                        progress, cancel, target.input_channels)
