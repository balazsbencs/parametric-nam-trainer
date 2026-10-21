"""Plain-language messages for the main path. No Qt."""
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ..find_route import CLIP_DBFS as ROUTE_CLIP_DBFS  # one clip rule; the UI imports the core
from ..find_route import FindResult, Route

CLIP_TEXT = "The signal is too close to clipping. Turn the reamp box or the sound card input down a little, then check again."
LOCKED_CLIP_TEXT = ("The signal is too close to clipping. This project already has recordings, so keep the reamp box "
                    "and sound card gain fixed. Start a new capture to set a lower level.")

# Find my connection, spec §4.2 and §6.1, verbatim.
FIND_NONE_TEXT = "No signal came back. Check the cables, and check that the reamp box and the pedal have power."
FIND_FAILED_TEXT = "The sound card stopped during the search. Check that nothing else uses it, then try again."
FIND_CANCELLED_TEXT = "Search cancelled."
FIND_SILENT_TEXT = ("Every input recorded total silence. Allow microphone access for the app that opened Parametric "
                    "(usually Terminal or Python) in System Settings › Privacy & Security › Microphone, then try again.")
# Find stays at −20 dBFS, so a very quiet or dark path can miss it (final review, I2).
FIND_QUIET_HINT = "If your gear is quiet or dark, turn its volume or the sound card input gain up a little, then try again."


def _and_list(numbers: Sequence[int]) -> str:
    words = [str(n) for n in numbers]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def several_routes_text() -> str:
    return "More than one connection answered. Choose the one that goes through the reamp box and your gear."


def route_choice_text(route: Route) -> str:
    return f"Use Output {route.output_channel} → Input {route.input_channel}"


def find_message(result: FindResult, outputs: int | None = None, levels_locked: bool = False) -> str:
    """What Find says about its result: the route, the other inputs that heard it, clipping, and an early stop."""
    route = result.route
    if result.silent:
        return FIND_SILENT_TEXT
    if route is None:
        if result.state == "several":
            return several_routes_text()
        # Spec §4.3: once recording has started the levels stay fixed, so no hint to turn anything up.
        return FIND_NONE_TEXT if levels_locked else FIND_NONE_TEXT + "\n" + FIND_QUIET_HINT
    lines = [f"Found: Output {route.output_channel} → Input {route.input_channel}."]
    if result.stopped_early and outputs:
        # Outputs after this one were not tried, so a timing cable on an earlier output could be the answer.
        lines.append(f"{stopped_early_note(outputs)} Check that Output {route.output_channel} goes to the reamp box.")
    if route.other_inputs:
        heard = sorted((route.input_channel, *route.other_inputs))
        lines.append(f"Found on inputs {_and_list(heard)}. Using input {route.input_channel} (louder).")
    if route.clipping:
        lines.append(CLIP_TEXT)
    return "\n".join(lines)


def loopback_note(inputs: Sequence[int]) -> str:
    return "\n".join(f"Input {n} looks like a loopback — ignored" for n in inputs)


def stopped_early_note(outputs: int) -> str:
    return f"Stopped at the first answer: this sound card has {outputs} outputs."


def _khz(rate: int) -> str:
    return f"{rate / 1000:.1f}".rstrip("0").rstrip(".") + " kHz"


def sample_rate_message(device_rate: int | None, file_rate: int | None) -> str | None:
    """A blocking message when the sound card runs at another rate than the capture signals."""
    if device_rate is None or file_rate is None or device_rate == file_rate:
        return None
    return (f"Your sound card runs at {_khz(device_rate)}. Set it to {_khz(file_rate)} in Audio MIDI Setup, "
            "then check again.")


def card_rate_message(input_rate: int | None, output_rate: int | None, file_rate: int | None) -> str | None:
    """Name the mismatched half; equal rates keep the existing duplex wording."""
    if file_rate is None and input_rate is not None and output_rate is not None and input_rate != output_rate:
        return (f"Your sound card’s input runs at {_khz(input_rate)} and its output runs at {_khz(output_rate)}. "
                "Set both to the same sample rate in Audio MIDI Setup, then check again.")
    if input_rate == output_rate:
        return sample_rate_message(input_rate, file_rate)
    for half, rate in (("input", input_rate), ("output", output_rate)):
        if rate is not None and file_rate is not None and rate != file_rate:
            return (f"The {half} of your sound card runs at {_khz(rate)}. Set it to {_khz(file_rate)} "
                    "in Audio MIDI Setup, then check again.")
    return None


def card_rate_label(input_rate: int | None, output_rate: int | None) -> str:
    if input_rate is None or output_rate is None:
        return ""
    if input_rate == output_rate:
        return _khz(input_rate)
    return f"in {_khz(input_rate)} · out {_khz(output_rate)}"


def level_message(peak_dbfs: float, clip_threshold: float = ROUTE_CLIP_DBFS, *, locked: bool = False) -> tuple[Literal["ok", "clip"], str]:
    if peak_dbfs >= clip_threshold:
        return "clip", LOCKED_CLIP_TEXT if locked else CLIP_TEXT
    return "ok", f"Peak {peak_dbfs:.1f} dB · good. Do not touch the sound card gain from now on.".replace("-", "−", 1)


CONNECT_HELP = "\n".join((
    "No sound card in the list: plug it in, wait a moment, then press refresh.",
    "Two sound cards with the same name: unplug one, then press refresh.",
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
