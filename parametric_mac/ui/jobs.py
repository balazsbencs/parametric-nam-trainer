"""Check and training subprocess jobs."""
from pathlib import Path
import os
import re
import signal
import sys
import time
from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer

from ..workflow import takes_to_record
from .copy import check_errors, minutes_left, parse_epoch_finished

JOB_OUTPUT_TAIL = 200_000  # characters kept for the failure check; the full text is in the log


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

    def _start_training_flow(self):
        """Start training: check the recordings first, then train if the check passes."""
        if self._busy() or self.project_dir is None:
            return
        if self.project and (not self.project.entries or takes_to_record(self.project)):
            self.status_label.setText("Finish recording first. Replace any clipped takes.")
            return
        self.train_alert.hide()
        self._train_after_check = True
        self._start("check")

    def _start(self, command):
        if self._busy() or self.project_dir is None:
            return
        if command == "train" and self.project and (not self.project.entries or takes_to_record(self.project)):
            self.status_label.setText("Finish recording first.")
            return
        if command == "qualify" and (self._selected_run is None or not self.playback_confirm.isChecked()):
            self.status_label.setText("Confirm input mapping in Train, then select a saved run.")
            return
        self.stopping = False
        self.command = command
        self._run_folder = None
        self._log_buffer = ""
        self._job_output = ""
        self._epoch_started = []
        self._tiers_seen = []
        self.train_alert.hide()
        self.train_progress.setValue(0)
        self.train_metric.setText("")
        self.training_chart.clear()
        self.training_chart.set_total(self.epochs.value())
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("MPLBACKEND", "Agg")
        process.setProcessEnvironment(env)
        process.setWorkingDirectory(str(self.project_dir))
        if command == "qualify":
            self._run_folder = self._selected_run
            args = ["-m", "parametric_mac", "qualify", str(self._run_folder), "--input-pad-db", str(self.playback_pad.value())]
        else:
            args = ["-m", "parametric_mac", command, str(self.project_dir), "--architecture", self.model_architecture.currentData()]
        if command == "train":
            args += ["--device", self.device.currentData(), "--epochs", str(self.epochs.value()), "--batch", str(self.batch.value())]
            if self.playback_confirm.isChecked():
                args += ["--input-pad-db", str(self.playback_pad.value())]
        self.process = process
        process.readyReadStandardOutput.connect(self._read_log)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self.stop_button.setText("Stop check" if command in ("check", "qualify") else "Stop training")
        self.train_stage_title.setText("Checking playback model…" if command == "qualify" else "Checking your recordings…" if command == "check" else "Training")
        self.train_stage_note.setText("")
        for value in (self.train_percent, self.train_time_left, self.train_rounds):
            value.setText("—")
        self.status_label.setText("")
        self.train_log.appendPlainText(f"\n{command.capitalize()}: {self.project_dir}\n")
        self._sync_states()
        process.start(sys.executable, args)

    def _read_log(self):
        if not self.process:
            return
        self._handle_log_text(bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace"))

    def _handle_log_text(self, value: str) -> None:
        """Show trainer output in the log, and turn known lines into progress, chart points and run folder."""
        cursor = self.train_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(value)
        self.train_log.setTextCursor(cursor)
        self.train_log.ensureCursorVisible()
        self._job_output = (getattr(self, "_job_output", "") + value)[-JOB_OUTPUT_TAIL:]
        self._log_buffer = getattr(self, "_log_buffer", "") + value
        lines = self._log_buffer.split("\n")
        self._log_buffer = lines.pop()
        for line in lines:
            if line.startswith("Run folder: "):
                self._run_folder = Path(line.removeprefix("Run folder: ").strip())
            match = re.search(r"Epoch (\d+)/(\d+) started", line)
            if match:
                self._show_round(*map(int, match.groups()))
            point = parse_epoch_finished(line)
            if point is not None:
                self._show_point(point)

    def _show_round(self, epoch: int, total: int) -> None:
        starts = getattr(self, "_epoch_started", [])
        starts.append(time.monotonic())
        self._epoch_started = starts
        durations = [b - a for a, b in zip(starts, starts[1:])]
        left = minutes_left(durations, total - epoch + 1)
        self.train_progress.setValue(int((epoch - 1) / total * 100))
        self.train_percent.setText(f"{int((epoch - 1) / total * 100)}%")
        self.train_rounds.setText(f"{epoch - 1} / {total}")
        self.train_time_left.setText(f"~{left} min" if left is not None else "—")

    def _show_point(self, point) -> None:
        self.training_chart.add_point(point)
        self.train_metric.setText(f"Latest difference: {point.value:.4g} (lower is better)")
        if point.tier:
            tiers = self.__dict__.setdefault("_tiers_seen", [])
            if point.tier not in tiers:
                tiers.append(point.tier)
            self.train_stage_title.setText(f"Training · {point.tier.capitalize()} size")
            self.train_stage_note.setText("Step 1 of 2. The second size comes next." if tiers.index(point.tier) == 0
                                          else "Step 2 of 2.")

    def _finished(self, code, status):
        self._read_log()
        command, output, stopped = self.command, getattr(self, "_job_output", ""), self.stopping
        self._reset_process()
        self._refresh_runs()
        self._after_job(command, code, output, stopped)

    def _after_job(self, command: str, code: int, output: str, stopped: bool = False) -> None:
        """What happens after a check or a training run ends. Kept free of QProcess for tests."""
        if stopped:
            self._train_after_check = False
            self.status_label.setText("Stopped. Your recordings are safe. A run folder may hold a partial result.")
            return
        if command == "check":
            self._after_check(code, output)
            return
        if command == "qualify":
            self._refresh_runs()
            self.status_label.setText("Playback checks passed. Open Listen to save and assess the model." if code == 0 else
                                      "Playback checks failed. Open Listen and the log for details; recordings and checkpoints are preserved.")
            if code != 0:
                self.train_log_toggle.setChecked(True)
            return
        # Show the newest run with a model: the new one after success, the last good one after a failure.
        self._selected_run = None
        self._refresh_runs()
        if code == 0:
            self.train_alert.hide()
            self.train_progress.setValue(100)
            self.status_label.setText("Training finished. Open Listen for playback qualification and listening.")
            self._sync_states()
            return
        # Only the real error: Apple GPU runs also log harmless lines that mention "MPS" or "memory".
        memory = re.search(r"out of memory", output, re.IGNORECASE) is not None
        body = ("Training stopped: not enough graphics memory. Your recordings are safe. The CPU is slower but uses less memory."
                if memory else "Training stopped. Your recordings are safe. Open the log to see why, or try again on the CPU.")
        self._show_train_failure("Training stopped", body, retry=True)

    def _after_check(self, code: int, output: str) -> None:
        after = getattr(self, "_train_after_check", False)
        self._train_after_check = False
        if code == 0:
            if after:
                self._start("train")
            else:
                self.status_label.setText("Your recordings passed the check.")
            return
        problems = check_errors(output) or ("The check did not pass. Open the log for details.",)
        self._show_train_failure("Your recordings need attention", "\n".join(problems), retry=False)

    def _show_train_failure(self, title: str, body: str, retry: bool) -> None:
        self.train_alert.show_message(title, body)
        self.retry_button.setVisible(retry)
        self.train_alert_go_record.setVisible(not retry)
        self.train_log_toggle.setChecked(True)
        self.status_label.setText("")

    def _process_error(self, error):
        if self.process and error == QProcess.FailedToStart:
            self.train_log.appendPlainText(self.process.errorString())
            self._show_train_failure("Could not start", "Could not start Python. Run Install.command again.", retry=False)
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
        self.status_label.setText("Stopping. The trainer saves its work first; wait before you close the app…")
        process = self.process
        if os.name == "posix" and process.processId():
            try:
                os.kill(process.processId(), signal.SIGINT)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        QTimer.singleShot(15000, lambda: process.kill() if self.process is process else None)
