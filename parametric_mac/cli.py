import argparse
import importlib.util
import platform
import sys
from pathlib import Path


def doctor():
    print(f"Python: {sys.version.split()[0]} ({platform.machine()})")
    print(f"System: {platform.system()} {platform.release()}")
    success = True
    if platform.system() != "Darwin":
        print("NOTE: this is not macOS; Mac/CoreAudio/MPS checks cannot be performed here.")
    elif platform.machine() != "arm64":
        print("WARNING: use native arm64 Python to access Apple Silicon MPS.")
    for module in ("numpy", "soundfile", "torch", "PySide6", "nam.capture.gui.main", "nam.train.parametric"):
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, AttributeError, ValueError):
            found = False
        print(f"{module}: {'available' if found else 'MISSING — run Install.command'}")
        success &= found
    if importlib.util.find_spec("torch"):
        import torch
        print(f"PyTorch: {torch.__version__}; MPS available: {torch.backends.mps.is_available()}")
        if torch.backends.mps.is_available():
            try:
                x = torch.ones(1, 1, 64, device="mps", requires_grad=True)
                layer = torch.nn.Conv1d(1, 2, 3).to("mps")
                layer(x).square().mean().backward()
                torch.mps.synchronize()
                print("MPS convolution/backprop smoke check: passed (not a full model benchmark)")
            except RuntimeError as exc:
                success = False
                print(f"MPS smoke check failed: {exc}; select CPU.")
    try:
        import sounddevice as sd
        print("Audio devices (verify input/output channel counts in Connect):")
        print(sd.query_devices())
    except Exception as exc:
        print(f"Audio device enumeration unavailable: {exc}")
        print("On Mac, connect the UMC22 and grant microphone access to the launching app.")
    return 0 if success else 1


def project_configs(directory, architecture=None):
    directory = Path(directory).expanduser().resolve()
    from .workflow import read_state
    selected = architecture if architecture is not None else read_state(directory).get("model_architecture", "auto")
    if (directory / "capture_project.json").exists():
        from .controls import load_project, model_config
        from nam.capture.export import build_data_config
        project = load_project(directory)
        return build_data_config(project), model_config(project, selected)
    if selected != "auto":
        from .architectures import apply_architecture
        from .checks import read_json
        return read_json(directory / "data.json"), apply_architecture(read_json(directory / "model_concat.json"), selected)
    return None, None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guided pedal capture and Apple Silicon parametric NAM training")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="Check dependencies, Apple GPU and audio devices")
    capture = sub.add_parser("capture", help="Open the native capture app with Mac training controls")
    capture.add_argument("--train-tab", action="store_true")
    assets = sub.add_parser("inputs", help="Download and verify the short upstream reamp signals")
    assets.add_argument("directory", type=Path)
    check = sub.add_parser("check", help="Check a capture project before training")
    check.add_argument("project", type=Path)
    from .architectures import ARCHITECTURES
    check.add_argument("--architecture", choices=tuple(ARCHITECTURES))
    train = sub.add_parser("train", help="Train a concat or FiLM A2 model from a capture project")
    train.add_argument("project", type=Path)
    train.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    train.add_argument("--epochs", type=int, default=200)
    train.add_argument("--batch", type=int, default=4)
    train.add_argument("--dry-run", action="store_true")
    train.add_argument("--input-pad-db", type=float, help="Confirm playback-to-capture input attenuation (0–30 dB); use 12 only for a dataset captured in that digital domain")
    train.add_argument("--architecture", choices=tuple(ARCHITECTURES), help="a2-* uses concat; film-* uses FiLM (continuous controls only); *-dual trains Standard + Nano into one file; auto preserves the recipe")
    qualify = sub.add_parser("qualify", help="Calibrate and qualify an existing saved run without retraining")
    qualify.add_argument("run", type=Path)
    qualify.add_argument("--input-pad-db", type=float, help="Explicit playback input mapping for this saved run")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor()
        if args.command == "inputs":
            from .assets import download_inputs
            download_inputs(args.directory)
        elif args.command == "check":
            from .checks import check_project
            data, model = project_configs(args.project, args.architecture)
            report = check_project(args.project, data, model)
            print(report.text())
            return 0 if report.ok else 1
        elif args.command == "train":
            from .training import run_training
            run_training(args.project, args.device, args.epochs, args.batch, args.dry_run, args.architecture, args.input_pad_db)
        elif args.command == "qualify":
            from .playback import qualify_run
            return 0 if qualify_run(args.run, args.input_pad_db)["passed"] else 1
        else:
            from .gui import launch
            return launch(getattr(args, "train_tab", False))
    except (OSError, ValueError, RuntimeError, ImportError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Captures and existing run outputs are preserved.", file=sys.stderr)
        return 130
    return 0
