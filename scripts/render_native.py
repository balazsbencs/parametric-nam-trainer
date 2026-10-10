"""Render desktop/compact Qt evidence. --run-project must be real synthetic test output.

Run after pytest with the project's native GUI dependencies available. No audio is
recorded here. Plan/Capture show genuinely pending settings; Review reads real exports.
"""
import argparse
from pathlib import Path
import tempfile
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from parametric_mac.gui import MacWindow

parser = argparse.ArgumentParser()
parser.add_argument('--run-project', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = root / '.impeccable' / 'review' / 'native'
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
window = MacWindow()
window.show()
folder = Path(tempfile.mkdtemp(prefix='parametric-native-evidence-'))
window._create_project(folder)
window._commit_plan()
files = []
for name, size in [('desktop', (1140, 900)), ('compact', (800, 680))]:
    window.resize(*size)
    for index, stage in enumerate(('connect', 'plan', 'capture', 'train', 'review')):
        if stage == 'review':
            # Load a real native capture manifest and CPU export from pytest.
            window._open_project(args.run_project.resolve())
            window.project.name = 'Synthetic trainer verification'
            window.project_title.setText('Synthetic trainer verification')
        elif window.project_dir != folder:
            window._open_project(folder)
        window.go_to(index)
        app.processEvents()
        QTest.qWait(80)
        path = out / f'{stage}-{name}.png'
        window.grab().save(str(path))
        files.append(str(path.relative_to(root)))
window.resize(1140, 900)
window.go_to(3)
window._start('check')
app.processEvents()
window.grab().save(str(out / 'check-running-desktop.png'))
for _ in range(400):
    if not window.process:
        break
    QTest.qWait(50)
assert window.process is None
window.device.setCurrentIndex(window.device.findData('mps'))
window.epochs.setValue(1)
window._start('train')  # Actual unavailable-MPS failure on this Linux host.
for _ in range(400):
    if not window.process:
        break
    QTest.qWait(50)
assert window.process is None
app.processEvents()
window.grab().save(str(out / 'train-error-desktop.png'))
window._open_project(folder)
window.go_to(1)
window.plan_advanced_toggle.setChecked(True)
window.resize(800, 680)
app.processEvents()
window.pages.widget(1).ensureWidgetVisible(window.seed_spin, 0, 10)
app.processEvents()
window.grab().save(str(out / 'plan-advanced-compact.png'))
window.plan_advanced_toggle.setChecked(False)
window.resize(1140, 900)
for level, name in ((0, 'quick'), (4, 'overkill')):
    window.quality_slider.setValue(level)
    app.processEvents()
    window.grab().save(str(out / f'plan-{name}-desktop.png'))
window._open_project(args.run_project)
window.go_to(1)
app.processEvents()
window.grab().save(str(out / 'plan-locked-desktop.png'))
# Amp layout and switch targets use a genuinely planned pending project.
amp_folder = Path(tempfile.mkdtemp(prefix='parametric-amp-evidence-'))
window._create_project(amp_folder)
window._use_starter(True)
window.quality_slider.setValue(0)
window._commit_plan()
for name, size in [('desktop', (1140, 900)), ('compact', (800, 680))]:
    window.resize(*size)
    for stage, index in [('amp-controls', 0), ('amp-targets', 2)]:
        window.go_to(index)
        app.processEvents()
        QTest.qWait(80)
        path = out / f'{stage}-{name}.png'
        window.grab().save(str(path))
        files.append(str(path.relative_to(root)))
(out / 'evidence.json').write_text(json.dumps({
    'platform': 'Linux Qt offscreen, not macOS',
    'pending_capture_project': str(folder),
    'real_synthetic_training_project': str(args.run_project),
    'viewports': {'desktop':[1140,900], 'compact':[800,680]},
    'screenshots': files,
    'additional_states': ['check-running-desktop.png', 'train-error-desktop.png', 'plan-advanced-compact.png',
                          'plan-quick-desktop.png', 'plan-overkill-desktop.png', 'plan-locked-desktop.png'],
    'recordings_performed': False,
}, indent=2) + '\n')
window.close()
app.processEvents()
print(out)
