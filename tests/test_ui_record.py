from gui_harness import run_gui

CHOOSE_SCRIPT = r"""
import hashlib, json, os, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, "tests")
from test_recent import make_project
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.ui import project_io
from parametric_mac.control_editor import starter
from parametric_mac.workflow import make_plan, quality_settings
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window.resize(1140, 900); window.show(); app.processEvents()
window._start_new_capture(); window.gear_next_button.click()
window.go_to_step("record"); app.processEvents()

expected = {level: len(make_plan(*quality_settings(starter(False), level)).entries) for level in (0, 2, 3)}
assert expected[2] == 40 and expected[0] == 14, expected
fast, good, maximum = window.quality_cards
assert window.record_stack.currentWidget() is window.record_choose
assert good.selected and not fast.selected and good.tag_text() == "Recommended"
for card, level in zip(window.quality_cards, (0, 2, 3)):
    assert card.number_text() == str(expected[level]), (card.title_text(), card.number_text())
assert [c.title_text() for c in window.quality_cards] == ["Fast", "Good", "Max"]

fast.clicked.emit(); app.processEvents()
assert window._quality == 0 and fast.selected and not good.selected
good.clicked.emit(); app.processEvents()
window.record_start_button.click(); app.processEvents()
assert json.loads((window.project_dir / "workflow.json").read_text())["quality"] == 2
assert window.record_stack.currentWidget() is window.record_loop
assert window.current_step() == "record"

# Review Focus 1: an old locked Overkill project shows its level, read-only.
old = make_project(Path(os.environ["PARAMETRIC_PROJECTS_ROOT"]) / "Old", 1, 40,
                   workflow={"quality": 4, "plan_locked": True, "gear_kind": "pedal", "fixed_notes": "Level at 5"})
window._open_project(old); window._refresh_level_cards(); app.processEvents()
assert all(not card.isEnabled() for card in window.quality_cards)
selected = [card for card in window.quality_cards if card.selected]
assert len(selected) == 1 and selected[0].title_text() == "Overkill", [c.title_text() for c in selected]
print("OK")
"""


def test_record_choose_level():
    run_gui(CHOOSE_SCRIPT)


def test_level_cards_do_not_stretch():
    run_gui(r"""
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show()
window.go_to_step("record"); app.processEvents()
heights = {card.height() for card in window.quality_cards}
assert len(heights) == 1 and max(heights) < 220, heights
tops = {card._number.mapTo(window, card._number.rect().topLeft()).y() for card in window.quality_cards}
assert len(tops) == 1, tops
print("OK")
""")


CHANGE_SCRIPT = r"""
import hashlib, json, tempfile, shutil
from dataclasses import replace
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
window._start_new_capture(); window.gear_next_button.click()
window.go_to_step("record"); window.record_start_button.click(); app.processEvents()
assert len(window.project.entries) == 40 and window.record_stack.currentWidget() is window.record_loop

# 1. Change the level before the first take.
assert window.change_level_link.isVisible()
window.change_level_link.click(); app.processEvents()
assert window.record_stack.currentWidget() is window.record_choose and window.record_start_button.isVisible()
window.quality_cards[0].clicked.emit(); window.record_start_button.click(); app.processEvents()
assert len(window.project.entries) == 14
assert json.loads((window.project_dir / "workflow.json").read_text())["quality"] == 0

# 2. A Gear edit before the first take drops the uncommitted plan.
window.go_to_step("gear")
controls = window.control_editor.controls
window.control_editor.commit((replace(controls[0], name="Gain"),) + controls[1:]); app.processEvents()
window.go_to_step("record"); app.processEvents()
assert window.record_stack.currentWidget() is window.record_choose
window.record_start_button.click(); app.processEvents()
names = {name for entry in window.project.entries for name in entry.params}
assert "Gain" in names and "Drive" not in names, names

# 3. After the first take, the plan is locked.
entry = window.project.entries[0]; entry.status = "captured"; entry.delay = 0
from nam.capture.project import QAModel, save_project
target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(inputs / "validation.wav", target); save_project(window.project, window.project_dir)
window._on_capture_success(QAModel(peak=-16, messages=[])); window.go_to_step("record"); app.processEvents()
assert not window.change_level_link.isVisible()
before = [dict(e.params) for e in window.project.entries]
controls = window.control_editor.controls
window.control_editor.commit((replace(controls[0], name="Drive"),) + controls[1:]); app.processEvents()
assert [dict(e.params) for e in window.project.entries] == before
print("OK")
"""


