"""Snapshot run configs and call the real parametric NAM trainer."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import os
import platform
import sys
import uuid
import hashlib
from contextlib import redirect_stdout, redirect_stderr
from . import UPSTREAM_REV
from .checks import absolute_data, check_project, read_json
from .architectures import apply_architecture, is_film, is_dual, FILM_FACTORY
from .workflow import read_state


def select_device(requested="auto"):
    import torch
    mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    if requested == "mps" and not mps:
        raise ValueError("MPS is unavailable. Use CPU or native arm64 Python on an Apple Silicon Mac.")
    if requested == "auto":
        return "mps" if mps else "cpu"
    if requested not in ("mps", "cpu"):
        raise ValueError("Choose auto, mps, or cpu.")
    return requested


def mac_learning_config(original, device, epochs=200, batch=4):
    if epochs < 1 or batch < 1:
        raise ValueError("Epochs and batch size must be positive.")
    config = copy.deepcopy(original)
    config["torch_compile"] = {"enabled": False}
    trainer = config.setdefault("trainer", {})
    trainer.update(accelerator=device, devices=1, precision="32-true", benchmark=False,
                   max_epochs=epochs, enable_progress_bar=False, log_every_n_steps=1)
    # Do not inherit multi-device strategies or resume arguments from other machines.
    trainer.pop("strategy", None)
    for name in ("train_dataloader", "val_dataloader"):
        loader = config.setdefault(name, {})
        loader.update(batch_size=batch, num_workers=0, pin_memory=False)
        loader.pop("prefetch_factor", None)
        loader.pop("persistent_workers", None)
    # With small capture sets, dropping the final batch can create an empty loader.
    config["train_dataloader"]["drop_last"] = False
    return config


def prepare_run(directory, device="auto", epochs=200, batch=4, architecture=None, input_pad_db=None):
    directory = Path(directory).expanduser().resolve()
    state = read_state(directory)
    calibration = copy.deepcopy(state.get("playback_calibration", {}))
    if input_pad_db is not None:
        import math
        if isinstance(input_pad_db, bool) or not math.isfinite(input_pad_db) or not 0 <= input_pad_db <= 30:
            raise ValueError("Playback input pad must be between 0 and 30 dB")
        calibration = {"confirmed": True, "input_pad_db": float(input_pad_db)}
    architecture = architecture if architecture is not None else state.get("model_architecture", "auto")
    name = directory.name
    # Regenerate from the project's latest captures, even if configs were exported earlier.
    if (directory / "capture_project.json").exists():
        from .controls import load_project, model_config
        from nam.capture.export import build_data_config, build_concat_learning_config
        project = load_project(directory)
        name = project.name or name
        data = build_data_config(project)
        model = model_config(project)
        learning = build_concat_learning_config(project)
    else:
        data = read_json(directory / "data.json")
        model = read_json(directory / "model_concat.json")
        learning = read_json(directory / "learning_concat.json")
    model = apply_architecture(model, architecture)
    report = check_project(directory, data, model)
    if not report.ok:
        raise ValueError(report.text())
    if model["net"]["name"] not in ("ConcatWaveNet", FILM_FACTORY):
        raise ValueError("This workflow supports concat and FiLM A2 models.")
    selected = select_device(device)
    learning = mac_learning_config(learning, selected, epochs, batch)
    data = absolute_data(data, directory)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = directory / "outputs" / f"{stamp}-{uuid.uuid4().hex[:8]}"
    gear_type = state.get("gear_kind", "pedal")
    if gear_type not in ("pedal", "amp"):
        raise ValueError("Project gear kind must be pedal or amp.")
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"upstream_revision": UPSTREAM_REV, "device": selected, "python": sys.version,
                "platform": platform.platform(), "project": str(directory), "warnings": report.warnings,
                "requested_epochs": epochs, "batch_size": batch, "playback_calibration": calibration,
                "model_architecture": architecture, "model_name": name, "gear_type": gear_type,
                "export_format": "SlimmableContainer" if is_dual(architecture) else
                                 ("ParametricWaveNet" if is_film(architecture) else "ConcatWaveNet"),
                "export_version": "0.7.0" if is_film(architecture) else "1.0.0"}
    import torch
    import nam
    manifest.update(torch_version=torch.__version__, nam_version=nam.__version__)
    paths = set()
    for split in ("train", "validation"):
        for entry in data[split]:
            merged = {**data.get("common", {}), **entry}
            paths.update(merged[k] for k in ("x_path", "y_path"))
    manifest["audio_sha256"] = {}
    for path in sorted(paths):
        digest = hashlib.sha256()
        with open(path, "rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        manifest["audio_sha256"][path] = digest.hexdigest()
    for name, value in (("data", data), ("model", model), ("learning", learning), ("manifest", manifest)):
        (out / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    if is_dual(architecture):
        for tier in ("standard", "nano"):
            child = out / "tiers" / tier
            child.mkdir(parents=True)
            profile = f"{'film' if is_film(architecture) else 'a2'}-{tier}"
            for name, value in (("data", data), ("model", apply_architecture(model, profile)),
                                ("learning", learning), ("manifest", {**manifest,
                                 "model_architecture": profile, "export_format":
                                 "ParametricWaveNet" if is_film(profile) else "ConcatWaveNet"})):
                (child / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    return out


def finish_exports(out):
    """Retain exported inference/calibration fields and add the project's gear identity."""
    from nam.capture.project import atomic_write_json
    manifest = read_json(out / "manifest.json")
    for path in out.glob("*_parametric.nam"):
        model = read_json(path)
        expected = ("ParametricWaveNet", "0.7.0") if is_film(manifest["model_architecture"]) else ("ConcatWaveNet", "1.0.0")
        if (model.get("architecture"), model.get("version")) != expected or model.get("sample_rate") != 48000:
            raise RuntimeError("Trainer export is not an Ardor-compatible 48 kHz model of the selected architecture.")
        metadata = model.setdefault("metadata", {})
        metadata.update(name=manifest["model_name"], gear_type=manifest["gear_type"])
        metadata["training_architecture"] = manifest["model_architecture"]
        atomic_write_json(path, model)


