from gui_harness import run_gui

GEAR_SCRIPT = r"""
import hashlib, os, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication, QLabel
app = QApplication([])
from parametric_mac.ui import project_io
from parametric_mac.recent import projects_root
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window.resize(1140, 900); window.show(); app.processEvents()

# Start → New capture opens Gear with the pedal starter.
window.new_button.click(); app.processEvents()
assert window.current_step() == "gear", window.current_step()
assert window.gear_kind.currentText() == "Pedal"
assert [c.name for c in window.control_editor.controls] == ["Drive", "Tone"]
assert window.effort_label.text().startswith("~40 recordings"), window.effort_label.text()
expected = str(projects_root() / "My pedal")
assert window.gear_folder_label.full_text() == "Saved in " + expected, window.gear_folder_label.full_text()

# Pedal / Amp swaps only an untouched starter.
window.gear_kind.setCurrentIndex(1); app.processEvents()
assert len(window.control_editor.controls) == 7 and window.gear_kind.currentText() == "Amp"
window.control_editor.add_control(); app.processEvents()
window.gear_kind.setCurrentIndex(0); app.processEvents()
assert len(window.control_editor.controls) == 8 and window.gear_kind.currentText() == "Pedal"
from parametric_mac.control_editor import starter
window.control_editor.set_controls(starter(False))
window.control_editor.changed.emit(); app.processEvents()

# "Change" refuses a non-empty folder and keeps the old path.
busy = Path(tempfile.mkdtemp()); (busy / "x.txt").write_text("x")
window._ask_gear_folder = lambda: str(busy)
window.gear_change_link.click(); app.processEvents()
assert window.gear_error.text() == "Choose an empty folder." and window.gear_error.isVisible()
assert window.gear_folder_label.full_text() == "Saved in " + expected

# Next creates the folder and goes to Connect.
window.pedal_name.setText("Klon/Clone"); window.pedal_name.editingFinished.emit()
window.gear_next_button.click(); app.processEvents()
assert window.current_step() == "connect", window.current_step()
first = window.project_dir
assert first == projects_root() / "Klon-Clone" and (first / "capture_project.json").is_file(), first

# Locked gear: inputs disabled, note visible, and a new capture copies the gear.
window._workflow["plan_locked"] = True; window._sync_states(); window.go_to_step("gear"); app.processEvents()
assert not window.control_editor.isEnabled() and not window.pedal_name.isEnabled()
assert window.gear_lock_note.isVisible() and "Locked after the first take" in window.gear_lock_note.text()
before = (first / "capture_project.json").read_bytes()
window.fixed_notes.setText("Level at 7")
window._new_capture_from_gear(); app.processEvents()
assert window.project_dir != first and window.project_dir.parent == projects_root(), window.project_dir
assert [c.name for c in window.control_editor.controls] == ["Drive", "Tone"]
assert window.fixed_notes.text() == "Level at 7"
assert (first / "capture_project.json").read_bytes() == before
assert window.current_step() == "connect"

# Review Focus 3: 24 controls fit at 800x680 without horizontal scrolling.
window.new_button.click(); app.processEvents()
while len(window.control_editor.controls) < 24:
    window.control_editor.add_control()
window.resize(800, 680); window.go_to_step("gear"); app.processEvents()
page = window.pages.currentWidget()
assert page.horizontalScrollBar().maximum() == 0, page.widget().size()
print("OK")
"""


def test_gear_page_flow():
    run_gui(GEAR_SCRIPT)


def test_tile_area_has_no_empty_space():
    run_gui(r"""
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
from parametric_mac.control_editor import TILE_HEIGHT
window = MacWindow(); window.resize(1140, 760); window.show()
window._start_new_capture(); app.processEvents()
editor = window.control_editor
assert editor.height() <= TILE_HEIGHT + 4, editor.height()
print("OK")
""")


RESET_SCRIPT = r"""
import hashlib, json, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.ui import project_io
from parametric_mac.recent import projects_root
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show(); app.processEvents()

# A failed Next leaves no empty folder behind.
window._inputs_dir = Path(tempfile.mkdtemp())
window._start_new_capture(); window.gear_next_button.click(); app.processEvents()
assert window.gear_error.isVisible() and window.project_dir is None
assert not (projects_root() / "My pedal").exists()

# A new capture does not inherit the old level or the old model.
window._inputs_dir = inputs
window.gear_next_button.click(); app.processEvents()
first = window.project_dir
window._apply_quality(4)
run = first / "outputs" / "r1"; run.mkdir(parents=True)
(run / "manifest.json").write_text("{}"); (run / "model_parametric.nam").write_text("{}")

(run / "playback").mkdir(exist_ok=True)
(run / "playback/model_playback.nam").write_text("{}")
(run / "playback/qualification.json").write_text(json.dumps({"passed": True, "policy": {"version": 3}, "transients": {"passed": True}, "model_sha256": hashlib.sha256((run / "playback/model_playback.nam").read_bytes()).hexdigest()}))
window._refresh_runs()
assert window._exported_run() is not None
window._start_new_capture(); app.processEvents()
assert window._quality == 2, window._quality
assert window._exported_run() is None
assert "train" not in window._done_steps()

# The recovery path for a clipped take also starts at Good.
window._open_project(first); window._apply_quality(4)
window._workflow["plan_locked"] = True; window._sync_states()
window._new_capture_from_gear(); app.processEvents()
assert window.project_dir != first
assert json.loads((window.project_dir / "workflow.json").read_text())["quality"] == 2
print("OK")
"""


def test_new_capture_starts_clean():
    run_gui(RESET_SCRIPT)


def test_fixed_controls_reads_short_notes_only():
    from parametric_mac.ui.widgets.knobs import fixed_controls
    assert fixed_controls("Level at 5") == (("Level", "5"),)
    assert fixed_controls("Volume at noon") == (("Volume", "noon"),)
    assert fixed_controls("Tone at 2 o'clock") == (("Tone", "2 o'clock"),)
    assert fixed_controls("Keep unmodeled controls at their recorded positions") == ()


def test_gear_form_has_no_large_gaps():
    run_gui(r"""
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show()
window._start_new_capture(); app.processEvents()
top = window.control_editor.mapTo(window, window.control_editor.rect().topLeft()).y() - window.pedal_name.mapTo(window, window.pedal_name.rect().bottomLeft()).y()
assert top < 80, top
print("OK")
""")