def test_record_level_can_change_until_the_first_take():
    run_gui(CHANGE_SCRIPT)


def test_changed_controls_and_size_tiers():
    from parametric_mac.ui.widgets.knobs import changed_controls, size_tier
    assert changed_controls({"Drive": 2.5, "Tone": 7}, {"Drive": 6, "Tone": 7}) == {"Drive"}
    assert changed_controls(None, {"Drive": 6, "Tone": 7}) == {"Drive", "Tone"}
    assert (size_tier(1), size_tier(2), size_tier(3), size_tier(6), size_tier(7), size_tier(24)) == (
        "large", "large", "medium", "medium", "compact", "compact")


LOOP_SCRIPT = r"""
import hashlib, shutil, tempfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np, soundfile as sf
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
from nam.capture.project import QAModel, save_project
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
window._start_new_capture(); window.gear_next_button.click()
window.wire_check.setChecked(True)
window._on_route_test_success(SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False, loopback_disagreement=False,
    crosscheck=None, peak=-9.0, latency=SimpleNamespace(delay=17, peak_delay=17.0)))
window.go_to_step("record"); window.record_start_button.click(); app.processEvents()
assert window.record_stack.currentWidget() is window.record_loop
assert not hasattr(window, "confirm_knobs")
assert window.record_button.isEnabled() and window.record_button.text() == "Record"
assert window.setting_label.text() == "SETTING 1 / 40", window.setting_label.text()
assert window.capture_continue.property("primary") and not window.capture_continue.isEnabled()

def capture_shown(qa):
    entry = window._shown_entry
    entry.status = "captured"; entry.delay = 0
    entry.qa = qa
    target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inputs / "validation.wav", target); save_project(window.project, window.project_dir)
    window._recording_entry = entry
    window._on_capture_success(qa); app.processEvents()
    return entry

# A running take turns the button into Cancel.
window._worker = object(); window._cancel_token = object(); window._sync_states()
assert window.record_button.text() == "Cancel" and window.record_button.isEnabled()
window._worker = None; window._cancel_token = None; window._sync_states()

# A clipped take: plain alert, Record again, and the new-capture link.
first = capture_shown(QAModel(peak=0.0, clipping=True, messages=["Clipping detected"]))
assert window.take_alert.isVisible() and window.take_alert.body_text().startswith("This take clipped.")
assert window.take_alert_new_capture.isVisible()
assert window.record_button.text() == "Record again" and window._shown_entry is first
assert window.setting_label.text() == "SETTING 1 / 40", window.setting_label.text()

# A good replacement clears the clipped retry and advances the setting.
capture_shown(QAModel(peak=-12.0, messages=[]))
assert not window.take_alert.isVisible() and window.record_button.text() == "Record"
assert window.setting_label.text() == "SETTING 2 / 40", window.setting_label.text()
assert "Good take" in window.last_take_label.text()

# Review Focus 6: Space only records from the visible loop, never from a text field or another page.
calls = []
window._begin_capture = lambda entry: calls.append(entry)
window.go_to_step("gear"); window.pedal_name.setFocus(); app.processEvents()
QTest.keyClick(window.pedal_name, Qt.Key_Space); app.processEvents()
window.go_to_step("train"); app.processEvents()
QTest.keyClick(window.pages.currentWidget(), Qt.Key_Space); app.processEvents()
window.go_to_step("record"); window._choose_level_again() if not window._plan_locked() else None; app.processEvents()
assert calls == [], calls
window._show_record_state(); window.go_to_step("record"); window.record_loop.setFocus(); app.processEvents()
QTest.keyClick(window.record_loop, Qt.Key_Space); app.processEvents()
assert len(calls) == 1, calls
print("OK")
"""


