"""Render every page of the native app in dark and light, at desktop and compact size.

No audio is recorded and no model is trained: the script builds a synthetic demo project with generated
signals, a committed plan, saved takes and a run folder with a model file, then grabs the window.

    .venv/bin/python scripts/render_native.py [--out DIR]

Settings and projects go to temporary folders unless PARAMETRIC_SETTINGS_DIR / PARAMETRIC_PROJECTS_ROOT are set.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# A throwaway home folder: no real settings or projects are touched, and paths render as ~/Music/Parametric/…
os.environ["HOME"] = tempfile.mkdtemp(prefix="parametric-home-")
os.environ.setdefault("PARAMETRIC_SETTINGS_DIR", tempfile.mkdtemp(prefix="parametric-render-"))
os.environ.setdefault("PARAMETRIC_PROJECTS_ROOT", str(Path(os.environ["HOME"]) / "Music" / "Parametric"))

import numpy as np
import soundfile as sf
from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from nam.capture.audio import DeviceInfo
from parametric_mac.capture_cards import CaptureCard

from parametric_mac.find_route import FindResult, Route

ROOT = Path(__file__).resolve().parents[1]
SIZES = (("desktop", (1140, 900)), ("compact", (800, 680)))
MODES = ("dark", "light")
ROUTE_OK = SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False, loopback_disagreement=False,
                           crosscheck=None, peak=-9.2, latency=SimpleNamespace(delay=17, peak_delay=17.0))
TRAIN_LOG = "".join(f"Epoch {i}/400 started\nEpoch {i} finished. standard: ESR={0.9 / i ** 0.7:.4f}, MSE=0.1\n"
                    for i in range(1, 120))


def synthetic_inputs() -> Path:
    folder = Path(tempfile.mkdtemp(prefix="parametric-inputs-"))
    for name in ("inputTrunc.wav", "validation.wav"):
        sf.write(folder / name, np.zeros(4800, dtype=np.float32), 48000)
    return folder


def save_take(window, entry, inputs: Path) -> None:
    from nam.capture.project import save_project
    entry.status, entry.delay = "captured", 0
    target = window.project_dir / entry.y_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inputs / "validation.wav", target)
    save_project(window.project, window.project_dir)


def add_run(window) -> None:
    run = window.project_dir / "outputs" / "demo-run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text(json.dumps({"model_architecture": "a2-dual"}))
    (run / "status.json").write_text(json.dumps({"status": "exported"}))
    (run / "metrics.json").write_text(json.dumps({"tiers": {"standard": {"epoch": 200, "ESR": 0.0123},
                                                            "nano": {"epoch": 200, "ESR": 0.0211}}}))
    (run / "model_parametric.nam").write_text("{}")


class Renderer:
    def __init__(self, app, window, out: Path):
        self.app, self.window, self.out, self.files = app, window, out, []

    def shoot(self, name: str) -> None:
        for mode in MODES:
            self.window.appearance.set_choice(mode)
            for size_name, size in SIZES:
                self.window.resize(*size)
                self.app.processEvents()
                QTest.qWait(60)
                path = self.out / f"{name}-{mode}-{size_name}.png"
                self.window.grab().save(str(path))
                self.files.append(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))


def build_window(inputs: Path):
    import nam.capture.gui.main as upstream
    from parametric_mac.ui import project_io
    from nam.capture import audio
    from parametric_mac import device_rates
    for method in ("warning", "critical", "information"):
        setattr(upstream._QMessageBox, method, staticmethod(lambda *a, **k: None))  # no modal boxes
    project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
    from parametric_mac.gui import MacWindow
    devices = [DeviceInfo(0, "Scarlett 2i2", "Core Audio", 2, 2, 48000.0)]
    upstream._list_devices = lambda **kw: devices
    audio.list_devices = lambda **kw: devices
    device_rates.live_device_state = lambda: ({}, {})
    window = MacWindow()
    window._render_devices = devices
    window._inputs_dir = inputs
    window.device_combo.setCurrentIndex(0)
    assert isinstance(window.device_combo.currentData(), CaptureCard)
    window.show()
    return window


def find_route(window) -> None:
    """Run Find with a stubbed scan that answers on Output 1 → Input 1; nothing is played."""
    found = FindResult("found", (Route(1, 1, -16.0, ()),), ())
    window._scan_outputs = lambda target, progress, cancel: found
    window.find_button.click()
    for _ in range(250):
        if window._worker is None:
            break
        QTest.qWait(20)
    if not window.find_result.text().startswith("Found:"):
        raise RuntimeError(f"Find did not run: {window.find_result.text()!r}")


def render_setup(r: Renderer, connect_only: bool = False) -> None:
    w = r.window
    if not connect_only:
        r.shoot("start-empty")
    w._start_new_capture()
    w.pedal_name.setText("Klon-style drive")
    w.pedal_name.editingFinished.emit()
    if not connect_only:
        r.shoot("gear")
    w.gear_next_button.click()
    r.shoot("connect-not-ready")
    original = list(w._render_devices)
    w._render_devices[:] = [*original, DeviceInfo(2, "USB Audio CODEC", "Core Audio", 0, 2, 48000),
                           DeviceInfo(3, "USB Audio CODEC", "Core Audio", 2, 0, 48000)]
    w._refresh_devices()
    w.device_combo.setCurrentIndex(1)
    r.shoot("connect-split")
    w.wire_check.setChecked(True)
    find_route(w)
    r.shoot("connect-split-found")
    w._render_devices[:] = original
    w._refresh_devices()
    w.device_combo.setCurrentIndex(0)
    find_route(w)
    w._on_route_test_success(ROUTE_OK)
    r.shoot("connect-ready")


def render_record(r: Renderer, inputs: Path) -> None:
    from nam.capture.project import QAModel
    w = r.window
    w.go_to_step("record")
    r.shoot("record-choose")
    w.record_start_button.click()
    r.shoot("record-loop")
    entry = w._shown_entry
    save_take(w, entry, inputs)
    w._recording_entry = entry
    w._on_capture_success(QAModel(peak=0.0, clipping=True, messages=["Clipping detected"]))
    r.shoot("record-clipped")


def render_train_and_listen(r: Renderer, inputs: Path) -> None:
    w = r.window
    for entry in w.project.entries:
        if entry.status != "captured":
            save_take(w, entry, inputs)
    w._retry_entry = None
    w._refresh_all()
    w.go_to_step("train")
    r.shoot("train-before")
    job = QProcess()
    job.start(sys.executable, ["-c", "import time; time.sleep(60)"])
    job.waitForStarted(5000)
    w.process, w.command = job, "train"
    w._handle_log_text(TRAIN_LOG)
    w._sync_states()
    r.shoot("train-running")
    job.kill()
    job.waitForFinished(3000)
    w.process = None
    w._after_job("train", 1, "RuntimeError: MPS backend out of memory\n")
    r.shoot("train-failed")
    add_run(w)
    w._after_job("train", 0, "")
    w.go_to_step("listen")
    r.shoot("listen")
    w.go_to_step("start")
    r.shoot("start-recent")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "screenshots" / "native")
    parser.add_argument("--connect-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    inputs = synthetic_inputs()
    renderer = Renderer(app, build_window(inputs), args.out)
    render_setup(renderer, args.connect_only)
    if not args.connect_only:
        render_record(renderer, inputs)
        render_train_and_listen(renderer, inputs)
    (args.out / ("connect-evidence.json" if args.connect_only else "evidence.json")).write_text(json.dumps({"files": renderer.files, "audio_recorded": False,
                                                        "model_trained": False}, indent=2))
    print(f"{len(renderer.files)} screenshots in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
