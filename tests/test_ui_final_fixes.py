"""Regression tests for the final whole-branch review findings."""
from gui_harness import run_gui

SETUP = r"""
import hashlib, json, os, sys, tempfile, shutil
from pathlib import Path
from types import SimpleNamespace
import numpy as np, soundfile as sf
sys.path.insert(0, "tests")
from test_recent import make_project
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
import nam.capture.gui.main as upstream
for method in ("warning", "critical", "information"):
    setattr(upstream._QMessageBox, method, staticmethod(lambda *a, **k: None))
from nam.capture.project import save_project
from parametric_mac.ui import project_io
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window._has_device = lambda: True; window._device_sample_rate = lambda: 48000
window._current_sample_rate_warnings = lambda: []
window.resize(1140, 900); window.show(); app.processEvents()
root = Path(os.environ["PARAMETRIC_PROJECTS_ROOT"])
ROUTE = SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False, loopback_disagreement=False,
                        crosscheck=None, peak=-9.0, latency=SimpleNamespace(delay=17, peak_delay=17.0))
"""

CHOOSING = SETUP + r"""
window._start_new_capture(); window.gear_next_button.click()
window.go_to_step("record"); window.record_start_button.click(); window.change_level_link.click(); app.processEvents()
locked = make_project(root / "Locked", 3, 14, {"quality": 0, "plan_locked": True, "gear_kind": "pedal", "fixed_notes": "Level at 5"})
window._open_project(locked); window.go_to_step("record"); app.processEvents()
window.record_start_button.click(); app.processEvents()
assert window.record_stack.currentWidget() is window.record_loop, "a locked project must reach the recording loop"
print("OK")
"""

FAILED_OPEN = SETUP + r"""
window._start_new_capture(); window.gear_next_button.click(); app.processEvents()
# Bad draft controls are unsaved edits: the project still opens, with its saved knobs.
bad = make_project(root / "Bad", 0, 14, {"draft_controls": [{"bogus": 1}]})
window._open_recent(bad); app.processEvents()
assert window.project_dir == bad and window._applying is False
assert [c.name for c in window.control_editor.controls] == ["Drive", "Tone"]
assert "draft controls" in window.capture_log.toPlainText().lower()
# Odd workflow values fall back to defaults.
odd = make_project(root / "Odd", 0, 14, {"fixed_notes": 5, "quality": "x", "gear_kind": 3})
window._open_recent(odd); app.processEvents()
assert window.project_dir == odd and window.fixed_notes.text() == "", (window.project_dir, window.fixed_notes.text())

# A failure after the window starts changing ends with no project open, and nothing is written.
good = make_project(root / "Good", 0, 14)
before = (good / "capture_project.json").read_bytes()
real = window._recover_and_reconcile
def boom():
    raise RuntimeError("boom")
window._recover_and_reconcile = boom
window._open_recent(good); app.processEvents()
assert window.project_dir is None and window._applying is False, window.project_dir
assert "Could not open Good: boom" in window.footer.status.text(), window.footer.status.text()
window._sync_states(); app.processEvents()
assert "Could not open Good" in window.footer.status.text(), "the message must survive the next sync"
window.control_editor.add_control(); app.processEvents()
assert (good / "capture_project.json").read_bytes() == before, "a failed open must never write into that project"
# A later successful open clears the message.
window._recover_and_reconcile = real
window._open_recent(good); app.processEvents()
assert window.project_dir == good and "Could not open" not in window.footer.status.text()

# Settings from "Try again on CPU" do not follow the user into the next project.
window.device.setCurrentIndex(window.device.findData("cpu")); window.batch.setValue(1)
window._start_new_capture(); app.processEvents()
assert window.device.currentData() == "auto" and window.batch.value() == 4
print("OK")
"""


SAVED_TAKE = SETUP + r"""
window._start_new_capture(); window.gear_next_button.click()
window.wire_check.setChecked(True); window._on_route_test_success(ROUTE)
window.go_to_step("record"); window.record_start_button.click(); app.processEvents()
entry = window._shown_entry
entry.status, entry.delay = "captured", 0
target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(inputs / "validation.wav", target); save_project(window.project, window.project_dir)
window._refresh_all(); app.processEvents()
row = next(i for i, e in enumerate(window._displayed_entries) if e.status == "captured")
window.capture_table.selectRow(row); app.processEvents()
assert window._shown_entry.status == "captured"
assert window.record_button.text() == "Record again", window.record_button.text()
assert "replace" in window.capture_feedback.text().lower(), window.capture_feedback.text()

# Space with focus on a control inside the loop acts on that control, never records.
calls = []
window._begin_capture = lambda e: calls.append(e)
for widget in (window.capture_table, window.clear_captures_button):
    widget.setFocus(); app.processEvents()
    QTest.keyClick(widget, Qt.Key_Space); app.processEvents()
assert calls == [], calls
window.record_loop.setFocus(); QTest.keyClick(window.record_loop, Qt.Key_Space); app.processEvents()
assert len(calls) == 1
# After "Keep this take and continue", Space records again (focus returns to the loop).
from nam.capture.project import QAModel
window._begin_capture = lambda e: calls.append(e)
window._capture_table_clear = None
window.capture_table.clearSelection(); window._retry_entry = None; window._show_next_target()
shown = window._shown_entry
shown.status, shown.delay = "captured", 0
target = window.project_dir / shown.y_path; target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(inputs / "validation.wav", target); save_project(window.project, window.project_dir)
window._recording_entry = shown
window._on_capture_success(QAModel(peak=-12.0, messages=["Delay disagreement"])); app.processEvents()
window.take_alert_keep.setFocus(); window.take_alert_keep.click(); app.processEvents()
QTest.keyClick(QApplication.focusWidget(), Qt.Key_Space); app.processEvents()
assert len(calls) == 2, calls
print("OK")
"""


def test_choosing_state_does_not_leak_into_the_next_project():
    run_gui(CHOOSING)


def test_failed_open_leaves_no_half_open_project():
    run_gui(FAILED_OPEN)


def test_saved_take_is_labelled_and_space_respects_focus():
    run_gui(SAVED_TAKE)