def run_training(directory, device="auto", epochs=200, batch=4, dry_run=False, architecture=None, input_pad_db=None):
    # Fail unsupported operations visibly, rather than quietly falling back on CPU.
    # Users can explicitly retry the identical captured dataset with --device cpu.
    out = prepare_run(directory, device, epochs, batch, architecture, input_pad_db)
    print(f"Run folder: {out}", flush=True)
    print(f"Settings: {read_json(out / 'manifest.json')['device']}, {epochs} epochs, batch {batch}", flush=True)
    if dry_run:
        print("Preflight passed; configs saved. No training started.", flush=True)
        return out
    if not is_dual(read_json(out / "manifest.json")["model_architecture"]):
        _train_prepared(out)
        from .playback import qualify_run
        qualify_run(out)
        return out
    from nam.capture.project import atomic_write_json
    from .bundle import bundle_a2
    atomic_write_json(out / "status.json", {"status": "running"})
    try:
        metrics = {}
        for index, tier in enumerate(("standard", "nano")):
            print(f"Training tier: {tier.capitalize()} · {epochs} epochs", flush=True)
            child = out / "tiers" / tier
            _train_prepared(child, tier.capitalize(), index * epochs, 2 * epochs)
            metrics[tier] = read_json(child / "metrics.json")
        bundle_a2(out / "tiers/standard/model_parametric.nam", out / "tiers/nano/model_parametric.nam",
                  out / "model_parametric.nam")
        atomic_write_json(out / "metrics.json", {"tiers": metrics})
        atomic_write_json(out / "status.json", {"status": "exported"})
        print(f"Model exported: {out / 'model_parametric.nam'} · Standard + Nano", flush=True)
    except BaseException as exc:
        atomic_write_json(out / "status.json", {"status": "failed_or_interrupted", "error": str(exc)})
        raise
    finally:
        with (out / "training.log").open("w") as combined_log:
            for tier in ("standard", "nano"):
                log = out / "tiers" / tier / "training.log"
                if log.is_file():
                    combined_log.write(f"\n{tier.capitalize()}\n")
                    with log.open() as source:
                        for line in source:
                            combined_log.write(line)
    from .playback import qualify_run
    qualify_run(out)
    return out


