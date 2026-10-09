"""Native Qt integration in an isolated process, like the shipped launcher."""
import os
import subprocess
import sys
from test_workflow import project

SCRIPT = '''
import sys, hashlib, shutil
from types import SimpleNamespace
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from nam.capture.project import save_project, QAModel
from parametric_mac import gui
from parametric_mac.gui import MacWindow
app = QApplication([])
window = MacWindow()
window.show()
app.processEvents()
assert window.pages.count() == 5
assert not window.train_button.isEnabled()
assert not window.capture_next_button.isEnabled()
assert window.quality_slider.value() == 2
assert window.effort_label.text().startswith('40 recordings')
window.project_dir = Path(sys.argv[1])
window.go_to(3)
window._start('check')
assert window.process is not None
assert not window.train_button.isEnabled()
assert not window.new_button.isEnabled()
window.go_to(4)
assert window.pages.currentIndex() == 4
assert all(b.isEnabled() for b in window.nav_buttons)
for _ in range(400):
    if window.process is None:
        break
    QTest.qWait(50)
assert window.process is None, window.train_log.toPlainText()
assert 'Ready for training.' in window.train_log.toPlainText()
assert window.train_button.isEnabled()
assert window.new_button.isEnabled()
assert not window.stop_button.isEnabled()
# Creating a native manifest automatically copies verified excitation files.
root = Path(sys.argv[1])
assets = root / 'assets'
assets.mkdir()
for name in ('inputTrunc.wav', 'validation.wav'):
    shutil.copy2(root / 'input.wav', assets / name)
gui.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir()}
fresh = root / 'native-project'
fresh.mkdir()
window._create_project(fresh, assets)
assert (fresh / 'input_train.wav').is_file()
window.quality_slider.setValue(0)
assert window.n_train_spin.value() == 8
assert window.knob_table.item(0, 3).text() == '2.0'
window._commit_plan()
assert len(window.project.entries) == 14  # an LHS setting already covers a boundary
assert window.pages.currentIndex() == 2
assert not window.capture_next_button.isEnabled()  # no route proof
assert not window.loopback_check.isChecked()
# A known route-test result allows recording only after setup confirmations;
# invalidating the setup removes readiness. No audio hardware is driven here.
for check in (window.reamp_check, window.monitor_check, window.level_check):
    check.setChecked(True)
route = SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False,
    loopback_disagreement=False, crosscheck=None, peak=-16,
    latency=SimpleNamespace(delay=17, peak_delay=17.0))
window._on_route_test_success(route)
assert window._route_ready()
window.monitor_check.setChecked(False)
assert not window._route_ready()
window.monitor_check.setChecked(True)
window.confirm_knobs.setChecked(True)
window.target_label.setText('A different selected setting')
window._begin_capture(window.project.entries[0])
assert window._worker is None
assert not window.confirm_knobs.isChecked()  # cannot mislabel a pending take
# Manual sampling is visibly custom; the slider restores complete defaults.
window.n_train_spin.setValue(9)
assert window.quality_name.text() == 'Custom capture plan'
window.quality_slider.setValue(2)
assert window.n_train_spin.value() == 30
window._commit_plan()
assert len(window.project.entries) == 40
entry = window.project.entries[0]
entry.status = 'captured'
entry.delay = 0
path = fresh / entry.y_path
path.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(root / 'input.wav', path)
save_project(window.project, fresh)
window._on_capture_success(QAModel(peak=-16, messages=[]))
assert not window.quality_slider.isEnabled()
assert not window.plan_advanced.isEnabled()
assert not window.separate_button.isHidden()
labels = [(e.params, e.y_path) for e in window.project.entries]
window._open_project(fresh)
assert [(e.params, e.y_path) for e in window.project.entries] == labels
assert not window.quality_slider.isEnabled()
assert window._quality == 2
assert window._workflow['plan_locked']
window.epochs.setValue(7)
assert '7 epochs' in window.training_mode.currentText()
window.training_mode.setCurrentIndex(1)
assert window.epochs.value() == 1
# Opening a run shows its saved metrics and remembers listening per run.
run = fresh / 'outputs' / 'example-run'
run.mkdir(parents=True)
(run / 'manifest.json').write_text('{}')
(run / 'status.json').write_text('{"status":"exported"}')
(run / 'model_parametric.nam').write_text('{}')
(run / 'metrics.json').write_text('{"epoch":2,"ESR":0.031}')
window.go_to(4)
assert '0.031' in window.review_metric.text()
assert window.save_model_button.isEnabled()
window.review_check.setChecked(True)
assert (run / 'review.json').is_file()
window._refresh_runs()
assert window.review_check.isChecked()
# New project cannot overwrite existing captures, even via the private entry point.
try:
    window._create_project(fresh, assets)
    raise AssertionError('existing folder overwritten')
except ValueError:
    pass
assert path.is_file()
window.close()
app.processEvents()
print('GUI workflow check passed')
'''


def test_gui_workflow_and_job_controls(project):
    result = subprocess.run([sys.executable, '-c', SCRIPT, str(project)],
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'GUI workflow check passed' in result.stdout
