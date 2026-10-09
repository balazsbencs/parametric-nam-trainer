"""Extend the incumbent native Qt capture app; no separate audio engine."""
from pathlib import Path
import os
import signal
import sys
from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QComboBox, QSpinBox, QPushButton, QPlainTextEdit, QMessageBox)
from nam.capture.gui.main import MainWindow


class MacWindow(MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parametric — pedal capture & training")
        self.process = None
        self.stopping = False
        panel = QWidget()
        layout = QVBoxLayout(panel)
        title = QLabel("Train your pedal model")
        font = title.font()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        intro = QLabel("Open a project, capture its training and held-out settings, then train here. "
                       "Each run gets a new folder. Your WAVs stay untouched.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.device = QComboBox()
        self.device.addItem("Automatic · Apple GPU when available", "auto")
        self.device.addItem("Apple GPU · MPS", "mps")
        self.device.addItem("CPU", "cpu")
        self.epochs = QSpinBox()
        self.epochs.setRange(1, 10000)
        self.epochs.setValue(200)
        self.batch = QSpinBox()
        self.batch.setRange(1, 64)
        self.batch.setValue(4)
        form.addRow("Train on", self.device)
        form.addRow("Epochs", self.epochs)
        form.addRow("Batch size", self.batch)
        layout.addLayout(form)
        hint = QLabel("Start with 1 epoch to test the workflow, then try 200. "
                      "For memory errors, reduce batch size or select CPU. "
                      "An exported model still needs listening and held-out ESR checks.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self.check_button = QPushButton("Check captures")
        self.train_button = QPushButton("Start training")
        self.stop_button = QPushButton("Stop training")
        self.stop_button.setEnabled(False)
        self.folder_button = QPushButton("Open outputs")
        for button in (self.check_button, self.train_button, self.stop_button, self.folder_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.status_label = QLabel("Open or create a capture project in the Project tab.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.train_log = QPlainTextEdit()
        self.train_log.setReadOnly(True)
        self.train_log.setMaximumBlockCount(10000)
        self.train_log.setAccessibleName("Training log")
        layout.addWidget(self.train_log, 1)
        note = QLabel("Playback: model_parametric.nam needs NamParametricPlugin. "
                      "The stock NAM player cannot load this parametric architecture.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.train_tab = self.centralWidget().addTab(panel, "Train on Mac")
        self.check_button.clicked.connect(lambda: self._start("check"))
        self.train_button.clicked.connect(lambda: self._start("train"))
        self.stop_button.clicked.connect(self._stop)
        self.folder_button.clicked.connect(self._open_outputs)
        guide = QWidget()
        guide_layout = QVBoxLayout(guide)
        for heading, text in (
            ("UMC22 · pedal wiring", "OUTPUT L → reamp box → pedal input\n"
             "Pedal output → MIC/LINE 1, using its ¼-inch jack\n"
             "Optional timing loopback: OUTPUT R → INST 2, gain low. Run Route test first."),
            ("Before recording", "Turn DIRECT MONITOR off to prevent feedback. Disable DAW input monitoring. "
             "Disconnect speakers from the capture outputs. Use the pedal's correct power supply. "
             "Set Audio MIDI Setup to 48 kHz; select the same UMC22 for input and output."),
            ("Keep levels fixed", "Begin with low OUTPUT and reamp levels. Check your loudest pedal setting for "
             "input clipping, then keep interface gains, OUTPUT and reamp level fixed for the whole session. "
             "Photograph their positions. You turn only the knobs included in the plan."),
            ("Choose the first model", "Start with an overdrive or distortion pedal: Drive and Tone, fixed Level. "
             "Use reachable 0.5 increments and include corner settings. "
             "The capture planner currently supports continuous knobs; keep switches fixed and use separate projects."),
        ):
            label = QLabel(heading)
            f = label.font()
            f.setBold(True)
            label.setFont(f)
            guide_layout.addWidget(label)
            body = QLabel(text)
            body.setWordWrap(True)
            guide_layout.addWidget(body)
        guide_layout.addStretch()
        self.centralWidget().addTab(guide, "Pedal setup")

    def _start(self, command):
        if self.process is not None:
            return
        if self.project_dir is None:
            QMessageBox.information(self, "Open a project", "Open or create a project in the Project tab first.")
            return
        if self._worker is not None:
            QMessageBox.information(self, "Capture in progress", "Finish or cancel the capture before checking or training.")
            return
        self.stopping = False
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("MPLBACKEND", "Agg")
        process.setProcessEnvironment(env)
        process.setWorkingDirectory(str(self.project_dir))
        args = ["-m", "parametric_mac", command, str(self.project_dir)]
        if command == "train":
            args += ["--device", self.device.currentData(), "--epochs", str(self.epochs.value()),
                     "--batch", str(self.batch.value())]
        self.process = process
        process.readyReadStandardOutput.connect(self._read_log)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self.check_button.setEnabled(False)
        self.train_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        # Prevent changing capture projects while this run's paths are in use.
        for i in range(self.centralWidget().count()):
            if i != self.train_tab:
                self.centralWidget().setTabEnabled(i, False)
        self.status_label.setText("Checking captures…" if command == "check" else "Checking captures and preparing training…")
        self.train_log.appendPlainText(f"\n{command.capitalize()}: {self.project_dir}")
        process.start(sys.executable, args)

    def _read_log(self):
        if self.process:
            value = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            cursor = self.train_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(value)
            self.train_log.setTextCursor(cursor)
            self.train_log.ensureCursorVisible()

    def _finished(self, code, status):
        self._read_log()
        self.status_label.setText("Stopped. Review the run folder for any saved checkpoint or model." if self.stopping
                                  else "Finished. Review the results below." if code == 0
                                  else "Failed. Review the error below; for MPS errors, retry with CPU.")
        self._reset_process()

    def _process_error(self, error):
        if self.process and error == QProcess.FailedToStart:
            self.train_log.appendPlainText(self.process.errorString())
            self.status_label.setText("Could not start Python. Run Install.command again.")
            self._reset_process()

    def _reset_process(self):
        if self.process:
            self.process.deleteLater()
        self.process = None
        self.stop_button.setEnabled(False)
        self.check_button.setEnabled(True)
        self.train_button.setEnabled(True)
        for i in range(self.centralWidget().count()):
            self.centralWidget().setTabEnabled(i, True)

    def _stop(self):
        if self.process:
            self.stopping = True
            self.stop_button.setEnabled(False)
            self.status_label.setText("Stopping; allowing the trainer time to save…")
            process = self.process
            if os.name == "posix" and process.processId():
                try:
                    os.kill(process.processId(), signal.SIGINT)
                except ProcessLookupError:
                    pass
            else:
                process.terminate()
            # Bound shutdown time. A forced stop may leave only earlier checkpoints.
            QTimer.singleShot(15000, lambda: process.kill() if self.process is process else None)

    def _open_outputs(self):
        if self.project_dir:
            folder = self.project_dir / "outputs"
            if folder.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            else:
                self.status_label.setText("No outputs yet. Start a training run first.")

    def closeEvent(self, event):
        if self.process:
            QMessageBox.information(self, "Job running", "Use Stop training and wait for it to finish before closing.")
            event.ignore()
            return
        super().closeEvent(event)


def launch(train_tab=False):
    app = QApplication.instance() or QApplication(sys.argv)
    window = MacWindow()
    if train_tab:
        window.centralWidget().setCurrentIndex(window.train_tab)
    window.show()
    return app.exec()
