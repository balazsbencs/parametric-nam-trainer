"""Plain-language messages for the main path. No Qt."""
from typing import Literal

# A route test at or above this peak is too close to clipping (the rule the app already used).
ROUTE_CLIP_DBFS = -1.0

CLIP_TEXT = "The signal is too close to clipping. Turn the reamp box or the sound card input down a little, then check again."


def _khz(rate: int) -> str:
    return f"{rate / 1000:.1f}".rstrip("0").rstrip(".") + " kHz"


def sample_rate_message(device_rate: int | None, file_rate: int | None) -> str | None:
    """A blocking message when the sound card runs at another rate than the capture signals."""
    if device_rate is None or file_rate is None or device_rate == file_rate:
        return None
    return (f"Your sound card runs at {_khz(device_rate)}. Set it to {_khz(file_rate)} in Audio MIDI Setup, "
            "then check again.")


def level_message(peak_dbfs: float, clip_threshold: float = ROUTE_CLIP_DBFS) -> tuple[Literal["ok", "clip"], str]:
    if peak_dbfs >= clip_threshold:
        return "clip", CLIP_TEXT
    return "ok", f"Peak {peak_dbfs:.1f} dB · good. Do not touch the sound card gain from now on.".replace("-", "−", 1)


CONNECT_HELP = "\n".join((
    "No sound card in the list: plug it in, wait a moment, then press refresh.",
    "Wrong sample rate: open Audio MIDI Setup, select your sound card and set it to 48 kHz.",
    "No signal comes back: check every cable, the reamp box and the power supply of your gear. "
    "Check that the output and input channels match the jacks you use.",
    "Clipping: turn the reamp box output or the sound card input gain down a little, then check again.",
))
