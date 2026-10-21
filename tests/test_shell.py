from gui_harness import run_gui

SHELL_SCRIPT = r"""
import sys
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QPushButton
app = QApplication([])
from parametric_mac.gui import MacWindow
from parametric_mac.ui.shell import STEPS, StepBar
from parametric_mac.ui.tokens import DARK, LIGHT
window = MacWindow()
window.resize(1140, 900)
window.show()
app.processEvents()
keys = [s.key for s in STEPS]
assert window.pages.count() == len(STEPS), (window.pages.count(), len(STEPS))
assert window.current_step() == "start", window.current_step()

# Keyed navigation.
window.go_to_step("train")
assert window.current_step() == "train"
assert window.pages.currentIndex() == keys.index("train")

# Before a project exists, only Start and the first numbered step are enabled.
bar = window.findChild(StepBar)
numbered = [s.key for s in STEPS if s.numbered]
enabled = {k for k in numbered if bar.button(k).isEnabled()}
assert enabled == {numbered[0]}, enabled
seen = []
bar.selected.connect(seen.append)
bar.button(numbered[0]).click()
app.processEvents()
assert seen == [numbered[0]] and window.current_step() == numbered[0], (seen, window.current_step())

# Exactly one visible filled button on every page.
for key in keys:
    window.go_to_step(key)
    app.processEvents()
    primaries = [b for b in window.findChildren(QPushButton) if b.property("primary") and b.isVisible()]
    assert len(primaries) == 1, (key, [b.text() for b in primaries])

# Appearance menu and View menu share three exclusive actions.
menu_actions = window.appearance_actions
assert [a.text() for a in menu_actions] == ["Match macOS", "Light", "Dark"]
assert all(a.isCheckable() for a in menu_actions)
view_menu = [m for m in window.menuBar().actions() if m.text() == "View"][0].menu()
appearance_menu = [a for a in view_menu.actions() if a.text() == "Appearance"][0].menu()
assert appearance_menu.actions() == menu_actions
menu_actions[1].trigger()
assert LIGHT.bg in app.styleSheet() and menu_actions[1].isChecked() and not menu_actions[2].isChecked()
assert window.statusBar().isHidden()

# Review Focus 4: an appearance change keeps the page, the job and the form values.
job = QProcess()
job.start(sys.executable, ["-c", "import time; time.sleep(5)"])
assert job.waitForStarted(5000)
window.process = job
window.go_to_step("train")
window.pedal_name.setText("Klon-style drive")
window.appearance.set_choice("dark")
window.appearance.set_choice("light")
app.processEvents()
assert window.current_step() == "train"
assert window.process is job and job.state() == QProcess.Running
assert window.pedal_name.text() == "Klon-style drive"
job.kill(); job.waitForFinished(3000)
window.process = None
print("OK")
"""


def test_shell_navigation_primary_buttons_and_appearance():
    run_gui(SHELL_SCRIPT)


def test_top_bar_brand_and_project_name_are_visible():
    run_gui(r"""
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show(); app.processEvents()
title = window.top_bar.project_title
assert title.isVisible() and title.width() >= title.fontMetrics().horizontalAdvance(title.text()), (title.width(), title.text())
brand = window.top_bar.brand_button
assert brand.isVisible() and brand.width() >= brand.fontMetrics().horizontalAdvance("Parametric"), brand.width()
print("OK")
""")


def test_start_is_reachable_and_file_menu_works():
    run_gui(r"""
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show(); app.processEvents()
window.go_to_step("train")
window.top_bar.brand_button.click()
assert window.current_step() == "start", window.current_step()
calls = []
window._on_open_project = lambda: calls.append("open")
window._start_new_capture = lambda: calls.append("new")
file_menu = [m for m in window.menuBar().actions() if m.text() == "File"][0].menu()
actions = {a.text(): a for a in file_menu.actions()}
assert actions["Open folder…"].shortcut() == QKeySequence(QKeySequence.Open)
assert actions["New capture…"].shortcut() == QKeySequence(QKeySequence.New)
actions["Open folder…"].trigger(); actions["New capture…"].trigger()
assert calls == ["open", "new"], calls
assert actions["Open folder…"] in window._mutating and actions["New capture…"] in window._mutating
window.statusBar().showMessage("Active-learning round finished.")
assert window.footer.status.text() == "Active-learning round finished.", window.footer.status.text()
print("OK")
""")


def test_window_shrinks_to_800_with_a_long_project_name():
    run_gui(r"""
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show(); app.processEvents()
window.top_bar.set_project_title("A very long project name " * 5)
window.resize(800, 680); app.processEvents()
assert window.width() == 800, window.width()
bar = window.top_bar
assert bar.minimumSizeHint().width() <= 800, bar.minimumSizeHint().width()
assert bar.appearance_button.geometry().right() <= bar.width(), (bar.appearance_button.geometry(), bar.width())
assert window.top_bar.project_title.toolTip().startswith("A very long project name")
print("OK")
""")