def _train_prepared(out, tier="", epoch_offset=0, total_epochs=None):
    os.environ.setdefault("MPLBACKEND", "Agg")
    from nam.train import parametric as trainer_module
    import pytorch_lightning as pl

    class Progress(pl.Callback):
        def on_train_epoch_start(self, trainer, module):
            print(f"Epoch {epoch_offset + trainer.current_epoch + 1}/{total_epochs or trainer.max_epochs} started"
                  + (f" · {tier}" if tier else ""), flush=True)

        def on_train_batch_end(self, trainer, module, outputs, batch, batch_idx):
            if (batch_idx + 1) % 25 == 0:
                print(f"Epoch {trainer.current_epoch + 1}: {batch_idx + 1}/{trainer.num_training_batches} batches", flush=True)

        def on_train_epoch_end(self, trainer, module):
            metrics = []
            saved_metrics = {"epoch": trainer.current_epoch + 1}
            for key in ("ESR", "MSE", "val_loss"):
                value = trainer.callback_metrics.get(key)
                if value is not None:
                    number = float(value.detach().cpu()) if hasattr(value, 'detach') else float(value)
                    metrics.append(f"{key}={number:.6g}")
                    # JSON has no infinity/NaN; preserve only meaningful measurements.
                    import math
                    if math.isfinite(number):
                        saved_metrics[key] = number
            from nam.capture.project import atomic_write_json
            atomic_write_json(out / "metrics.json", saved_metrics)
            print(f"Epoch {epoch_offset + trainer.current_epoch + 1} finished. "
                  + (f"{tier}: " if tier else "") + ", ".join(metrics), flush=True)

    class Tee:
        def __init__(self, console, logfile):
            self.console, self.logfile = console, logfile

        def write(self, value):
            self.logfile.write(value)
            self.console.write(value)
            return len(value)

        def flush(self):
            self.logfile.flush()
            self.console.flush()

        def isatty(self):
            return False

    # This pinned trainer builds callbacks internally. Add progress without modifying
    # its source or replacing checkpoint/validation callbacks. Restore after the run.
    state = {"status": "running"}
    (out / "status.json").write_text(json.dumps(state))
    create_callbacks = trainer_module._create_parametric_callbacks
    original_export = trainer_module._export_parametric
    if is_film(read_json(out / "manifest.json")["model_architecture"]):
        from .film import FiLMA2, export_film
        def export_model(model, *args, **kwargs):
            return (export_film if isinstance(model, FiLMA2) else original_export)(model, *args, **kwargs)
        trainer_module._export_parametric = export_model
    trainer_module._create_parametric_callbacks = lambda *a, **kw: [*create_callbacks(*a, **kw), Progress()]
    try:
        with (out / "training.log").open("w", buffering=1) as logfile:
            with redirect_stdout(Tee(sys.stdout, logfile)), redirect_stderr(Tee(sys.stderr, logfile)):
                trainer_module.main(read_json(out / "data.json"), read_json(out / "model.json"),
                                    read_json(out / "learning.json"), out, no_show=True, make_plots=False)
        if not (out / "model_parametric.nam").is_file():
            raise RuntimeError("Trainer ended without model_parametric.nam. Inspect checkpoints and the log.")
        finish_exports(out)
    except BaseException as exc:
        (out / "status.json").write_text(json.dumps({"status": "failed_or_interrupted", "error": str(exc)}))
        raise
    else:
        (out / "status.json").write_text(json.dumps({"status": "exported"}))
        print(f"Model exported: {out / 'model_parametric.nam'}", flush=True)
        print("Evaluate held-out ESR and listen before treating this model as finished.", flush=True)
    finally:
        trainer_module._create_parametric_callbacks = create_callbacks
        trainer_module._export_parametric = original_export
    return out
