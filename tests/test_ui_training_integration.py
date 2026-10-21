"""Cross-stack checks for Console and the new training controls."""
from gui_harness import run_gui


def test_training_controls_reset_between_projects_and_lock_during_jobs():
    run_gui(r'''
import hashlib, json, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QProcess
from parametric_mac.ui import project_io
from parametric_mac.gui import MacWindow
app = QApplication([])
inputs = Path(tempfile.mkdtemp())
for name in ('inputTrunc.wav', 'validation.wav'):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
w = MacWindow(); w._inputs_dir = inputs
w._start_new_capture(); w.gear_next_button.click()
assert w.benchmark_button.isEnabled() and w.record_reference_button.isEnabled()
w._workflow['warm_start_path'] = '/tmp/raw-start.nam'
w.learning_schedule.setCurrentIndex(1)
w.early_stopping.setValue(5)
w._performance_report = Path('/tmp/old-profile.json')
w.performance_mode.setCurrentIndex(1)
assert not w.batch.isEnabled()
w.process = QProcess(w); w._sync_states()
for widget in (w.device, w.epochs, w.batch, w.performance_mode, w.learning_schedule,
               w.early_stopping, w.benchmark_button, w.record_reference_button,
               w.warm_start_button, w.clear_warm_start_button):
    assert not widget.isEnabled(), widget
w.process = None
w._start_new_capture()
assert w._performance_report is None and w.performance_mode.currentData() == 'baseline'
assert w.learning_schedule.currentData() == 'original' and w.early_stopping.value() == 0
assert 'raw-start' not in w.warm_start_hint.text()
assert not w.record_reference_button.isEnabled()
# A stale qualification report cannot enable saving, even when its hash matches.
run = inputs / 'run'; (run / 'playback').mkdir(parents=True)
(run / 'playback/model_playback.nam').write_text('{}')
report = {'passed': True, 'policy': {'version': 2},
          'model_sha256': hashlib.sha256(b'{}').hexdigest()}
(run / 'playback/qualification.json').write_text(json.dumps(report))
from parametric_mac.review import qualified_model
assert qualified_model(run) is None
w.close()
print('OK')
''')
