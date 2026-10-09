"""Run native Qt integration in an isolated process, like the shipped launcher."""
import os
import subprocess
import sys
from test_workflow import project  # shared synthetic capture fixture

SCRIPT = '''
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from parametric_mac.gui import MacWindow
app = QApplication([])
window = MacWindow()
window.project_dir = Path(sys.argv[1])
window.centralWidget().setCurrentIndex(window.train_tab)
window._start('check')
assert window.process is not None
assert not window.train_button.isEnabled()
for _ in range(200):
    if window.process is None:
        break
    QTest.qWait(50)
assert window.process is None, window.train_log.toPlainText()
assert 'Ready for training.' in window.train_log.toPlainText()
assert window.train_button.isEnabled()
assert not window.stop_button.isEnabled()
assert all(window.centralWidget().isTabEnabled(i) for i in range(window.centralWidget().count()))
window.close()
app.processEvents()
print('GUI subprocess check passed')
'''


def test_gui_check_process_and_controls(project):
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
    result = subprocess.run([sys.executable, '-c', SCRIPT, str(project)], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'GUI subprocess check passed' in result.stdout
