"""Train page: one choice, one start button, live progress, and plain failures."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QPlainTextEdit, QProgressBar, QSizePolicy,
                               QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QWidget,
                               QDialog, QDialogButtonBox, QFileDialog, QMessageBox)

from ...theme import mono_font
from ...checks import read_json

from ...workflow import takes_to_record, write_state
from ..widgets.common import (PAGE_MARGIN, AlertBox, ChoiceCard, PageScroll, button, disclosure, label,
                              set_style_property, themed)
from ..widgets.meters import TrainingChart

QUICK_ROUNDS, FULL_ROUNDS = 1, 200
MODES = ((QUICK_ROUNDS, "Quick test", "Checks that everything works. The model will not sound good yet.", None),
         (FULL_ROUNDS, "Full training", "The real model.", "Recommended"))


def link(text: str, callback):
    widget = button(text, callback)
    widget.setProperty("link", True)
    return widget


class TrainPageMixin:
    def _train_page(self):
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(PageScroll.NoFrame)
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(PAGE_MARGIN, 32, PAGE_MARGIN, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label("Train your model", "title"))
        layout.addWidget(label("Your Mac learns how your gear sounds at every knob position. "
                               "Keep the app open while it trains.", "muted"))
        layout.addWidget(self._train_before())
        layout.addWidget(self._train_running())
        self.status_label = label("", "muted")
        layout.addWidget(self.status_label)
        layout.addWidget(self._train_alert())
        self._train_expert(layout)
        self.train_log = QPlainTextEdit()
        self.train_log.setReadOnly(True)
        self.train_log.setMaximumBlockCount(10000)
        self.train_log.setAccessibleName("Training log")
        self.train_log.setMinimumHeight(200)
        self.train_log_toggle = disclosure(layout, "Training log", self.train_log)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        self._train_footer = QWidget()
        row = QHBoxLayout(self._train_footer)
        row.setContentsMargins(0, 0, 0, 0)
        self.train_button = button("Start training →", lambda: self._start_training_flow(), True)
        self.train_continue = button("Next: Listen →", lambda: self.go_to_step("listen"), True)
        row.addWidget(self.train_button)
        row.addWidget(self.train_continue)
        self._refresh_mode_cards()

    def _train_before(self) -> QWidget:
        self.train_settings = QWidget()
        box = QVBoxLayout(self.train_settings)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(12)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.mode_cards = tuple(ChoiceCard() for _ in MODES)
        for card, (rounds, *_rest) in zip(self.mode_cards, MODES):
            card.clicked.connect(lambda rounds=rounds: self.epochs.setValue(rounds))
            cards.addWidget(card, 1)
        cards.addStretch(0)
        box.addLayout(cards)
        readiness = QHBoxLayout()
        self.train_readiness = label("", "muted")
        self.train_go_record = link("Go to Record", lambda: self.go_to_step("record"))
        readiness.addWidget(self.train_readiness, 1)
        readiness.addWidget(self.train_go_record)
        box.addLayout(readiness)
        return self.train_settings

    def _train_running(self) -> QWidget:
        self.train_running = QWidget()
        box = QVBoxLayout(self.train_running)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)
        self.train_stage_title = label("Training", "section")
        self.train_stage_note = label("", "muted")
        box.addWidget(self.train_stage_title)
        box.addWidget(self.train_stage_note)
        stats = QHBoxLayout()
        self.train_percent, self.train_time_left, self.train_rounds = (label("", "quality") for _ in range(3))
        for value, caption in ((self.train_percent, "done"), (self.train_time_left, "left"), (self.train_rounds, "rounds")):
            column = QVBoxLayout()
            value.setWordWrap(False)
            value.setFont(mono_font(24))
            value.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            column.addWidget(value)
            column.addWidget(label(caption, "muted"))
            stats.addLayout(column)
            stats.addSpacing(28)
        stats.addStretch()
        box.addLayout(stats)
        self.train_progress = QProgressBar()
        self.train_progress.setRange(0, 100)
        self.train_progress.setTextVisible(False)
        box.addWidget(self.train_progress)
        box.addWidget(label("Difference from the real gear, on test settings — lower is better", "muted"))
        self.training_chart = themed(TrainingChart(), self.appearance)
        box.addWidget(self.training_chart)
        self.train_metric = label("", "muted")
        box.addWidget(self.train_metric)
        self.stop_button = button("Stop training", self._stop)
        self.stop_button.setProperty("outline", True)
        box.addWidget(self.stop_button, alignment=Qt.AlignLeft)
        self.train_running.hide()
        return self.train_running

    def _train_alert(self) -> AlertBox:
        self.train_alert = AlertBox()
        self.retry_button = button("Try again on CPU", self._retry_cpu)
        self.retry_button.setProperty("outline", True)
        self.train_alert_show_log = link("Show log", lambda: self.train_log_toggle.setChecked(True))
        self.train_alert_go_record = link("Go to Record", lambda: self.go_to_step("record"))
        for widget in (self.retry_button, self.train_alert_show_log, self.train_alert_go_record):
            self.train_alert.actions.addWidget(widget)
        self.train_alert.actions.addStretch()
        return self.train_alert

    def _train_expert(self, layout) -> None:
        self.train_expert = QWidget()
        form = QFormLayout(self.train_expert)
        from ...architectures import ARCHITECTURES
        self.model_architecture = QComboBox()
        self.model_architecture.setAccessibleName("Model type")
        for key, title in ARCHITECTURES.items():
            self.model_architecture.addItem(title, key)
        self.model_architecture.currentIndexChanged.connect(self._save_architecture)
        self.architecture_hint = label("", "muted")
        self.playback_pad = QDoubleSpinBox()
        self.playback_pad.setRange(0, 30)
        self.playback_pad.setSuffix(" dB")
        self.playback_pad.setAccessibleName("Playback input attenuation")
        self.playback_confirm = QCheckBox("I confirmed the playback input mapping for these recordings")
        self.playback_pad.valueChanged.connect(self._save_playback_mapping)
        self.playback_confirm.toggled.connect(self._save_playback_mapping)
        form.addRow("Playback input attenuation", self.playback_pad)
        self.mapping_hint = label("Confirm the known playback attenuation; audio peaks cannot determine it.", "muted")
        form.addRow(self.mapping_hint)
        form.addRow(self.playback_confirm)
        self.record_reference_button = button("Record input reference…", self._record_input_reference)
        form.addRow(self.record_reference_button)
        self.warm_start_button = button("Choose raw model for fine-tuning…", self._choose_warm_start)
        self.clear_warm_start_button = button("Train from scratch", self._clear_warm_start)
        form.addRow(self.warm_start_button)
        form.addRow(self.clear_warm_start_button)
        self.warm_start_hint = label("Starts a new model. Original recordings stay in training.", "muted")
        form.addRow(self.warm_start_hint)
        self.device = QComboBox()
        self.device.addItem("Automatic · GPU when available", "auto")
        self.device.addItem("Apple GPU · MPS", "mps")
        self.device.addItem("CPU", "cpu")
        self.device.addItem("NVIDIA GPU · CUDA", "cuda")
        self.epochs = QSpinBox()
        self.epochs.setRange(1, 10000)
        self.epochs.setValue(FULL_ROUNDS)
        self.epochs.valueChanged.connect(lambda *_: self._refresh_mode_cards())
        self.batch = QSpinBox()
        self.batch.setRange(1, 64)
        self.batch.setValue(4)
        for text, widget in (("Model type", self.model_architecture), ("", self.architecture_hint),
                             ("Train on", self.device), ("Epochs (rounds)", self.epochs), ("Batch size", self.batch)):
            widget.setAccessibleName(text or "Model type note")
            form.addRow(text, widget)
        self.performance_mode = QComboBox()
        self.performance_mode.addItem("Safe baseline", 'baseline')
        self.performance_mode.addItem("Use measured recommendation", 'measured')
        self.performance_mode.currentIndexChanged.connect(self._sync_states)
        form.addRow("Performance", self.performance_mode)
        self.learning_schedule = QComboBox()
        self.learning_schedule.addItem("Original learning schedule", 'original')
        self.learning_schedule.addItem("Reduce rate on validation plateau", 'plateau')
        form.addRow("Learning rate", self.learning_schedule)
        self.early_stopping = QSpinBox()
        self.early_stopping.setRange(0, 1000)
        self.early_stopping.setSpecialValueText("Disabled")
        self.early_stopping.setSuffix(" checks without improvement")
        form.addRow("Stop on plateau", self.early_stopping)
        self.benchmark_button = button("Benchmark this device", lambda: self._start('tune'))
        form.addRow(self.benchmark_button)
        self.performance_hint = label("Benchmark one model size at a time. Short trials select speed settings; the trained model must still pass audio checks.", "muted")
        form.addRow(self.performance_hint)
        self._performance_report = None
        disclosure(layout, "Expert settings", self.train_expert)

    # ---- state ----------------------------------------------------------------------

    def _dual_model(self) -> bool:
        from ...architectures import is_dual
        return is_dual(self.model_architecture.currentData())

    def _refresh_mode_cards(self) -> None:
        if not hasattr(self, "mode_cards"):
            return
        dual = self._dual_model()
        for card, (rounds, title, body, tag) in zip(self.mode_cards, MODES):
            unit = "round" if rounds == 1 else "rounds per size" if dual else "rounds"
            text = body + (" Makes a Standard and a Nano size in one file." if dual and rounds == FULL_ROUNDS else "")
            card.set_content(title, str(rounds), unit, text, tag)
            card.set_selected(self.epochs.value() == rounds)

    def _refresh_train(self) -> None:
        if not hasattr(self, "train_readiness"):
            return
        project = self.project
        total = len(project.entries) if project else 0
        remaining = takes_to_record(project)
        captured = total - len(remaining)
        ready = bool(total) and captured == total
        if project is None:
            text = "Create or open a project first." if self.project_dir is None else "Ready to check and train."
        elif ready:
            text = f"✓ {total} recordings are saved. The app checks them first, then trains."
        else:
            text = f"Finish recording first: {captured} of {total} takes saved."
            if any(entry.qa and entry.qa.clipping for entry in remaining):
                text += " Replace the clipped takes on Record."
        self.train_readiness.setText(text)
        self.train_go_record.setVisible(project is not None and not ready)

    def _sync_train(self, busy: bool, can_train: bool) -> None:
        running = self.process is not None
        self.train_running.setVisible(running)
        self.train_settings.setVisible(not running)
        self.stop_button.setEnabled(running and not self.stopping)
        model = self._exported_run() is not None and not busy
        self.train_continue.setVisible(model)
        self.train_button.setText("Train again" if model else "Start training →")
        set_style_property(self.train_button, "primary", not model)
        set_style_property(self.train_button, "outline", model)
        self.train_button.setEnabled(can_train)
        for card in self.mode_cards:
            card.setEnabled(can_train)

    def _save_playback_mapping(self, *args):
        if self._ready and not self._applying and self.project_dir and not self._busy():
            self._workflow["playback_calibration"] = {"confirmed": self.playback_confirm.isChecked(),
                                                     "input_pad_db": self.playback_pad.value()}
            write_state(self.project_dir, self._workflow)
            self._sync_states()

    def _save_architecture(self, *args):
        from ...architectures import is_film, is_dual
        architecture = self.model_architecture.currentData()
        if hasattr(self, "architecture_hint"):
            text = ("FiLM supports up to 16 continuous controls. Use concat for switches. " if is_film(architecture)
                    else "Concat supports up to 24 controls, including switches. ")
            text += ("Both sizes are saved in one model; each gets the selected number of epochs." if is_dual(architecture)
                     else "Trains and saves the selected model size.")
            self.architecture_hint.setText(text)
        self._refresh_mode_cards()
        if self._ready and not self._applying and self.project_dir and not self._busy():
            self._workflow["model_architecture"] = self.model_architecture.currentData()
            write_state(self.project_dir, self._workflow)

    def _record_input_reference(self):
        if not self.project_dir or self._busy():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Record input reference")
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Enter known capture/playback levels. Audio peaks cannot measure this reference. "
                               "Keep interface gain controls at their calibrated positions."))
        kind = QComboBox()
        kind.addItem("Digital signal gains (dB)", 'digital')
        kind.addItem("Measured analog full-scale levels (dBu)", 'analog')
        layout.addWidget(kind)
        form = QFormLayout()
        capture, playback = QDoubleSpinBox(), QDoubleSpinBox()
        for field in (capture, playback):
            field.setRange(-120, 60)
            field.setDecimals(2)
        form.addRow("Capture signal gain", capture)
        form.addRow("Playback signal gain", playback)
        layout.addLayout(form)
        def labels():
            analog = kind.currentData() == 'analog'
            form.labelForField(capture).setText("Capture 0 dBFS reference" if analog else "Capture signal gain")
            form.labelForField(playback).setText("Playback ADC 0 dBFS reference" if analog else "Playback signal gain")
            for field in (capture, playback):
                field.setSuffix(" dBu" if analog else " dB")
        kind.currentIndexChanged.connect(labels)
        labels()
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        actions.accepted.connect(dialog.accept)
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)
        if dialog.exec() == QDialog.Accepted:
            try:
                from ...input_reference import record_reference
                from ...transients import project_data
                from ...cli import project_configs
                data, _ = project_configs(self.project_dir)
                record_reference(self.project_dir, project_data(self.project_dir, data or read_json(self.project_dir / "data.json")),
                                 kind=kind.currentData(), capture=capture.value(), playback=playback.value())
                self._load_training_extras()
                self._sync_states()
            except (OSError, ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self, "Could not record input reference", str(exc))

    def _clear_warm_start(self):
        if self.project_dir and not self._busy():
            self._workflow['warm_start_path'] = None
            write_state(self.project_dir, self._workflow)
            self.warm_start_hint.setText("Starts a new model. Original recordings stay in training.")

    def _choose_warm_start(self):
        if not self.project_dir or self._busy():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose matching raw training export", str(self.project_dir), "NAM model (*.nam)")
        if path:
            self._workflow['warm_start_path'] = path
            write_state(self.project_dir, self._workflow)
            self.warm_start_hint.setText("Fine-tuning from " + Path(path).name + ". Select its matching architecture below.")

    def _load_training_extras(self):
        saved = self._workflow.get('performance_profile')
        path = self.project_dir / saved if self.project_dir and isinstance(saved, str) else None
        self._performance_report = path if path and path.is_file() else None
        self.performance_mode.setCurrentIndex(0)
        self.learning_schedule.setCurrentIndex(0)
        self.early_stopping.setValue(0)
        self.performance_hint.setText('Saved recommendation available; hardware and recordings are checked before training.' if self._performance_report else
                                      'Benchmark one model size at a time. Audio qualification remains required.')
        self._recorded_reference = bool(self.project_dir and (self.project_dir / 'input_reference.json').exists())
        self.mapping_hint.setText('Confirm the known playback attenuation; audio peaks cannot determine it.')
        if self._recorded_reference:
            try:
                from ...input_reference import resolve_reference
                from ...transients import project_data
                from ...cli import project_configs
                data, _ = project_configs(self.project_dir)
                mapping = resolve_reference(self.project_dir, project_data(self.project_dir, data or read_json(self.project_dir / 'data.json')))
                self.playback_pad.setValue(mapping['input_pad_db'])
                self.playback_confirm.setChecked(True)
                self.mapping_hint.setText(f"Recorded input reference: fixed {mapping['input_pad_db']:g} dB attenuation, applied automatically.")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.playback_confirm.setChecked(False)
                self.mapping_hint.setText('Input reference needs updating: ' + str(exc))
        configured = self._workflow.get('warm_start_path')
        recipe = self.project_dir / 'fine_tune.json' if self.project_dir else None
        if 'warm_start_path' not in self._workflow and recipe and recipe.exists():
            configured = read_json(recipe).get('source')
        self.warm_start_hint.setText('Fine-tuning from ' + Path(configured).name + '. Select the matching architecture.' if configured else
                                     'Starts a new model. Original recordings stay in training.')
