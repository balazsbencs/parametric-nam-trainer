from gui_harness import run_gui

LISTEN_SCRIPT = r"""
import hashlib, json, os, tempfile, time
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
app = QApplication([])
from parametric_mac.ui import project_io
from parametric_mac.ui.copy import CHECKPOINT_NOTE
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
from parametric_mac.ui.shell import STEPS
assert [s.key for s in STEPS] == ["start", "gear", "connect", "record", "train", "listen"]
window = MacWindow(); window._inputs_dir = inputs
window.resize(1140, 900); window.show(); app.processEvents()
window._start_new_capture(); window.pedal_name.setText("Klon-style drive"); window.pedal_name.editingFinished.emit()
window.gear_next_button.click(); window.go_to_step("record"); window.record_start_button.click()

def make_run(name, model, age):
    run = window.project_dir / "outputs" / name; run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    (run / "status.json").write_text(json.dumps({"status": "exported" if model else "failed_or_interrupted"}))
    (run / "metrics.json").write_text('{"epoch": 2, "ESR": 0.031}')
    if model:
        (run / "model_parametric.nam").write_text("{}")

        (run / "playback").mkdir(exist_ok=True)
        (run / "playback/model_playback.nam").write_text("{}")
        (run / "playback/qualification.json").write_text(json.dumps({"passed": True, "model_sha256": hashlib.sha256((run / "playback/model_playback.nam").read_bytes()).hexdigest()}))
    stamp = time.time() - age
    os.utime(run / "manifest.json", (stamp, stamp))
    return run

old = make_run("old", True, 200)
good = make_run("good", True, 100)
make_run("failed", False, 0)
window.go_to_step("listen"); app.processEvents()
assert window._exported_run() == good, window._exported_run()
assert window.model_card.isVisible() and window.model_file_label.text() == "Klon-style drive.nam"
assert window.save_model_button.isEnabled() and window.save_model_button.isVisible()
assert window.test_table.rowCount() == len(window.project.entries_for_split("validation"))
assert window.test_table.item(0, window.test_table.columnCount() - 1).text() == "—"
badge = [l for l in window.model_card.findChildren(QLabel) if l.text() == ".nam"][0]
assert badge.width() >= badge.fontMetrics().horizontalAdvance(".nam"), badge.width()
assert len(window.earlier_rows) == 3
visible = [w.text() for w in window.pages.currentWidget().findChildren(QLabel) if w.isVisible()]
assert not [t for t in visible if "never heard" in t.lower()]
assert CHECKPOINT_NOTE in window.listen_expert_text()

first, second = window.listen_checks
first.setChecked(True)
assert json.loads((good / "review.json").read_text()) == {"listened": False, "checks": [True, False]}
second.setChecked(True)
assert json.loads((good / "review.json").read_text()) == {"listened": True, "checks": [True, True]}

# An old review.json without checks shows both on.
(old / "review.json").write_text('{"listened": true}')
window._select_run(old); app.processEvents()
assert window._exported_run() == old and all(c.isChecked() for c in window.listen_checks)
print("OK")
"""


def test_listen_page():
    run_gui(LISTEN_SCRIPT)


RUNS_SCRIPT = r"""
import hashlib, json, os, tempfile, time
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.ui import project_io
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window.resize(1140, 900); window.show(); app.processEvents()
window._start_new_capture(); window._use_starter(True)
window.pedal_name.setText("Fuzz/Face"); window.pedal_name.editingFinished.emit()
window.gear_next_button.click(); window.go_to_step("record"); window.record_start_button.click()

def make_run(name, model, age, architecture="a2-nano"):
    run = window.project_dir / "outputs" / name; run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"model_architecture": architecture}))
    (run / "status.json").write_text(json.dumps({"status": "exported" if model else "failed_or_interrupted"}))
    if model:
        (run / "model_parametric.nam").write_text("{}")

        (run / "playback").mkdir(exist_ok=True)
        (run / "playback/model_playback.nam").write_text("{}")
        (run / "playback/qualification.json").write_text(json.dumps({"passed": True, "model_sha256": hashlib.sha256((run / "playback/model_playback.nam").read_bytes()).hexdigest()}))
    stamp = time.time() - age
    os.utime(run / "manifest.json", (stamp, stamp))
    return run

old = make_run("old", True, 300)
window.go_to_step("listen"); app.processEvents()
assert window._exported_run() == old

# The card names the run's own model type, not the current Expert choice.
window.model_architecture.setCurrentIndex(window.model_architecture.findData("a2-standard")); window._show_run()
assert "Nano" in window.model_details.text() and "Standard" not in window.model_details.text(), window.model_details.text()

# A failed newer run keeps the good model shown.
failed = make_run("failed", False, 100)
window.command, window._job_output, window._run_folder = "train", "x", failed
window._finished(1, None); app.processEvents()
assert window._exported_run() == old and window.listen_title.text() == "Your model is ready"
# A successful newer run is shown.
new = make_run("new", True, 0)
window.command, window._job_output, window._run_folder = "train", "", None
window._finished(0, None); app.processEvents()
assert window._exported_run() == new

# Earlier models use plain words; the save name is a safe file name.
texts = [row.text() for row in window.earlier_rows]
assert any("Model ready" in t for t in texts) and any("Did not finish" in t for t in texts), texts
assert window._default_model_name() == "Fuzz-Face.nam"

# Switch positions show their names in the test table.
names = [window.test_table.horizontalHeaderItem(c).text() for c in range(window.test_table.columnCount())]
column = names.index("Bright")
values = {window.test_table.item(r, column).text() for r in range(window.test_table.rowCount())}
assert values <= {"Off", "On"} and values, values
print("OK")
"""


def test_listen_runs_types_and_names():
    run_gui(RUNS_SCRIPT)


def test_rebased_playback_job_arguments_and_project_reset():
    run_gui(LISTEN_SCRIPT.replace('print("OK")', r'''
from unittest.mock import patch
from PySide6.QtCore import QProcess
calls = []
with patch.object(QProcess, "start", lambda process, executable, args: calls.append(args)):
    window.playback_pad.setValue(12)
    window.playback_confirm.setChecked(True)
    window._start("qualify")
    assert calls[-1] == ["-m", "parametric_mac", "qualify", str(old), "--input-pad-db", "12.0"], calls
    assert window._busy() and not window.playback_pad.isEnabled() and not window.qualify_button.isEnabled()
    window._reset_process()
    for entry in window.project.entries:
        entry.status = "captured"
    window._start("train")
    assert calls[-1][-2:] == ["--input-pad-db", "12.0"], calls
    window._reset_process()
window._start_new_capture()
assert window.playback_pad.value() == 0 and not window.playback_confirm.isChecked()
print("OK")
'''))
