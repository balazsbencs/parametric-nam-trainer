"""Read-only checks of captured audio and the trainer's actual data configuration."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import numpy as np
import soundfile as sf


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    captures: dict[str, int] = field(default_factory=dict)
    sample_rate: int | None = None

    @property
    def ok(self):
        return not self.errors

    def text(self):
        lines = [f"{k}: {v} captures" for k, v in self.captures.items()]
        if self.sample_rate:
            lines.append(f"Sample rate: {self.sample_rate} Hz")
        lines.extend(f"ERROR: {x}" for x in self.errors)
        lines.extend(f"WARNING: {x}" for x in self.warnings)
        lines.append("Ready for training." if self.ok else "Fix the errors before training.")
        return "\n".join(lines)


def read_json(path):
    with Path(path).open() as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def absolute_data(data, directory):
    """Resolve paths relative to the project, including shared common paths."""
    result = json.loads(json.dumps(data))
    for entry in [result.get("common", {})] + [
        e for split in ("train", "validation") for e in result.get(split, [])
    ]:
        for key in ("x_path", "y_path"):
            if key in entry:
                path = Path(entry[key]).expanduser()
                entry[key] = str((directory / path).resolve() if not path.is_absolute() else path.resolve())
    return result


def audio_stats(path):
    peak, energy, n, nonfinite, clipped = 0.0, 0.0, 0, False, False
    with sf.SoundFile(path) as audio:
        info = (audio.samplerate, audio.channels, len(audio), audio.subtype)
        for block in audio.blocks(blocksize=65536, dtype="float32", always_2d=True):
            if not np.isfinite(block).all():
                nonfinite = True
                continue
            peak = max(peak, float(np.max(np.abs(block), initial=0)))
            clipped |= bool(np.any(np.abs(block) >= 0.999))
            energy += float(np.sum(block.astype(np.float64) ** 2))
            n += block.size
    return {"rate": info[0], "channels": info[1], "frames": info[2],
            "subtype": info[3], "peak": peak, "rms": math.sqrt(energy / max(n, 1)),
            "nonfinite": nonfinite, "clipped": clipped}


def check_project(directory, data=None, model=None):
    directory = Path(directory).expanduser().resolve()
    report = Report()
    try:
        data = absolute_data(data or read_json(directory / "data.json"), directory)
        model = model or read_json(directory / "model_concat.json")
        if data.get("type") != "parametric":
            raise ValueError("data.json must use type 'parametric'. Export ConcatWaveNet configs in Capture.")
        params = model["net"]["config"]["params"]
        from .architectures import FILM_FACTORY
        if model["net"]["name"] == FILM_FACTORY:
            if not 1 <= len(params) <= 16:
                raise ValueError("FiLM requires 1–16 continuous controls. Choose a concat profile for more controls.")
            if any(p.get("type", "continuous") != "continuous" for p in params):
                raise ValueError("FiLM supports continuous controls only. Choose a concat profile for switches.")
        names = [p["name"] for p in params]
        if not names or len(names) > 24 or any(not str(n).strip() for n in names) or len(set(names)) != len(names):
            raise ValueError("Model requires 1–24 controls with nonempty unique names.")
        # Lower-bound receptive field for the fork's exported ConcatWaveNet recipe.
        receptive = 1
        for layer in model["net"]["config"].get("layers", []):
            kernels, dilations = layer["kernel_sizes"], layer["dilations"]
            if len(kernels) != len(dilations):
                raise ValueError("Model kernel sizes and dilations must have matching lengths.")
            receptive += sum((k - 1) * d for k, d in zip(kernels, dilations))
            receptive += layer.get("head", {}).get("kernel_size", 1) - 1
        # File/audio checks deliberately work without torch installed.
        settings = {"train": set(), "validation": set()}
        cache, rates, outputs = {}, set(), set()
        for split in settings:
            entries = data.get(split, [])
            if not isinstance(entries, list) or not entries:
                report.errors.append(f"{split}: needs at least one captured entry.")
                continue
            report.captures[split] = len(entries)
            for i, entry in enumerate(entries):
                label = f"{split} capture {i + 1}"
                merged = {**data.get("common", {}), **entry}
                values = merged.get("params", {})
                if set(values) != set(names):
                    report.errors.append(f"{label}: controls differ from the model's controls.")
                    continue
                valid = True
                for p in params:
                    v = values[p["name"]]
                    if not isinstance(v, (int, float)) or not math.isfinite(v) or not p["min"] <= v <= p["max"]:
                        report.errors.append(f"{label}: {p['name']} is outside its finite range.")
                        valid = False
                    elif p.get("type") == "switch" and v != int(v):
                        report.errors.append(f"{label}: switch {p['name']} needs an integer position.")
                        valid = False
                if valid:
                    settings[split].add(tuple(values[n] for n in names))
                pair = []
                for key in ("x_path", "y_path"):
                    path = merged.get(key)
                    if not path or not Path(path).is_file():
                        report.errors.append(f"{label}: missing {key}: {path}")
                        continue
                    if path not in cache:
                        cache[path] = audio_stats(path)
                    stats = cache[path]
                    pair.append(stats)
                    rates.add(stats["rate"])
                    if stats["channels"] != 1:
                        report.errors.append(f"{label}: {key} must be mono.")
                    if stats["nonfinite"]:
                        report.errors.append(f"{label}: {key} contains NaN or infinity.")
                    if stats["clipped"]:
                        report.errors.append(f"{label}: {key} reaches digital full scale; recapture with more headroom.")
                    if stats["rms"] < 1e-6:
                        report.errors.append(f"{label}: {key} is effectively silent; check routing.")
                    elif stats["rms"] < 1e-4:
                        report.warnings.append(f"{label}: {key} is very quiet; check gain and noise.")
                    if key == "y_path":
                        if path in outputs:
                            report.errors.append(f"{label}: output WAV reused by another capture.")
                        outputs.add(path)
                if len(pair) == 2:
                    delay = merged.get("delay", 0)
                    if not isinstance(delay, int) or isinstance(delay, bool):
                        report.errors.append(f"{label}: delay must be an integer number of samples.")
                        continue
                    if pair[0]["frames"] != pair[1]["frames"]:
                        report.errors.append(f"{label}: input/output lengths differ; check capture/export trimming.")
                    frames = min(s["frames"] for s in pair)
                    rate = pair[0]["rate"]
                    start = merged.get("start_seconds", 0) or 0
                    stop = merged.get("stop_seconds")
                    start = int(start * rate)
                    stop = frames if stop is None else int(stop * rate)
                    # NAM slices the requested window before applying the delay.
                    start = frames + start if start < 0 else start
                    stop = frames + stop if stop < 0 else stop
                    usable = stop - start - abs(delay)
                    if start < 0 or stop > frames or stop <= start or usable < receptive:
                        report.errors.append(f"{label}: invalid training window after delay alignment.")
                    ny = merged.get("ny")
                    if ny is not None and (not isinstance(ny, int) or ny <= 0 or usable < ny + receptive - 1):
                        report.errors.append(f"{label}: audio window is shorter than ny plus model context, or ny is invalid.")
        if len(rates) != 1:
            report.errors.append("All input and output WAVs must have the same sample rate.")
        else:
            report.sample_rate = next(iter(rates))
            if report.sample_rate != 48000:
                report.errors.append("Ardor-compatible parametric models require 48000 Hz recordings.")
            declared = model["net"]["config"].get("sample_rate")
            if declared and declared != report.sample_rate:
                report.errors.append("Model sample rate differs from the captured audio.")
        if settings["train"] & settings["validation"]:
            report.errors.append("Training and validation share knob settings. Hold out unseen settings to test interpolation.")
        if len(settings["validation"]) < 3:
            report.warnings.append("Fewer than three held-out settings: interpolation quality is poorly tested.")
        if directory.joinpath("capture_project.json").exists():
            project = read_json(directory / "capture_project.json")
            pending = sum(e.get("status") != "captured" for e in project.get("entries", []))
            if pending:
                report.warnings.append(f"{pending} planned captures remain. Training will use only completed captures.")
            for entry in project.get("entries", []):
                if entry.get("status") != "captured":
                    continue
                qa = entry.get("qa") or {}
                faults = [k for k in ("clipping", "delay_disagreement", "loopback_disagreement") if qa.get(k)]
                if faults:
                    report.errors.append(f"Capture {entry.get('y_path')}: capture QA flagged {', '.join(faults)}; review or recapture.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
        report.errors.append(str(exc))
    return report
