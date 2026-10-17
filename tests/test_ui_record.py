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
