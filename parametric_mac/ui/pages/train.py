"""Train page."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QSpinBox, QPlainTextEdit, QProgressBar,
)
from ...workflow import write_state
from ..widgets.common import label, button, disclosure, TrainingProfiles, Columns


class TrainPageMixin:
    def _train_page(self):
        layout = self._page("Train your model", "Your Mac learns how your gear changes as you turn its controls. Each run gets its own folder.")
        columns = Columns(layout)
        layout, reference = columns.columns
        self.train_readiness = label("Capture a project first.", "section")
        layout.addWidget(self.train_readiness)
        self.train_settings = QWidget()
        options = QVBoxLayout(self.train_settings)
        options.setContentsMargins(0, 0, 0, 0)
        self.training_mode = QComboBox()
        self.training_mode.addItem("Full training · 200 epochs", 200)
        self.training_mode.addItem("Quick workflow test · 1 epoch", 1)
        self.training_mode.addItem("Custom training duration", None)
        self.training_mode.setAccessibleName("Training duration")
        self.training_mode.currentIndexChanged.connect(self._set_duration)
        self.training_mode.hide()
        self.training_profiles = TrainingProfiles(self.training_mode)
        options.addWidget(self.training_profiles)
        self.training_profile_note = label(self.training_mode.currentText(), 'muted')
        self.training_mode.currentTextChanged.connect(self.training_profile_note.setText)
        options.addWidget(self.training_profile_note)
        layout.addWidget(label("Model architecture", "section"))
        from ...architectures import ARCHITECTURES
        self.model_architecture = QComboBox()
        self.model_architecture.setAccessibleName("Model architecture")
        for key, title in ARCHITECTURES.items():
            self.model_architecture.addItem(title, key)
        self.model_architecture.currentIndexChanged.connect(self._save_architecture)
        layout.addWidget(self.model_architecture)
        self.architecture_hint = label("Standard + Nano trains both sizes and saves one model for Ardor. "
                                       "Training runs twice; each size gets the selected number of epochs.", "muted")
        layout.addWidget(self.architecture_hint)
        advanced = QWidget()
        form = QFormLayout(advanced)
        self.device = QComboBox()
        self.device.addItem("Automatic · Apple GPU when available", "auto")
        self.device.addItem("Apple GPU · MPS", "mps")
        self.device.addItem("CPU", "cpu")
        self.epochs = QSpinBox()
        self.epochs.setRange(1, 10000)
        self.epochs.setValue(200)
        self.epochs.valueChanged.connect(self._show_duration)
        self.batch = QSpinBox()
        self.batch.setRange(1, 64)
        self.batch.setValue(4)
        for text, widget in (("Train on", self.device), ("Epochs", self.epochs), ("Batch size", self.batch)):
            widget.setAccessibleName(text)
            form.addRow(text, widget)
        disclosure(options, "Advanced training settings", advanced)
        layout.addWidget(self.train_settings)
        layout.addWidget(label("Try a quick test first to check the complete workflow. It is not a finished model. "
                               "Automatic uses the Apple GPU when available, otherwise CPU.", "muted"))
        row = QHBoxLayout()
        self.check_button = button("Check recordings", lambda: self._start("check"))
        self.train_button = button("Start training", lambda: self._start("train"), True)
        self.stop_button = button("Stop training", self._stop)
        row.addWidget(self.check_button)
        row.addWidget(self.train_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.stop_button, alignment=Qt.AlignLeft)
        self.status_label = label("Open or create a project to begin.")
        layout.addWidget(self.status_label)
        self.train_progress = QProgressBar()
        self.train_progress.setRange(0, 100)
        layout.addWidget(self.train_progress)
        self.train_metric = label("Validation results will appear during training.", "muted")
        layout.addWidget(self.train_metric)
        self.retry_button = button("Retry on CPU", self._retry_cpu)
        self.retry_button.hide()
        layout.addWidget(self.retry_button, alignment=Qt.AlignLeft)
        reference.addWidget(label('Before you train', 'section'))
        reference.addWidget(label('Every recording is checked for alignment and usable audio. Unseen test settings stay out of training.', 'muted'))
        self.train_log = QPlainTextEdit()
        self.train_log.setReadOnly(True)
        self.train_log.setMaximumBlockCount(10000)
        self.train_log.setAccessibleName("Training log")
        self.train_log.setMinimumHeight(200)
        self.train_log_toggle = disclosure(reference, "Training log and errors", self.train_log)
        self.train_continue = button("Review saved runs", lambda: self.go_to(4))
        layout.addWidget(self.train_continue, alignment=Qt.AlignRight)

    def _set_duration(self, *args):
        value = self.training_mode.currentData()
        if value is not None:
            self.epochs.setValue(value)

    def _show_duration(self, value):
        index = self.training_mode.findData(value)
        if index < 0:
            self.training_mode.setItemText(2, f"Custom training duration · {value} epochs")
            index = 2
        self.training_mode.setCurrentIndex(index)

    def _save_architecture(self, *args):
        from ...architectures import is_film, is_dual
        architecture = self.model_architecture.currentData()
        if hasattr(self, "architecture_hint"):
            text = ("FiLM supports up to 16 continuous controls. Use concat for switches. " if is_film(architecture)
                    else "Concat supports up to 24 controls, including switches. ")
            text += ("Both sizes are saved in one model; each gets the selected number of epochs." if is_dual(architecture)
                     else "Trains and saves the selected model size.")
            self.architecture_hint.setText(text)
        if self._ready and not self._applying and self.project_dir and not self._busy():
            self._workflow["model_architecture"] = self.model_architecture.currentData()
            write_state(self.project_dir, self._workflow)
