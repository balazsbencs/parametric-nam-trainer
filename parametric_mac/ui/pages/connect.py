"""Connect page: wire it up, find the connection, check the loudest level."""
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import QCheckBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget
from nam.capture.gui.main import read_wav_rate

from ..copy import CONNECT_HELP, level_message, sample_rate_message
from ..widgets.common import PAGE_MARGIN, PageScroll, button, disclosure, field, label, set_style_property, themed
from ..widgets.meters import CableChain, LevelMeter
from .connect_find import ConnectFindMixin

WIRE_TEXT = "Monitoring is off and speakers are unplugged from the sound card"
AMP_WARNING = "Never connect the amp's speaker output to the sound card. Use a load box."
NEEDS = ("A sound card with one output and one input",
         "A reamp box (it makes the sound card output safe for a pedal input)",
         "The gear's own power supply")
AMP_NEED = "A load box that matches your amp's speaker output"
NO_DEVICE_TEXT = "No sound card found. Plug it in, then press refresh."


class Stage(QFrame):
    """A numbered step inside a page. Shows a check mark when done."""

    def __init__(self, number: int, title: str):
        super().__init__()
        self.number = number
        self.setProperty("stage", True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)
        head = QHBoxLayout()
        self.badge = QLabel(str(number))
        self.badge.setProperty("badge", True)
        self.badge.setFixedSize(22, 22)
        self.badge.setAlignment(Qt.AlignCenter)
        head.addWidget(self.badge)
        self.title = label(title, "section")
        head.addWidget(self.title, 1)
        self.body.addLayout(head)

    def set_done(self, done: bool) -> None:
        self.badge.setText("✓" if done else str(self.number))
        set_style_property(self.badge, "done", done)
        set_style_property(self, "done", done)


