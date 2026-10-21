from gui_harness import run_gui

TRAIN_SCRIPT = r"""
import hashlib, json, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
app = QApplication([])
from nam.capture.project import save_project
from parametric_mac.ui import project_io
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window.resize(1140, 900); window.show(); app.processEvents()
window._start_new_capture(); window.gear_next_button.click()
window.go_to_step("record"); window.record_start_button.click()

# Not recorded yet: the cards wait and point to Record.
window.go_to_step("train"); app.processEvents()
assert not window.train_button.isEnabled()
assert window.train_readiness.text().startswith("Finish recording first: 0 of 40 takes saved."), window.train_readiness.text()
assert window.train_go_record.isVisible()
assert not any(card.isEnabled() for card in window.mode_cards)

for entry in window.project.entries:
    entry.status = "captured"; entry.delay = 0
save_project(window.project, window.project_dir); window._refresh_all(); app.processEvents()
quick, full = window.mode_cards
assert full.selected and window.epochs.value() == 200
quick.clicked.emit(); assert window.epochs.value() == 1 and quick.selected
full.clicked.emit(); assert window.epochs.value() == 200
window.epochs.setValue(7); assert not quick.selected and not full.selected

# No visible main-path text says "epoch".
expert = window.train_expert
page = window.pages.currentWidget()
texts = [w.text() for w in page.findChildren(QLabel) + page.findChildren(QPushButton)
         if w.isVisible() and not expert.isAncestorOf(w)]
assert not [t for t in texts if "epoch" in t.lower()], [t for t in texts if "epoch" in t.lower()]

# Start training runs the check first; a passing check starts training.
started = []
window._start = lambda command: started.append(command) or setattr(window, "command", command)
window.train_button.click()
assert started == ["check"] and window._train_after_check
window._after_job("check", 0, "Ready for training.\n")
assert started == ["check", "train"], started

# A failing check stops and explains.
started.clear(); window.train_button.click()
window._after_job("check", 1, "x\nERROR: Missing take 3\n")
assert started == ["check"] and window.train_alert.isVisible() and "Missing take 3" in window.train_alert.body_text()
assert window.train_alert_go_record.isVisible()

# A failing training offers CPU.
window._after_job("train", 1, "RuntimeError: MPS backend out of memory\n")
assert window.train_alert.isVisible() and window.retry_button.isVisible()
assert "graphics memory" in window.train_alert.body_text()
# An ordinary failure on Apple Silicon is not called a memory problem.
fallback = "UserWarning: The operator is not currently supported on the MPS backend and will fall back to run on the CPU.\n"
window._after_job("train", 1, fallback + "ValueError: bad config\n")
assert "graphics memory" not in window.train_alert.body_text(), window.train_alert.body_text()

# Live chart from the log, one series per size.
window._handle_log_text("Epoch 1/200 started\nEpoch 1 finished. standard: ESR=0.5, MSE=0.1\nEpoch 2 finished. standard: ESR=0.2\n")
assert len(window.training_chart.points("standard")) == 2
window.train_running.show(); app.processEvents()
for value in (window.train_percent, window.train_time_left, window.train_rounds):
    assert value.width() >= value.fontMetrics().horizontalAdvance(value.text()), (value.text(), value.width())
assert window.status_label.text() == "" or "Connect" not in window.status_label.text()
window._handle_log_text("Epoch 201 finished. nano: ESR=0.4\n")
assert window.training_chart.current_tier == "nano" and "Nano" in window.train_stage_title.text()

# Success: the model is ready, Next: Listen is the one filled button, Train again is an outline.
run = window.project_dir / "outputs" / "r1"; run.mkdir(parents=True)
(run / "manifest.json").write_text("{}"); (run / "model_parametric.nam").write_text("{}")

(run / "playback").mkdir(exist_ok=True)
(run / "playback/model_playback.nam").write_text("{}")
(run / "playback/qualification.json").write_text(json.dumps({"passed": True, "model_sha256": hashlib.sha256((run / "playback/model_playback.nam").read_bytes()).hexdigest()}))
window._refresh_runs(); window._after_job("train", 0, ""); app.processEvents()
assert "Training finished" in window.status_label.text()
primaries = [b for b in window.findChildren(QPushButton) if b.property("primary") and b.isVisible()]
assert primaries == [window.train_continue], [b.text() for b in primaries]
assert window.train_button.text() == "Train again" and window.train_button.property("outline")
print("OK")
"""


def test_train_page():
    run_gui(TRAIN_SCRIPT)
