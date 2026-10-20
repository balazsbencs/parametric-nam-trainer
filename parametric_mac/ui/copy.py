"""Plain-language messages for the main path. No Qt."""
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ..find_route import CLIP_DBFS as ROUTE_CLIP_DBFS  # one clip rule; the UI imports the core

CLIP_TEXT = "The signal is too close to clipping. Turn the reamp box or the sound card input down a little, then check again."
LOCKED_CLIP_TEXT = ("The signal is too close to clipping. This project already has recordings, so keep the reamp box "
                    "and sound card gain fixed. Start a new capture to set a lower level.")


def _khz(rate: int) -> str:
    return f"{rate / 1000:.1f}".rstrip("0").rstrip(".") + " kHz"


def sample_rate_message(device_rate: int | None, file_rate: int | None) -> str | None:
    """A blocking message when the sound card runs at another rate than the capture signals."""
    if device_rate is None or file_rate is None or device_rate == file_rate:
        return None
    return (f"Your sound card runs at {_khz(device_rate)}. Set it to {_khz(file_rate)} in Audio MIDI Setup, "
            "then check again.")


def level_message(peak_dbfs: float, clip_threshold: float = ROUTE_CLIP_DBFS, *, locked: bool = False) -> tuple[Literal["ok", "clip"], str]:
    if peak_dbfs >= clip_threshold:
        return "clip", LOCKED_CLIP_TEXT if locked else CLIP_TEXT
    return "ok", f"Peak {peak_dbfs:.1f} dB · good. Do not touch the sound card gain from now on.".replace("-", "−", 1)


CONNECT_HELP = "\n".join((
    "No sound card in the list: plug it in, wait a moment, then press refresh.",
    "Wrong sample rate: open Audio MIDI Setup, select your sound card and set it to 48 kHz.",
    "No signal comes back: check every cable, the reamp box and the power supply of your gear. "
    "Check that the output and input channels match the jacks you use.",
    "Clipping: before the first take, lower the reamp box output or sound card input gain, then check again. "
    "After recording starts, keep these levels fixed and start a new capture to set a lower level.",
))


# Spec §4.3, verbatim. Levels stay fixed for the whole project, so no message may suggest changing them.
CLIPPED_BODY = ("This take clipped. Record it again. If it clips again, the level is too high for this pedal. "
                "Start a new capture and set a lower level on Connect.")


@dataclass(frozen=True)
class TakeMessage:
    kind: Literal["ok", "clipped", "warning"]
    title: str
    body: str


def take_message(clipping: bool | None, messages: Sequence[str]) -> TakeMessage:
    """What the Record page says about the take that was just saved."""
    if clipping:
        return TakeMessage("clipped", "Too loud — the take clipped", CLIPPED_BODY)
    if messages:
        details = " ".join(m.rstrip(".") + "." for m in messages)
        return TakeMessage("warning", "Check this take", f"{details} Record it again if the problem stays.")
    return TakeMessage("ok", "Good take", "No clipping, and the timing matched.")


@dataclass(frozen=True)
class EpochPoint:
    tier: str
    epoch: int
    value: float


_EPOCH_FINISHED = re.compile(r"Epoch (\d+) finished\. (?:(\w+): )?(.*)")
_METRIC = re.compile(r"(ESR|val_loss)=([-+0-9.eE]+)")


def parse_epoch_finished(line: str) -> EpochPoint | None:
    """The validation value from a trainer line "Epoch N finished. [tier: ]ESR=…, MSE=…" (ESR, else val_loss)."""
    match = _EPOCH_FINISHED.search(line)
    if not match:
        return None
    metrics = dict(_METRIC.findall(match.group(3)))
    value = metrics.get("ESR", metrics.get("val_loss"))
    if value is None:
        return None
    try:
        return EpochPoint(match.group(2) or "", int(match.group(1)), float(value))
    except ValueError:
        return None


def check_errors(log: str) -> tuple[str, ...]:
    """The problems the recording check printed ("ERROR: …" lines, and "Error: …" when the command itself failed)."""
    prefixes = ("ERROR: ", "Error: ")
    return tuple(line[len(prefix):].strip() for line in log.splitlines()
                 for prefix in prefixes if line.startswith(prefix))


def minutes_left(epoch_seconds: Sequence[float], epochs_left: int) -> int | None:
    """Whole minutes left from measured round times (median), or None before two rounds finished."""
    if len(epoch_seconds) < 2:
        return None
    ordered = sorted(epoch_seconds)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return math.ceil(median * max(0, epochs_left) / 60)


CHECKPOINT_NOTE = "These settings also chose the best training round, so the match can look better than on new settings."


def metric_lines(metrics: Mapping) -> tuple[str, ...]:
    """The last logged validation ESR of a run, with the honest note that it is not a fresh evaluation."""
    tiers = metrics.get("tiers")
    if isinstance(tiers, dict):
        lines = []
        for tier, values in tiers.items():
            value = values.get("ESR") if isinstance(values, dict) else None
            lines.append(f"{tier.capitalize()}: last validation ESR {value:.6g} · epoch {values.get('epoch')}"
                         if isinstance(value, (int, float)) else f"{tier.capitalize()}: no validation ESR recorded")
        return (*lines, "Last epochs, not separate evaluations of the exported checkpoints. Listen to both sizes.")
    esr = metrics.get("ESR")
    if isinstance(esr, (int, float)):
        return (f"Last logged validation ESR: {esr:.6g} · epoch {metrics.get('epoch')}",
                "This is the last epoch, not a separate evaluation of the exported checkpoint. Lower is better; listen too.")
    return ("No validation metric recorded for this run. Inspect training.log for details.",)
