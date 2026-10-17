"""Check and training subprocess jobs."""
from pathlib import Path
import os
import re
import signal
import sys
from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer


class JobsMixin:
    def _busy(self):
        return self.process is not None or self._worker is not None

    def _run_worker(self, call, **kwargs):
        # Keep viewing stages available, but prevent mutations while an audio worker runs.
        if self.process is not None:
            return
        finished = kwargs.get("on_finished")
        def complete():
            if finished:
                finished()
            self._sync_states()
        kwargs["on_finished"] = complete
        kwargs["disable"] = list(kwargs.get("disable", ())) + (self._mutating if self._ready else [])
        super()._run_worker(call, **kwargs)
        self._sync_states()

    def _start(self, command):
        if self._busy() or self.project_dir is None:
            return
        if command == "train" and self.project and (not self.project.entries or self.project.pending_entries()):
            self.status_label.setText("Finish recording the plan before training.")
            return
        self.stopping = False
        self.command = command
        self._run_folder = None
        self._log_buffer = ""
        self.retry_button.hide()
        self.train_progress.setValue(0)
        self.train_metric.setText("Validation results will appear during training.")
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("MPLBACKEND", "Agg")
        process.setProcessEnvironment(env)
        process.setWorkingDirectory(str(self.project_dir))
        args = ["-m", "parametric_mac", command, str(self.project_dir)]
        args += ["--architecture", self.model_architecture.currentData()]
        if command == "train":
            args += ["--device", self.device.currentData(), "--epochs", str(self.epochs.value()), "--batch", str(self.batch.value())]
        self.process = process
        process.readyReadStandardOutput.connect(self._read_log)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self.stop_button.setText("Stop check" if command == "check" else "Stop training")
        self.status_label.setText("Checking recordings…" if command == "check" else "Checking recordings and preparing training…")
        self.train_log.appendPlainText(f"\n{command.capitalize()}: {self.project_dir}\n")
        self._sync_states()
        process.start(sys.executable, args)

    def _read_log(self):
        if not self.process:
            return
        value = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        cursor = self.train_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(value)
        self.train_log.setTextCursor(cursor)
        self.train_log.ensureCursorVisible()
        self._log_buffer += value
        lines = self._log_buffer.split("\n")
        self._log_buffer = lines.pop()
        for line in lines:
            if line.startswith("Run folder: "):
                self._run_folder = Path(line.removeprefix("Run folder: ").strip())
            match = re.search(r"Epoch (\d+)/(\d+) started", line)
            if match:
                epoch, total = map(int, match.groups())
                self.train_progress.setValue(int((epoch - 1) / total * 100))
                self.status_label.setText(f"Training · epoch {epoch} of {total}. You can view other stages while it runs.")
            if " finished. " in line:
                self.train_metric.setText(line)

    def _finished(self, code, status):
        self._read_log()
        if self.stopping:
            self.status_label.setText("Stopped. Check the run folder for saved checkpoints or an export before continuing.")
        elif code == 0:
            self.status_label.setText("Recordings passed the checks. You can start training." if self.command == "check" else "Model exported. Open Review to inspect this run and listen.")
            self.train_progress.setValue(100)
        else:
            self.status_label.setText("Job failed. Your recordings are preserved. Open Training log and errors; for GPU or memory errors, retry on CPU.")
            self.train_log_toggle.setChecked(True)
            self.retry_button.setVisible(self.command == "train")
        self._reset_process()
        self._refresh_runs()
        if self._run_folder:
            index = self.run_combo.findData(str(self._run_folder))
            if index >= 0:
                self.run_combo.setCurrentIndex(index)

    def _process_error(self, error):
        if self.process and error == QProcess.FailedToStart:
            self.train_log.appendPlainText(self.process.errorString())
            self.status_label.setText("Could not start Python. Run Install.command again.")
            self.train_log_toggle.setChecked(True)
            self._reset_process()

    def _reset_process(self):
        if self.process:
            self.process.deleteLater()
        self.process = None
        self._sync_states()

    def _retry_cpu(self):
        self.device.setCurrentIndex(self.device.findData("cpu"))
        self.batch.setValue(1)
        self._start("train")

    def _stop(self):
        if not self.process:
            return
        self.stopping = True
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopping; allowing time to save. Wait before closing the app…")
        process = self.process
        if os.name == "posix" and process.processId():
            try:
                os.kill(process.processId(), signal.SIGINT)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        QTimer.singleShot(15000, lambda: process.kill() if self.process is process else None)
