"""Connect page."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QCheckBox, QLineEdit,
)
from nam.capture.project import save_project
from ...controls import ControlModel
from ...control_editor import ControlEditor, starter
from ...theme import icon
from ...workflow import write_state
from ..widgets.common import label, button, disclosure, field, Columns


class ConnectPageMixin:
    def _connect_page(self):
        layout = self._page("Connect your gear", "A clean, repeatable route is the foundation of a good model. Set up once, then keep levels fixed.")
        columns = Columns(layout)
        left, right = columns.columns
        left.addWidget(label("Your project", "section"))
        details = QVBoxLayout()
        details.setSpacing(12)
        self.pedal_name = QLineEdit("My pedal")
        self.gear_kind = QComboBox()
        self.gear_kind.addItems(["Pedal", "Amp"])
        self.fixed_notes = QLineEdit("Level at 5")
        self.knob_names = QLineEdit("Drive, Tone")
        self.knob_names.hide()
        identity = QHBoxLayout()
        identity.setSpacing(12)
        identity.addWidget(field('Name', self.pedal_name), 3)
        identity.addWidget(field('Gear', self.gear_kind), 1)
        details.addLayout(identity)
        details.addWidget(field('Keep fixed', self.fixed_notes))
        left.addLayout(details)
        left.addSpacing(10)
        left.addWidget(label("Controls to model", "section"))
        left.addWidget(label("Add the knobs and switches you want in the model. Leave other controls fixed.", "muted"))
        self.control_editor = ControlEditor()
        left.addWidget(self.control_editor)
        presets = QHBoxLayout()
        presets.setContentsMargins(0, 0, 0, 0)
        presets.addWidget(button("Pedal starter", lambda: self._use_starter(False)))
        presets.addWidget(button("Amp starter", lambda: self._use_starter(True)))
        self.starter_actions = QWidget()
        self.starter_actions.setLayout(presets)
        left.addWidget(self.starter_actions)
        left.addSpacing(10)
        left.addWidget(label("Your recording setup", "section"))
        self.audio_controls = QWidget()
        form = QVBoxLayout(self.audio_controls)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        form.addWidget(field('Audio interface', self.device_combo))
        channels = QHBoxLayout()
        channels.setSpacing(12)
        channels.addWidget(field('Send · output', self.output_channel_spin), 1)
        channels.addWidget(field('Return · input', self.input_channel_spin), 1)
        form.addLayout(channels)
        left.addWidget(self.audio_controls)
        left.addWidget(self.no_devices_label)
        left.addWidget(self.sample_rate_warning_label)
        row = QHBoxLayout()
        self.refresh_devices_button = button("Refresh interfaces", self._refresh_devices)
        self.route_test_button.setText("Test connection")
        row.addWidget(self.refresh_devices_button)
        row.addWidget(self.route_test_button)
        left.addLayout(row)
        left.addWidget(self.route_test_progress)
        left.addWidget(self.route_test_result_label)
        right.addWidget(label("The signal route", "section"))
        route = QWidget()
        route.setObjectName("signalRoute")
        signal = QVBoxLayout(route)
        signal.setContentsMargins(0, 0, 0, 0)
        signal.setSpacing(0)
        self.route_caption = label('Capture route · channels 1 → 1')
        self.route_caption.setObjectName('routeCaption')
        signal.addWidget(self.route_caption)
        self.route_labels = []
        for i, (title, explanation) in enumerate([
                ("UMC22 OUTPUT L", "Line-level send"),
                ("Reamp box", "Set a repeatable instrument level"),
                ("Gear input → output", "Physical knobs and switches"),
                ("UMC22 MIC/LINE 1", "Use the ¼-inch line input")]):
            route_row = QWidget()
            route_row.setProperty('routeRow', i < 3)
            row = QHBoxLayout(route_row)
            row.setContentsMargins(16, 12, 16, 12)
            row.setSpacing(12)
            symbol = QLabel()
            symbol.setFixedSize(28, 28)
            symbol.setPixmap(icon(('plug', 'reamp', 'pedal', 'plug')[i]).pixmap(20, 20))
            symbol.setAlignment(Qt.AlignCenter)
            symbol.setProperty('routeSymbol', True)
            row.addWidget(symbol)
            words = QVBoxLayout()
            words.setContentsMargins(0, 0, 0, 0)
            words.setSpacing(4)
            title_label, explanation_label = label(title, 'section'), label(explanation, 'muted')
            words.addWidget(title_label)
            words.addWidget(explanation_label)
            row.addLayout(words, 1)
            if i < 3:
                direction = QLabel()
                direction.setPixmap(icon('arrow-down').pixmap(16, 16))
                row.addWidget(direction)
            signal.addWidget(route_row)
            self.route_labels.append((title_label, explanation_label))
        self.output_channel_spin.valueChanged.connect(self._update_route_caption)
        self.input_channel_spin.valueChanged.connect(self._update_route_caption)
        right.addWidget(route)
        self.wiring_note = label("You’ll need a reamp box, audio cables and the pedal’s correct power supply. Set the UMC22 to 48 kHz in Audio MIDI Setup.", "muted")
        right.addWidget(self.wiring_note)
        right.addSpacing(10)
        right.addWidget(label("Before audio starts", "section"))
        self.reamp_check = QCheckBox("Reamp box and powered gear connected")
        self.monitor_check = QCheckBox("Monitoring off; capture speakers disconnected")
        self.level_check = QCheckBox("Loudest setting clean; levels fixed")
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            right.addWidget(check)
        advanced = QWidget()
        extra = QFormLayout(advanced)
        self.loopback_check.setText("Use optional clean timing loopback")
        extra.addRow(self.loopback_check)
        extra.addRow(label("Optional: OUTPUT R → INST 2, gain low. Keep both routes on the UMC22.", "muted"))
        extra.addRow("Loopback output", self.loopback_output_channel_spin)
        extra.addRow("Loopback input", self.loopback_input_channel_spin)
        extra.addRow("Buffer size", self.buffer_size_combo)
        extra.addRow("Stream latency", self.latency_combo)
        self.loopback_check.setChecked(False)
        self.audio_advanced_toggle = disclosure(right, "Advanced audio routing", advanced)
        self.audio_advanced = advanced
        self.connect_button = button("Continue to plan", lambda: self.go_to_step("plan"), True)
        layout.addWidget(self.connect_button, alignment=Qt.AlignRight)
        layout.addStretch()

    def _mirror_controls(self):
        was_applying = self._applying
        self._applying = True
        self.knob_table.setRowCount(0)
        for c in self.control_editor.controls:
            self._add_knob_row(c.name, c.min, c.max, c.step, c.avoid_zero, c.is_gain)
        self.knob_names.setText(", ".join(c.name for c in self.control_editor.controls))
        self._applying = was_applying

    def _controls_changed(self):
        if self._busy() or self._plan_locked():
            return
        self._mirror_controls()
        if self._quality is not None:
            self._apply_quality(self._quality)
        else:
            self._refresh_preview()
        # Draft control edits never relabel an existing saved capture plan.
        if self.project and not self.project.entries:
            self.project.knobs = [ControlModel.from_spec(c) for c in self.control_editor.controls]
            save_project(self.project, self.project_dir)
        if self.project:
            self._workflow['draft_controls'] = [ControlModel.from_spec(c).model_dump() for c in self.control_editor.controls]
            write_state(self.project_dir, self._workflow)

    def _use_starter(self, amp):
        if self._busy() or self._plan_locked():
            return
        self.gear_kind.setCurrentIndex(int(amp))
        self.control_editor.set_controls(starter(amp))
        self.fixed_notes.setText('Cabinet / load-box settings fixed' if amp else 'Level at 5')
        self._controls_changed()
        self._save_details()

    def _update_route_caption(self, *args):
        self.route_caption.setText(f'Capture route · channels {self.output_channel_spin.value()} → {self.input_channel_spin.value()}')

    def _gear_changed(self):
        amp = self.gear_kind.currentIndex() == 1
        self.route_labels[2][0].setText('Amp → load box / DI' if amp else 'Pedal input → output')
        self.route_labels[2][1].setText('Speaker output to a matching load; DI / line return' if amp else 'Physical knobs and switches')
        self.wiring_note.setText(
            'Amp capture: reamp → amp input → a suitable load box / DI → interface line input. Never connect a speaker output directly to the UMC22. Match the load to your amp; see the README.' if amp else
            'You’ll need a reamp box, audio cables and the pedal’s correct power supply. Set the UMC22 to 48 kHz in Audio MIDI Setup.')
        self.reamp_check.setText('Reamp and correct amp load / DI connected' if amp else 'Reamp box and powered gear connected')
        self._route_fingerprint = None
        self.reamp_check.setChecked(False)
        if self._ready and not self._applying:
            self._save_details()

    def _save_details(self):
        if not self.project or self._busy() or self._plan_locked():
            return
        self.project.name = self.pedal_name.text().strip() or self.project_dir.name
        save_project(self.project, self.project_dir)
        self._workflow["fixed_notes"] = self.fixed_notes.text()
        self._workflow["gear_kind"] = "amp" if self.gear_kind.currentIndex() else "pedal"
        write_state(self.project_dir, self._workflow)
        self._refresh_all()
