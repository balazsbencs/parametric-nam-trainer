#!/usr/bin/env python3
"""Headless CUDA adapter for the frozen Ardor-compatible parametric trainer."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def verify():
    entries = read(ROOT / "SHA256.json")
    for name, expected in entries.items():
        with (ROOT / name).open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Package checksum mismatch: {name}")
    print(f"Verified {len(entries)} packaged files.", flush=True)


def device_check(device):
    import torch
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable. Select a Runpod PyTorch GPU template; no CPU fallback is used.")
        gpu = torch.cuda.get_device_properties(0)
        print(f"GPU: {gpu.name}; VRAM: {gpu.total_memory / 2**30:.1f} GiB; "
              f"torch {torch.__version__}; CUDA {torch.version.cuda}", flush=True)
    # Exercise a convolution and backward pass, rather than only checking discovery.
    model = torch.nn.Conv1d(2, 8, 6).to(device)
    model(torch.randn(1, 2, 8192, device=device)).square().mean().backward()
    if device == "cuda":
        torch.cuda.synchronize()
    print(f"Convolution/backpropagation check passed on {device}.", flush=True)


def configure(device, batch):
    from parametric_mac import training
    return training


def execute(out, training, hourly_rate):
    import torch
    import pytorch_lightning as pl
    from nam.train import parametric as upstream
    learning = read(out / "learning.json")
    target_epochs = learning["trainer"]["max_epochs"]
    original = upstream._create_parametric_callbacks
    previous = read(out / "timing.json") if (out / "timing.json").exists() else {"epochs": []}
    timings = previous["epochs"]
    device = read(out / "manifest.json")["device"]

    class Timing(pl.Callback):
        def on_train_epoch_start(self, trainer, module):
            if device == "cuda":
                torch.cuda.synchronize()
            self.start = time.perf_counter()

        def on_train_epoch_end(self, trainer, module):
            if device == "cuda":
                torch.cuda.synchronize()
            epoch = trainer.current_epoch + 1
            seconds = time.perf_counter() - self.start
            timings[:] = [entry for entry in timings if entry["epoch"] != epoch]
            timings.append({"epoch": epoch, "seconds": seconds})
            # Ignore the first measured epoch for warmup, whenever possible.
            samples = [entry["seconds"] for entry in timings[1:]] or [seconds]
            mean = statistics.mean(samples)
            estimate = {
                "epochs": timings, "mean_epoch_seconds_excluding_warmup": mean,
                "target_epochs": target_epochs,
                "estimated_total_training_hours": mean * target_epochs / 3600,
                "estimated_remaining_training_hours": mean * max(0, target_epochs - epoch) / 3600,
                "gpu_hourly_rate_usd": hourly_rate,
                "estimated_total_gpu_cost_usd": mean * target_epochs / 3600 * hourly_rate,
                "note": "Same configuration only; excludes setup, export, storage and idle GPU charges.",
            }
            write(out / "timing.json", estimate)
            print(f"Timing: epoch {epoch}: {seconds:.1f}s; mean {mean:.1f}s; "
                  f"200 epochs ≈ {mean * 200 / 3600:.2f}h / ${mean * 200 / 3600 * hourly_rate:.2f} GPU time",
                  flush=True)

    def callbacks(*args, **kwargs):
        result = original(*args, **kwargs)
        for callback in result:
            if isinstance(callback, pl.callbacks.ModelCheckpoint):
                # Keep stable callback paths across resume, plus a complete latest checkpoint.
                # Lightning serializes this into checkpoint state. Keep it a string
                # so modern PyTorch's weights-only loader does not reject PosixPath.
                callback.dirpath = str(out / "checkpoints")
        result[0].save_last = True
        return [*result, Timing()]

    upstream._create_parametric_callbacks = callbacks
    # Preserve console output and checkpoints if interrupted; resume overwrites the live log.
    if (out / "training.log").exists():
        (out / "training.log").rename(out / f"training-before-resume-{time.time_ns()}.log")
    started = time.perf_counter()
    try:
        training._train_prepared(out)
        prepare_playback(out)
    finally:
        upstream._create_parametric_callbacks = original
        write(out / "session.json", {"wall_seconds": time.perf_counter() - started,
                                    "torch_version": torch.__version__,
                                    "cuda_version": torch.version.cuda,
                                    "device": device})
    return out


def prepare_playback(out):
    # Keep the raw export internal. Qualification is the only publication path.
    destination = out / 'playback'
    destination.mkdir(exist_ok=True)
    final = destination / 'model_playback.nam'
    if final.exists():
        final.replace(destination / 'previous-qualified.json')
    print('Raw model retained. Run collect to check normal notes and reserved attacks before playback.', flush=True)


def qualify_export(out, project=None, source=None):
    from parametric_mac.playback import qualify_run
    if source is not None:
        raise ValueError('Recovery alone cannot repair learned transients. Fine-tune the raw model with the packaged attacks.')
    report = qualify_run(out)
    if not report['passed']:
        raise ValueError(f'Playback qualification failed; inspect {out / "playback/qualification.json"}. Checkpoints are retained.')
    return out / 'playback/model_playback.nam'


def train(args):
    device_check(args.device)
    import pytorch_lightning as pl
    pl.seed_everything(42, workers=True)
    training = configure(args.device, args.batch)
    out = training.prepare_run(args.project, args.device, args.epochs, args.batch, args.architecture, warm_start=args.warm_start,
                               performance={k:v for k,v in {'precision':args.precision, 'workers':args.workers,
                                   'ny':args.ny, 'compile':args.compiled, 'scheduler':args.scheduler,
                                   'early_stopping_patience':args.early_stopping_patience}.items() if v is not None},
                               performance_profile=args.performance_profile)
    manifest = read(out / "manifest.json")
    manifest["runpod_package"] = read(ROOT / "PROVENANCE.json")
    manifest["package_sources_sha256"] = read(ROOT / "SHA256.json")
    write(out / "manifest.json", manifest)
    print(f"Run folder: {out}", flush=True)
    if args.check:
        print("Dataset preflight passed. No training started.")
        return out
    return execute(out, training, args.hourly_rate)


def resume(args):
    out = args.run.resolve()
    manifest = read(out / "manifest.json")
    if manifest.get("package_sources_sha256") != read(ROOT / "SHA256.json"):
        raise ValueError("Resume requires a run made with this exact package. Mac checkpoints need a separate migration.")
    device = manifest["device"]
    device_check(device)
    checkpoint = out / "checkpoints" / "last.ckpt"
    if not checkpoint.is_file():
        raise ValueError("No checkpoints/last.ckpt; complete at least one validation epoch first.")
    import torch
    # Only load checkpoints produced by this package (PyTorch checkpoints contain pickle).
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if args.epochs <= state["epoch"] + 1:
        raise ValueError("--epochs is the total target and must exceed the checkpoint's completed epoch count.")
    del state
    learning = read(out / "learning.json")
    # Recheck the original audio against the manifest before continuing optimizer state.
    for name, expected in manifest["audio_sha256"].items():
        with Path(name).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                raise ValueError(f"Training audio changed: {name}")
    learning["trainer"]["max_epochs"] = args.epochs
    learning["trainer_fit_kwargs"] = {"ckpt_path": str(checkpoint)}
    write(out / "learning.json", learning)
    training = configure(device, learning["train_dataloader"]["batch_size"])
    print(f"Resuming {out} to {args.epochs} total epochs.", flush=True)
    return execute(out, training, args.hourly_rate)


def collect(args):
    out = args.run.resolve()
    model = qualify_export(out)
    target = out.parent / f"{out.name}-download.zip"
    with ZipFile(target, "x", ZIP_DEFLATED) as archive:
        for path in out.rglob("*"):
            # Publish only the qualified NAM; raw/checkpoint .nam exports are internal.
            if path.is_file() and (path == model or path.suffix in (".json", ".log", ".csv", ".yaml")):
                archive.write(path, path.relative_to(out))
    print(f"Download: {target}\nModel: {model}\nKeep checkpoints separately if you want to resume.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("doctor")
    for name in ("benchmark", "train"):
        command = sub.add_parser(name)
        command.add_argument("--project", type=Path, default=ROOT / "project")
        command.add_argument("--epochs", type=int, default=3 if name == "benchmark" else 200)
        command.add_argument("--batch", type=int, default=1)
        command.add_argument('--warm-start', type=Path, help='Matching raw NAM; defaults to project/fine_tune.json')
        command.add_argument("--architecture", choices=("a2-standard", "a2-nano"), default="a2-standard")
        command.add_argument("--hourly-rate", type=float, default=0.89)
        command.add_argument("--device", choices=("cuda", "cpu"), default="cuda",
                             help="CPU is for local verification only; default CUDA never falls back.")
        command.add_argument('--precision', choices=('32-true','bf16-mixed'), default=None)
        command.add_argument('--workers', type=int, default=None)
        command.add_argument('--ny', type=int, default=None)
        command.add_argument('--compile', dest='compiled', action='store_true', default=None)
        command.add_argument('--scheduler', choices=('original','plateau'), default=None)
        command.add_argument('--early-stopping-patience', type=int, default=None)
        command.add_argument('--performance-profile', type=Path)
        command.add_argument("--check", action="store_true", help="Validate and save configs without training")
    command = sub.add_parser('tune', help='Measure disposable speed trials; does not start a full training run')
    command.add_argument('--project', type=Path, default=ROOT/'project')
    command.add_argument('--device', choices=('cuda','cpu'), default='cuda')
    command.add_argument('--architecture', choices=('a2-standard','a2-nano'), default='a2-standard')
    command.add_argument('--batches', type=int, nargs='+', default=[4,8,16,32])
    command.add_argument('--steps', type=int, default=4)
    command.add_argument('--max-trials', type=int, default=8)
    command = sub.add_parser("resume")
    command.add_argument("run", type=Path)
    command.add_argument("--epochs", type=int, default=200, help="Total target, including completed epochs")
    command.add_argument("--hourly-rate", type=float, default=0.89)
    command = sub.add_parser("collect")
    command.add_argument("run", type=Path)
    command = sub.add_parser("qualify", help="Qualify a completed run and publish its playback NAM")
    command.add_argument("run", type=Path)
    args = parser.parse_args()
    if hasattr(args, "epochs") and args.epochs < 1:
        parser.error("--epochs must be positive")
    if hasattr(args, "batch") and args.batch < 1:
        parser.error("--batch must be positive")
    if hasattr(args, "hourly_rate") and (not math.isfinite(args.hourly_rate) or args.hourly_rate < 0):
        parser.error("--hourly-rate must be finite and nonnegative")
    if args.command == "verify":
        verify()
    elif args.command == "doctor":
        device_check("cuda")
        import nam.train.parametric
        import parametric_mac.training
        print("Headless trainer imports passed.")
    elif args.command == 'tune':
        device_check(args.device)
        from parametric_mac.benchmark import tune
        tune(args.project, args.device, args.architecture, args.batches, args.steps, max_trials=args.max_trials)
    elif args.command in ("benchmark", "train"):
        train(args)
    elif args.command == "resume":
        resume(args)
    elif args.command == "qualify":
        qualify_export(args.run)
    else:
        collect(args)


if __name__ == "__main__":
    main()
