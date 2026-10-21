"""Exercise real tune -> measured profile -> training through desktop subprocesses."""
import os
import subprocess
import sys
from test_workflow import project


def test_desktop_benchmark_then_train_keeps_save_gate(project):
    script = r'''
import sys,json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from parametric_mac import gui
from parametric_mac.ui import jobs
class ShortTune(QProcess):
    def start(self, program, arguments):
        if 'tune' in arguments:
            arguments += ['--batches','1','--max-trials','1','--steps','2','--warmup','1']
        return super().start(program,arguments)
jobs.QProcess=ShortTune
app=QApplication([])
w=gui.MacWindow()
w.project_dir=Path(sys.argv[1])
w.model_architecture.setCurrentIndex(w.model_architecture.findData('auto'))
w.device.setCurrentIndex(w.device.findData('cpu'))
w.go_to_step("train")
w.show()
w._start('tune')
assert w.process is not None
assert not w.benchmark_button.isEnabled()
for _ in range(600):
    QTest.qWait(50)
    if w.process is None: break
assert w.process is None,w.train_log.toPlainText()
assert w._performance_report is not None,w.train_log.toPlainText()
assert w.performance_mode.currentData()=='measured'
assert not w.batch.isEnabled()
report=json.loads(w._performance_report.read_text())
assert report['status']=='complete'
assert not list(Path(report['prepared_run']).glob('*.nam'))
w.epochs.setValue(1)
w._start('train')
for _ in range(600):
    QTest.qWait(50)
    if w.process is None: break
assert w.process is None,w.train_log.toPlainText()
assert w._run_folder and (w._run_folder/'model_parametric.nam').is_file(),w.train_log.toPlainText()
manifest=json.loads((w._run_folder/'manifest.json').read_text())
assert manifest['performance_profile']==str(w._performance_report.resolve())
assert not w.save_model_button.isEnabled()
w.close()
'''
    result=subprocess.run([sys.executable,'-c',script,str(project)],capture_output=True,text=True,
                          timeout=90,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'})
    assert result.returncode==0,result.stdout+result.stderr