class ConnectPageMixin(ConnectFindMixin):
    def _connect_page(self):
        self._level_state = None
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(PageScroll.NoFrame)
        content = QWidget()
        content.setObjectName("page")
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(PAGE_MARGIN, 28, PAGE_MARGIN, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label("Connect your sound card", "title"))
        self.wire_stage, self.card_stage, self.level_stage = self._wire_stage(), self._card_stage(), self._level_stage()
        for stage in (self.wire_stage, self.card_stage, self.level_stage):
            layout.addWidget(stage)
        columns.addWidget(main, 3)
        columns.addWidget(self._connect_aside(), 2)
        # A Find result belongs to one sound card; built here, after the Expert notes exist.
        self.device_combo.currentIndexChanged.connect(lambda *_: self._reset_find())
        scroll.setWidget(content)
        self.pages.addWidget(scroll)
        self.connect_button = button("Next: Record →", lambda: self.go_to_step("record"), True)

    def _wire_stage(self) -> Stage:
        stage = Stage(1, "Wire it up")
        self.amp_warning = label(AMP_WARNING, "danger")
        self.amp_warning.hide()
        stage.body.addWidget(self.amp_warning)
        self.cable_chain = themed(CableChain(), self.appearance)
        stage.body.addWidget(self.cable_chain)
        self.wire_check = QCheckBox(WIRE_TEXT)
        self.wire_check.toggled.connect(lambda *_: self._sync_states())
        stage.body.addWidget(self.wire_check)
        return stage

    def _card_stage(self) -> Stage:
        stage = Stage(2, "Find the connection")
        row = QHBoxLayout()
        row.addWidget(self.device_combo, 1)
        self.refresh_devices_button = QToolButton()
        self.refresh_devices_button.setText("↻")
        self.refresh_devices_button.setToolTip("Look for sound cards again")
        self.refresh_devices_button.setAccessibleName("Refresh sound cards")
        self.refresh_devices_button.clicked.connect(self._refresh_devices)
        row.addWidget(self.refresh_devices_button)
        self.sample_rate_label = label("", "muted")
        self.sample_rate_label.setWordWrap(False)
        row.addWidget(self.sample_rate_label)
        stage.body.addLayout(row)
        self.no_devices_label.setStyleSheet("")  # upstream sets a fixed color; the theme decides
        self.no_devices_label.setProperty("role", "warn")
        stage.body.addWidget(self.no_devices_label)
        self.sample_rate_message_label = label("", "warn")
        self.audio_midi_button = button("Open Audio MIDI Setup", self._open_audio_midi_setup)
        self.audio_midi_button.setProperty("outline", True)
        self.sample_rate_message_label.hide()
        stage.body.addWidget(self.sample_rate_message_label)
        self.audio_midi_button.hide()
        stage.body.addWidget(self.audio_midi_button, 0, Qt.AlignLeft)
        self._find_rows(stage.body)
        self.sample_rate_warning_label.hide()
        # Any route change makes the last level check stale: re-evaluate readiness at once.
        for spin in (self.output_channel_spin, self.input_channel_spin):
            spin.valueChanged.connect(lambda *_: self._sync_states())
        self.device_combo.currentIndexChanged.connect(lambda *_: self._sync_states())
        return stage

    def _level_stage(self) -> Stage:
        stage = Stage(3, "Check the loudest level")
        stage.body.addWidget(label("Turn every knob on your gear to its loudest setting. Then press Check level.", "muted"))
        self.level_meter = themed(LevelMeter(), self.appearance)
        stage.body.addWidget(self.level_meter)
        row = QHBoxLayout()
        self.check_level_button = self.route_test_button
        self.check_level_button.setText("Check level")
        set_style_property(self.check_level_button, "outline", True)
        row.addWidget(self.check_level_button)
        self.level_result = self.route_test_result_label
        self.level_result.setText("")
        row.addWidget(self.level_result, 1)
        stage.body.addLayout(row)
        self.level_new_capture = button("Start a new capture with these controls", self._new_capture_from_gear)
        self.level_new_capture.setProperty("link", True)
        self.level_new_capture.hide()
        stage.body.addWidget(self.level_new_capture, alignment=Qt.AlignLeft)
        stage.body.addWidget(self.route_test_progress)
        self.route_test_progress.hide()  # shown only while a check runs
        return stage

    def _connect_aside(self) -> QWidget:
        aside = QWidget()
        aside.setObjectName("aside")
        aside.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(aside)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(label("What you need", "muted"))
        self._need_labels = [label("✓  " + text) for text in (*NEEDS, AMP_NEED)]
        for need in self._need_labels:
            layout.addWidget(need)
        self._need_labels[-1].hide()
        layout.addStretch()
        self.connect_help = label(CONNECT_HELP + "\n\nThe hardware guides in the docs folder show two example setups.", "muted")
        self.connect_help_toggle = disclosure(layout, "Show me how to fix it", self.connect_help)
        self._connect_expert(layout)
        return aside

    def _connect_expert(self, layout) -> None:
        advanced = QWidget()
        extra = QFormLayout(advanced)
        # The channel numbers, for people who set them by hand; Find sets them on the main path.
        self.audio_controls = QWidget()
        channels = QVBoxLayout(self.audio_controls)
        channels.setContentsMargins(0, 0, 0, 0)
        channels.addWidget(field("Output channel (where the cable to the reamp box starts)", self.output_channel_spin))
        channels.addWidget(field("Input channel (where the cable from the gear comes back)", self.input_channel_spin))
        extra.addRow(self.audio_controls)
        self._find_expert_notes(extra)
        self.loopback_check.setText("Use the optional timing loopback")
        extra.addRow(self.loopback_check)
        extra.addRow(label("A second cable from another output to another input, with low gain, measures timing.", "muted"))
        extra.addRow("Loopback output", self.loopback_output_channel_spin)
        extra.addRow("Loopback input", self.loopback_input_channel_spin)
        extra.addRow("Buffer size", self.buffer_size_combo)
        extra.addRow("Stream latency", self.latency_combo)
        self.loopback_check.setChecked(False)
        self.audio_advanced_toggle = disclosure(layout, "Expert settings", advanced)
        self.audio_advanced = advanced

    # ---- state ----------------------------------------------------------------------

    def _has_device(self) -> bool:
        return self.device_combo.currentData() is not None

    def _device_sample_rate(self) -> int | None:
        self._update_live_device_rates()
        return self._device_rate(self.device_combo.currentData(), self._live_device_rates)

    def _file_sample_rate(self) -> int | None:
        if self.project is None or self.project_dir is None:
            return None
        return read_wav_rate(self.project_dir / self.project.train_input)

    def _refresh_rates(self) -> None:
        """Asking CoreAudio is slow: read both rates once per state sync."""
        device = self._device_sample_rate() if self._has_device() else None
        self._rates = (device, self._file_sample_rate())

    def _rate_problem(self) -> str | None:
        if not hasattr(self, "_rates"):
            self._refresh_rates()
        return sample_rate_message(*self._rates)

    def _refresh_devices(self):
        super()._refresh_devices()
        if hasattr(self, "no_devices_label") and self.device_combo.count() == 0:
            self.no_devices_label.setText(NO_DEVICE_TEXT)

    def _connect_ready(self) -> bool:
        return (self.wire_check.isChecked() and self._has_device() and self._rate_problem() is None
                and self._level_state == "ok" and self._route_fingerprint is not None
                and self._route_fingerprint == self._current_audio_settings().stream_fingerprint())

    def _sync_connect(self) -> None:
        if not hasattr(self, "wire_stage"):
            return
        problem = self._rate_problem()
        rate = self._rates[0]
        self.sample_rate_label.setText(f"{rate / 1000:g} kHz" if rate else "")
        self.sample_rate_message_label.setText(problem or "")
        self.sample_rate_message_label.setVisible(problem is not None)
        self.audio_midi_button.setVisible(problem is not None)
        self.wire_stage.set_done(self.wire_check.isChecked())
        self.card_stage.set_done(self._has_device() and problem is None)
        self.level_stage.set_done(self._connect_ready())
        self.level_new_capture.setVisible(self._level_state == "clip" and self._plan_locked())
        self._sync_find()

    def _show_level(self, peak: float | None) -> None:
        self.level_meter.set_peak(peak)
        if peak is None:
            self._level_state = None
            self.level_result.setText("")
            return
        self._level_state, text = level_message(peak, locked=self._plan_locked())
        self.level_result.setText(text)
        set_style_property(self.level_result, "role", "ok" if self._level_state == "ok" else "danger")

    def _reset_connect(self) -> None:
        """Reopen or new project: confirm the wiring and check the level again."""
        self.wire_check.setChecked(False)
        self._route_fingerprint = None
        self._show_level(None)
        self._reset_find()

    def _open_audio_midi_setup(self) -> None:
        if not QProcess.startDetached("open", ["-a", "Audio MIDI Setup"]):
            self.sample_rate_message_label.setText("Open Audio MIDI Setup from Applications › Utilities.")

    def _gear_changed(self):
        amp = self.gear_kind.currentIndex() == 1
        self.cable_chain.set_amp(amp)
        self.amp_warning.setVisible(amp)
        self._need_labels[-1].setVisible(amp)
        self.wire_check.setChecked(False)
        self._route_fingerprint = None
        self._show_level(None)
        if self._ready and not self._applying:
            self._save_details()

    def needs_list(self) -> list[str]:
        return [need.text() for need in self._need_labels if not need.isHidden()]
