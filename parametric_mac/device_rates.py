"""Live rates and transport types for each direction of a macOS sound card."""
import ctypes
import ctypes.util
import logging
import sys
from collections.abc import Mapping
from typing import Literal

from nam.capture.audio import reports_current_sample_rate
from .capture_cards import CaptureCard

Direction = Literal["input", "output"]
Half = tuple[str, Direction]
HalfReading = tuple[str, Direction, float | None, str | None]
log = logging.getLogger(__name__)


def card_rates(card: CaptureCard, live: Mapping[Half, float]) -> tuple[int | None, int | None]:
    if not reports_current_sample_rate(card):
        return None, None
    return (round(live.get((card.name, "input"), card.input_default_rate)),
            round(live.get((card.name, "output"), card.output_default_rate)))


def _live_halves() -> list[HalfReading]:
    if sys.platform != "darwin":
        return []
    try:
        return _coreaudio_halves()
    except Exception:
        log.debug("Could not read CoreAudio device halves", exc_info=True)
        return []


def live_device_state() -> tuple[dict[Half, float], dict[Half, str]]:
    """Read rates and transports in one walk; a failed property need not lose the other."""
    halves = _live_halves()
    rates = {(name, direction): rate for name, direction, rate, _ in halves if rate is not None}
    transports = {(name, direction): transport for name, direction, _, transport in halves if transport is not None}
    return rates, transports


def live_half_rates() -> dict[Half, float]:
    return live_device_state()[0]


def live_half_transports() -> dict[Half, str]:
    return live_device_state()[1]


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode("ascii"), "big")


class _Address(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32), ("element", ctypes.c_uint32)]


class _CoreAudio:  # pragma: no cover - needs CoreAudio
    def __init__(self) -> None:
        self.audio = ctypes.CDLL(ctypes.util.find_library("CoreAudio"))
        self.foundation = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
        self.foundation.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        self.foundation.CFStringGetCString.restype = ctypes.c_bool
        self.foundation.CFRelease.argtypes = [ctypes.c_void_p]

    def size(self, device: int, selector: str, scope: str = "glob") -> int:
        address = _Address(_fourcc(selector), _fourcc(scope), 0)
        size = ctypes.c_uint32()
        status = self.audio.AudioObjectGetPropertyDataSize(device, ctypes.byref(address), 0, None, ctypes.byref(size))
        if status:
            raise OSError(f"CoreAudio {selector} size failed: {status}")
        return size.value

    def read(self, device: int, selector: str, value, scope: str = "glob") -> None:
        address = _Address(_fourcc(selector), _fourcc(scope), 0)
        size = ctypes.c_uint32(ctypes.sizeof(value))
        status = self.audio.AudioObjectGetPropertyData(device, ctypes.byref(address), 0, None,
                                                      ctypes.byref(size), ctypes.byref(value))
        if status:
            raise OSError(f"CoreAudio {selector} read failed: {status}")

    def name(self, device: int) -> str:
        value = ctypes.c_void_p()
        self.read(device, "lnam", value)
        if not value.value:
            raise OSError("CoreAudio returned an empty device name")
        try:
            buffer = ctypes.create_string_buffer(4096)
            if not self.foundation.CFStringGetCString(value, buffer, len(buffer), 0x08000100):
                raise OSError("Could not decode CoreAudio device name")
            return buffer.value.decode("utf-8")
        finally:
            self.foundation.CFRelease(value)


def _property(core: _CoreAudio, device: int, selector: str, value):
    try:
        core.read(device, selector, value)
        return value.value
    except Exception:
        log.debug("Could not read CoreAudio %s for device %s", selector, device, exc_info=True)
        return None


def _device_halves(core: _CoreAudio, device: int) -> list[HalfReading]:
    name = core.name(device)
    rate = _property(core, device, "nsrt", ctypes.c_double())
    transport = _property(core, device, "tran", ctypes.c_uint32())
    fourcc = transport.to_bytes(4, "big").decode("ascii") if transport is not None else None
    halves = []
    for direction, scope in (("input", "inpt"), ("output", "outp")):
        try:
            if core.size(device, "stm#", scope) > 0:
                halves.append((name, direction, rate, fourcc))
        except Exception:
            log.debug("Could not read CoreAudio %s streams for device %s", direction, device, exc_info=True)
    return halves


def _coreaudio_halves() -> list[HalfReading]:
    core = _CoreAudio()
    devices = (ctypes.c_uint32 * (core.size(1, "dev#") // ctypes.sizeof(ctypes.c_uint32)))()
    core.read(1, "dev#", devices)
    halves = []
    for device in devices:
        try:
            halves.extend(_device_halves(core, device))
        except Exception:
            log.debug("Could not read CoreAudio device %s", device, exc_info=True)
    return halves