def test_recording_loop():
    run_gui(LOOP_SCRIPT)


WIDE_SCRIPT = r"""
import hashlib, tempfile
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
window._start_new_capture()
while len(window.control_editor.controls) < 24:
    window.control_editor.add_control()
window.gear_next_button.click(); window.go_to_step("record"); window.record_start_button.click()
window.resize(800, 680); app.processEvents()
page = window.record_stack.currentWidget()
assert page is window.record_loop
assert page.horizontalScrollBar().maximum() == 0, page.widget().size()
assert window.knob_targets.tier == "compact"
print("OK")
"""


def test_24_controls_fit_the_recording_loop():
    run_gui(WIDE_SCRIPT)


FLOW_SCRIPT = r"""
import hashlib, shutil, tempfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np, soundfile as sf
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
from nam.capture.project import QAModel, save_project
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
window._start_new_capture(); window.gear_next_button.click()
window.wire_check.setChecked(True)
window._on_route_test_success(SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False, loopback_disagreement=False,
    crosscheck=None, peak=-9.0, latency=SimpleNamespace(delay=17, peak_delay=17.0)))
window.go_to_step("record"); app.processEvents()
calls = []
real_begin = window._begin_capture
window._begin_capture = lambda entry: calls.append(entry)

# Review Focus 6 on the choose state: a spin box and a focused card take Space; nothing records.
window.plan_advanced_toggle.setChecked(True); app.processEvents()
window.n_train_spin.setFocus(); QTest.keyClick(window.n_train_spin, Qt.Key_Space)
fast = window.quality_cards[0]
fast.setFocus(); QTest.keyClick(fast, Qt.Key_Space); app.processEvents()
assert fast.selected and calls == [], (fast.selected, calls)
window.quality_cards[1].clicked.emit()

# Item 1: the real flow. Start recording with a click, then Space records the shown setting.
window.record_start_button.setFocus(); window.record_start_button.click(); app.processEvents()
assert window.current_step() == "record" and window.record_stack.currentWidget() is window.record_loop
QTest.keyClick(QApplication.focusWidget(), Qt.Key_Space); app.processEvents()
assert len(calls) == 1 and window.current_step() == "record", (calls, window.current_step())
window._begin_capture = real_begin

def capture_shown(qa):
    entry = window._shown_entry
    entry.status = "captured"; entry.delay = 0
    target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inputs / "validation.wav", target); save_project(window.project, window.project_dir)
    window._recording_entry = entry
    window._on_capture_success(qa); app.processEvents()
    return entry

# Item 2: a warning take can be kept.
capture_shown(QAModel(peak=-12.0, messages=["Delay disagreement between loopback and return"]))
assert window.record_button.text() == "Record again" and window.take_alert_keep.isVisible()
assert not window.take_alert_new_capture.isVisible()
window.take_alert_keep.click(); app.processEvents()
assert window.record_button.text() == "Record" and window.setting_label.text() == "SETTING 2 / 40", window.setting_label.text()
assert not window.knob_targets.changed or window.knob_targets.changed != frozenset(window._shown_entry.params)

# Done state.
for entry in window.project.entries:
    entry.status = "captured"; entry.delay = 0
save_project(window.project, window.project_dir)
window._refresh_all(); app.processEvents()
assert window.record_title.text() == "All 40 takes are saved.", window.record_title.text()
assert window.capture_continue.isEnabled() and window.capture_hint.text() == ""
print("OK")
"""


def test_recording_flow_space_warning_and_done():
    run_gui(FLOW_SCRIPT)
