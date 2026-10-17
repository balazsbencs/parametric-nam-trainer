"""Native Qt integration in an isolated process, like the shipped launcher."""
import os
import subprocess
import sys
from test_workflow import project

SCRIPT = '''
import sys, hashlib, shutil, json
from types import SimpleNamespace
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from nam.capture.project import save_project, QAModel
from parametric_mac import gui
from parametric_mac.ui import project_io
from parametric_mac.workflow import read_state
from parametric_mac.gui import MacWindow
app = QApplication([])
window = MacWindow()
window.show()
app.processEvents()
assert window.font().family() == 'Geist'
from parametric_mac.ui.shell import STEPS
assert window.pages.count() == len(STEPS)
assert not window.train_button.isEnabled()
assert not window.capture_next_button.isEnabled()
assert window.quality_slider.value() == 2
assert window.model_architecture.currentData() == 'a2-dual'
assert window.effort_label.text().startswith('~40 recordings')
window.project_dir = Path(sys.argv[1])
# This legacy test fixture deliberately uses a short, non-A2 network.
window.model_architecture.setCurrentIndex(window.model_architecture.findData('auto'))
window.go_to_step("train")
window._start('check')
assert window.process is not None
assert not window.train_button.isEnabled()
assert not window.new_button.isEnabled()
assert not window.model_architecture.isEnabled()
window.go_to_step("review")
assert window.current_step() == "review"
assert all(b.isEnabled() for b in window.top_bar.step_bar.buttons())
for _ in range(400):
    if window.process is None:
        break
    QTest.qWait(50)
assert window.process is None, window.train_log.toPlainText()
assert 'Ready for training.' in window.train_log.toPlainText()
assert window.train_button.isEnabled()
assert window.new_button.isEnabled()
assert not window.stop_button.isEnabled()
assert window.model_architecture.isEnabled()
# Failure disclosure follows actual visibility, and the first click collapses it.
root = Path(sys.argv[1])
window.project_dir = root / 'missing-project'
window.go_to_step("train")
window._start('check')
for _ in range(400):
    if window.process is None:
        break
    QTest.qWait(50)
assert window.process is None
assert window.train_log_toggle.isChecked()
assert window.train_log.isVisible()
QTest.mouseClick(window.train_log_toggle, Qt.LeftButton)
assert not window.train_log_toggle.isChecked()
assert not window.train_log.isVisible()
window.project_dir = root
# Creating a native manifest automatically copies verified excitation files.
root = Path(sys.argv[1])
assets = root / 'assets'
assets.mkdir()
for name in ('inputTrunc.wav', 'validation.wav'):
    shutil.copy2(root / 'input.wav', assets / name)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir()}
fresh = root / 'native-project'
fresh.mkdir()
window._create_project(fresh, assets)
assert (fresh / 'input_train.wav').is_file()
window.model_architecture.setCurrentIndex(window.model_architecture.findData('a2-nano'))
assert read_state(fresh)['model_architecture'] == 'a2-nano'
window._open_project(fresh)
assert window.model_architecture.currentData() == 'a2-nano'
window.model_architecture.setCurrentIndex(window.model_architecture.findData('film-dual'))
assert '16 continuous controls' in window.architecture_hint.text()
assert 'each gets the selected number of epochs' in window.architecture_hint.text()
window._open_project(fresh)
assert window.model_architecture.currentData() == 'film-dual'
original_export = window._export_configs
window._export_configs = lambda architecture, writer: writer(window.project, window.project_dir)
window._on_export_concat_configs()
window._export_configs = original_export
assert json.loads((fresh / 'model_concat.json').read_text())['net']['name'] == 'parametric_mac.film.init_film'
assert window.export_concat_button.text() == 'Export training configs'
window.model_architecture.setCurrentIndex(window.model_architecture.findData('film-nano'))
assert 'selected model size' in window.architecture_hint.text()
window.model_architecture.setCurrentIndex(window.model_architecture.findData('auto'))
window.quality_slider.setValue(0)
assert window.n_train_spin.value() == 8
assert window.knob_table.item(0, 3).text() == '2.0'
window._commit_plan()
assert len(window.project.entries) == 14  # an LHS setting already covers a boundary
assert window.current_step() == "capture"
assert not window.capture_next_button.isEnabled()  # no route proof
assert not window.loopback_check.isChecked()
# A known route-test result allows recording only after setup confirmations;
# invalidating the setup removes readiness. No audio hardware is driven here.
window._has_device = lambda: True
window._device_sample_rate = lambda: 48000
window.wire_check.setChecked(True)
route = SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False,
    loopback_disagreement=False, crosscheck=None, peak=-16,
    latency=SimpleNamespace(delay=17, peak_delay=17.0))
window._on_route_test_success(route)
assert window._route_ready()
window.wire_check.setChecked(False)
assert not window._route_ready()
window.wire_check.setChecked(True)
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
QTest.mouseClick(window.training_profiles.buttons[0], Qt.LeftButton)
assert window.epochs.value() == 200
QTest.mouseClick(window.training_profiles.buttons[0], Qt.LeftButton)
assert window.training_profiles.buttons[0].isChecked()
QTest.mouseClick(window.training_profiles.buttons[1], Qt.LeftButton)
assert window.epochs.value() == 1
# Opening a run shows its saved metrics and remembers listening per run.
run = fresh / 'outputs' / 'example-run'
run.mkdir(parents=True)
(run / 'manifest.json').write_text('{}')
(run / 'status.json').write_text('{"status":"exported"}')
(run / 'model_parametric.nam').write_text('{}')
(run / 'metrics.json').write_text('{"epoch":2,"ESR":0.031}')
window.go_to_step("review")
assert '0.031' in window.review_metric.text()
(run / 'metrics.json').write_text('{"tiers":{"standard":{"epoch":2,"ESR":0.021},"nano":{"epoch":2,"ESR":0.041}}}')
window._show_run()
assert 'Standard: last validation ESR 0.021' in window.review_metric.text()
assert 'Nano: last validation ESR 0.041' in window.review_metric.text()
assert not window.save_model_button.isEnabled()
assert 'qualified playback' in window.model_path.text().lower()
# Mapping is explicit and persists per project; the raw export remains unsavable.
window.playback_pad.setValue(12)
window.playback_confirm.setChecked(True)
assert json.loads((fresh / 'workflow.json').read_text())['playback_calibration'] == {'confirmed': True, 'input_pad_db': 12.0}
assert window.qualify_button.isEnabled()
window._open_project(fresh)
assert window.playback_pad.value() == 12 and window.playback_confirm.isChecked()
# A qualified file enables saving; altering it disables saving again.
playback = run / 'playback'
playback.mkdir()
(playback / 'model_playback.nam').write_text('{"qualified":"fixture"}')
digest = hashlib.sha256((playback / 'model_playback.nam').read_bytes()).hexdigest()
(playback / 'qualification.json').write_text(json.dumps({'passed': True, 'model_sha256': digest}))
window.go_to(4)
assert window.save_model_button.isEnabled()
(playback / 'model_playback.nam').write_text('{"changed":true}')
window._show_run()
assert not window.save_model_button.isEnabled()
(playback / 'model_playback.nam').write_text('{"qualified":"fixture"}')
window._show_run()
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
# Control editing works without entering comma-separated names or editing JSON.
window.close()
window = MacWindow()
window.show()
second = root / 'amp-project'
second.mkdir()
window._create_project(second, assets)
from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QDialog, QDialogButtonBox
from PySide6.QtCore import QTimer, Qt
from parametric_mac.controls import SwitchSpec, load_project
assert all(f.fieldGrowthPolicy() == QFormLayout.AllNonFixedFieldsGrow for f in window.findChildren(QFormLayout))
assert all(f.formAlignment() == (Qt.AlignLeft | Qt.AlignTop) for f in window.findChildren(QFormLayout))
QTest.mouseClick(window.control_editor.add_knob, Qt.LeftButton)
assert len(window.control_editor.controls) == 3
window.control_editor.remove(2)
assert len(window.control_editor.controls) == 2
window._use_starter(True)
assert len(window.control_editor.controls) == 7
assert isinstance(window.control_editor.controls[-1], SwitchSpec)
assert window.gear_kind.currentText() == 'Amp'
assert window.amp_warning.text().startswith("Never connect the amp's speaker output")
assert len(load_project(second).knob_specs()) == 7  # saved draft
window._open_project(second)
assert len(window.control_editor.controls) == 7
assert window.gear_kind.currentText() == 'Amp'
# Edit a named switch through its properties dialog.
def save_positions():
    dialog = window.findChild(QDialog)
    dialog.findChild(QPlainTextEdit).setPlainText('Normal\\nBright\\nBrighter')
    QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save), Qt.LeftButton)
QTimer.singleShot(20, save_positions)
window.control_editor.edit(6)
assert window.control_editor.controls[-1].enum_names == ('Normal', 'Bright', 'Brighter')
window.quality_slider.setValue(0)
window._commit_plan()
assert {(e.params['Bright']) for e in window.project.entries_for_split('validation')} == {0, 1, 2}
window._open_project(second)
assert window.project.knob_specs()[-1].enum_names == ('Normal', 'Bright', 'Brighter')
assert 'Normal' in window.target_label.text() or 'Bright' in window.target_label.text()
assert 'Bright: 0' not in window.target_label.text()
# Larger knob counts remain practical to edit and preview.
for i in range(17):
    window.control_editor.add_control()
assert len(window.control_editor.controls) == 24
assert window._preview is not None
assert len(window._preview.entries) < 5000
assert not window.control_editor.add_knob.isEnabled()
# Geometry must work with larger layouts, not just the data pipeline.
window.resize(800, 680)
for stage in ("gear", "connect", "plan", "capture", "train", "review"):
    window.go_to_step(stage)
    QTest.qWait(80)
    page = window.pages.currentWidget()
    assert page.horizontalScrollBar().maximum() == 0, (stage, page.widget().size())
    if stage == "gear":
        assert window.control_editor.scroll.verticalScrollBar().maximum() > 0
        assert all(field.height() >= 34 for field in window.control_editor.rows.findChildren(QLineEdit))
    if stage == "plan":
        assert window.quality_slider.width() >= 430
    if stage == "train":
        assert window.architecture_hint.height() >= window.architecture_hint.heightForWidth(window.architecture_hint.width())
        assert window.training_profiles.height() >= window.training_profiles.minimumSizeHint().height()
    if stage == "review":
        from parametric_mac.ui.widgets.common import Columns
        columns = page.findChild(Columns)
        first, second = [item.parentWidget() for item in columns.columns]
        assert 20 <= second.y() - first.y() - first.height() <= 36
        from PySide6.QtCore import QPoint
        heading = columns.columns[1].itemAt(0).widget()
        visible_gap = heading.mapTo(columns, QPoint(0, 0)).y() - window.folder_button.mapTo(columns, QPoint(0, window.folder_button.height())).y()
        assert 20 <= visible_gap <= 40, visible_gap
    if stage == "capture":
        import math
        cols = max(1, min(3, window.knob_targets.width() // 170))
        assert window.knob_targets.height() >= math.ceil(len(window.knob_targets.targets)/cols)*165
        assert window.capture_hint.y() >= window.knob_targets.y() + window.knob_targets.height()
        next_target = window._next_pending_entry()
        from parametric_mac.controls import format_controls
        assert window.queue_rows.itemAt(0).widget().text().startswith(format_controls(next_target.params, window.project.knob_specs()))
window.resize(1140, 900)
window.go_to_step("train")
QTest.qWait(80)
assert window.architecture_hint.height() >= window.architecture_hint.heightForWidth(window.architecture_hint.width())
assert window.training_profiles.height() >= window.training_profiles.minimumSizeHint().height()
window.close()
app.processEvents()
print('GUI workflow check passed')
'''


def test_gui_workflow_and_job_controls(project, tmp_path):
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen',
           'PARAMETRIC_SETTINGS_DIR': str(tmp_path / 'settings'), 'PARAMETRIC_PROJECTS_ROOT': str(tmp_path / 'projects')}
    result = subprocess.run([sys.executable, '-c', SCRIPT, str(project)],
                            env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'GUI workflow check passed' in result.stdout
