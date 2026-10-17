from gui_harness import run_gui

START_SCRIPT = r"""
import os, sys
from pathlib import Path
sys.path.insert(0, "tests")
from test_recent import make_project
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.recent import RECENT_KEY, dump_recent, parse_recent, remember
from parametric_mac.ui.style import settings_from_env
root = Path(os.environ["PARAMETRIC_PROJECTS_ROOT"])
good = make_project(root / "Rat", 3, 5)
corrupt = root / "Broken"; corrupt.mkdir(); (corrupt / "capture_project.json").write_text("{not json")
items = ()
for i, (path, name) in enumerate(((root / "Gone", "Gone"), (corrupt, "Broken"), (good, "Rat"))):
    items = remember(items, path, name, now=float(i))
settings = settings_from_env(); settings.setValue(RECENT_KEY, dump_recent(items)); settings.sync()

from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show(); app.processEvents()
assert window.current_step() == "start", window.current_step()
rows = {row.name: row for row in window.recent_rows}
assert list(rows) == ["Rat", "Broken", "Gone"], list(rows)
assert rows["Rat"].action.text() == "Continue" and rows["Rat"].remove_button is None
assert "3 of 5" in rows["Rat"].detail.text()
assert rows["Broken"].detail.text() == "Cannot read this project" and rows["Broken"].action is None
assert rows["Gone"].detail.text() == "Folder not found" and rows["Gone"].remove_button is not None

rows["Gone"].remove_button.click(); app.processEvents()
assert [row.name for row in window.recent_rows] == ["Rat", "Broken"]
assert [r.name for r in parse_recent(settings_from_env().value(RECENT_KEY))] == ["Rat", "Broken"]

# Continue opens the project on Connect (a reopened project needs a new level check).
[row for row in window.recent_rows if row.name == "Rat"][0].action.click(); app.processEvents()
assert window.project_dir == good.resolve() or window.project_dir == good, window.project_dir
assert window.current_step() == "connect", window.current_step()
assert parse_recent(settings_from_env().value(RECENT_KEY))[0].name == "Rat"
print("OK")
"""


def test_start_lists_recent_projects_with_safe_states():
    run_gui(START_SCRIPT)


GUARD_SCRIPT = r"""
import os, sys
from pathlib import Path
sys.path.insert(0, "tests")
from test_recent import make_project, add_run
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.recent import RECENT_KEY, dump_recent, remember
from parametric_mac.ui.style import settings_from_env
root = Path(os.environ["PARAMETRIC_PROJECTS_ROOT"])
first = make_project(root / "First", 5, 5)
second = make_project(root / "Second", 5, 5)
items = remember(remember((), second, "Second", 1.0), first, "First", 2.0)
for i in range(10):
    items = remember(items, root / f"gone {i}", f"Gone {i}", float(i) - 20)
settings = settings_from_env(); settings.setValue(RECENT_KEY, dump_recent(items)); settings.sync()
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show(); app.processEvents()

# Statuses are read again each time Start shows (fake takes have no audio, so do not open the project).
assert [row.action.text() for row in window.recent_rows if row.name == "First"] == ["Recorded"]
add_run(first, "r1", "exported", True)
window.go_to_step("train"); window.go_to_step("start"); app.processEvents()
assert [row.action.text() for row in window.recent_rows if row.name == "First"] == ["Ready"]

# Twelve rows scroll at 800x680 instead of clipping.
window.resize(800, 680); app.processEvents()
assert len(window.recent_rows) == 12
assert window.recent_scroll.verticalScrollBar().maximum() > 0

# No project switch while a job runs.
job = QProcess(); job.start(sys.executable, ["-c", "import time; time.sleep(5)"]); assert job.waitForStarted(5000)
window.process = job
window._sync_states(); app.processEvents()
assert all(not row.action.isEnabled() for row in window.recent_rows if row.action), "rows must be disabled"
before = window.project_dir
window._open_recent(second); app.processEvents()
assert window.project_dir == before, window.project_dir
job.kill(); job.waitForFinished(3000); window.process = None
print("OK")
"""


def test_start_refreshes_scrolls_and_blocks_switching_during_jobs():
    run_gui(GUARD_SCRIPT)
