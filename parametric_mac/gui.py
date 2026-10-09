"""Five-stage desktop workflow over the pinned NAM capture engine."""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import shutil
import signal
import sys
from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QUrl, QRectF, QPointF
from PySide6.QtGui import QDesktopServices, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QPlainTextEdit, QMessageBox, QStackedWidget,
    QScrollArea, QSlider, QCheckBox, QLineEdit, QFileDialog, QTableWidgetItem,
    QProgressBar, QSizePolicy,
)
from nam.capture.gui.main import MainWindow, knob_rows_to_specs
from nam.capture.project import CaptureProject, load_project, save_project, atomic_write_json
from nam.capture.session import CaptureSession
from .assets import FILES
from .workflow import QUALITIES, quality_settings, make_plan, recording_minutes, read_state, write_state

STAGES = ("Connect", "Plan", "Capture", "Train", "Review")
STYLE = """
QMainWindow, QScrollArea, QWidget#page { background: #ffffff; color: #252a32; }
QWidget { font-size: 14px; color: #252a32; }
QWidget#sidebar { background: #f6f7f9; border-right: 1px solid #e4e6e9; }
QLabel[role="title"] { font-size: 28px; font-weight: 600; }
QLabel[role="section"] { font-size: 18px; font-weight: 600; }
QLabel[role="quality"] { font-size: 28px; font-weight: 600; }
QLabel[role="muted"] { color: #606773; }
QLabel[role="target"] { font-size: 32px; font-weight: 600; color: #175cd3; }
QPushButton { padding: 9px 14px; border: 1px solid #d0d5dd; border-radius: 6px; background: #ffffff; color: #252a32; }
QPushButton:hover { background: #f1f5fc; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #175cd3; }
QPushButton:disabled { color: #606773; background: #f3f4f6; border-color: #e4e6e9; }
QPushButton[primary="true"] { background: #175cd3; color: #ffffff; border-color: #175cd3; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #124db5; }
QPushButton[primary="true"]:disabled { background: #e8edf5; color: #606773; border-color: #d0d5dd; }
QPushButton[nav="true"] { text-align: left; background: transparent; border: none; padding: 12px 16px; }
QPushButton[nav="true"]:checked { background: #eaf1fe; color: #175cd3; font-weight: 600; }
QPushButton[nav="true"]:focus { border: 2px solid #175cd3; }
QLineEdit, QComboBox, QSpinBox { background: #ffffff; color: #252a32; border: 1px solid #d0d5dd; border-radius: 5px; padding: 6px; min-height: 22px; }
QPlainTextEdit, QTableWidget { background: #f8f9fb; color: #252a32; border: 1px solid #e4e6e9; border-radius: 5px; }
QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e2c79e, stop:0.25 #b6d2c1, stop:0.75 #b6d2c1, stop:1 #d3d9e2); }
QSlider::handle:horizontal { background: #175cd3; border: 3px solid #ffffff; width: 20px; margin: -8px 0; border-radius: 12px; }
QSlider::groove:horizontal:disabled { background: #e4e6e9; }
QSlider::handle:horizontal:disabled { background: #929aa6; }
QSlider:focus { border: 2px solid #175cd3; border-radius: 6px; }
QProgressBar { border: 1px solid #e4e6e9; border-radius: 4px; text-align: center; min-height: 20px; }
QProgressBar::chunk { background: #b5cbf3; }
"""


def label(text, role=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    widget.setTextFormat(Qt.PlainText)
    if role:
        widget.setProperty("role", role)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    widget.clicked.connect(callback)
    return widget


def disclosure(layout, title, widget):
    toggle = QPushButton(title)
    toggle.setCheckable(True)
    toggle.setAccessibleName(title)
    widget.setVisible(False)
    toggle.toggled.connect(widget.setVisible)
    layout.addWidget(toggle)
    layout.addWidget(widget)
    return toggle


class KnobTargets(QWidget):
    """Read-only physical dial positions, never software controls."""
    def __init__(self):
        super().__init__()
        self.targets = []
        self.setAccessibleName("Physical pedal knob positions")

    def set_targets(self, entry, knobs):
        self.targets = [(k, entry.params[k.name]) for k in knobs] if entry else []
        self.setAccessibleDescription(", ".join(f"{k.name} {v:g}, range {k.min:g} to {k.max:g}" for k, v in self.targets))
        self._size_targets()
        self.update()

    def _size_targets(self):
        columns = max(1, min(3, self.width() // 170))
        self.setMinimumHeight(math.ceil(len(self.targets) / columns) * 165)
        self.setVisible(bool(self.targets))

    def resizeEvent(self, event):
        self._size_targets()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        columns = max(1, min(3, self.width() // 170))
        width = self.width() / columns
        for index, (knob, value) in enumerate(self.targets):
            row, col = divmod(index, columns)
            center = QPointF(width * (col + .5), row * 165 + 59)
            painter.setPen(QPen(QColor("#d0d5dd"), 5))
            painter.drawArc(QRectF(center.x()-42, center.y()-42, 84, 84), 225*16, -270*16)
            angle = math.radians(225 - 270 * (value - knob.min) / (knob.max - knob.min))
            painter.setPen(QPen(QColor("#175cd3"), 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(center, center + QPointF(34 * math.cos(angle), -34 * math.sin(angle)))
            font = painter.font()
            font.setPixelSize(26)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(col*width, row*165+107, width, 33), Qt.AlignCenter, f"{value:g}")
            font.setPixelSize(14)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#252a32"))
            painter.drawText(QRectF(col*width, row*165+141, width, 22), Qt.AlignCenter, knob.name)


class QualityStops(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(48)
        self.setAccessibleName("Quick test: setup only; Decent: starting point; Good: recommended; Thorough: more detail; Overkill: diminishing returns")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor("#606773"))
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        hints = ("Setup only", "Starting point", "Recommended", "More detail", "Little extra")
        for i, quality in enumerate(QUALITIES):
            x = 13 + (self.width() - 26) * i / 4
            rect = QRectF(max(0, min(self.width()-104, x-52)), 0, 104, 44)
            align = Qt.AlignLeft if i == 0 else Qt.AlignRight if i == 4 else Qt.AlignHCenter
            painter.drawText(rect, align | Qt.AlignTop, quality.name + "\n" + hints[i])


class MacWindow(MainWindow):
    def __init__(self):
        self.process = None
        self.stopping = False
        self.command = None
        self._applying = True
        self._ready = False
        self._route_fingerprint = None
        self._preview = None
        self._quality = 2
        self._run_folder = None
        self._log_buffer = ""
        self._workflow = {}
        super().__init__()
        self.setWindowTitle("Parametric — pedal capture & training")
        self.setStyleSheet(STYLE)
        self.resize(1140, 840)
        self.setMinimumSize(760, 580)
        self._ready = True
        self._applying = False
        self.loopback_check.setChecked(False)
        self._apply_quality(2)
        self._refresh_all()

    def _build_ui(self):
        # Build upstream controls once, then place those exact controls in the new flow.
        # Their signal connections, device polling, recorder and QA remain intact.
        super()._build_ui()
        self._legacy = self.takeCentralWidget()
        self._legacy.setParent(self)
        self._legacy.hide()
        self._legacy.widget(0).hide()
        self.project_log.setMaximumBlockCount(1000)
        self.capture_log.setMaximumBlockCount(1000)
        self.knob_table.setRowCount(0)
        self._add_knob_row("Drive", 0, 10, .5, True, True)
        self._add_knob_row("Tone", 0, 10, .5)
        self.knob_table.setMinimumHeight(160)
        self.plan_table.setMinimumHeight(180)
        self.capture_table.setMinimumHeight(180)
        self._sort_mode = "ascending"
        self.routing_note_label.hide()
        self.next_entry_label.hide()
        for warning in (self.no_devices_label, self.sample_rate_warning_label,
                        self.capture_sample_rate_warning_label):
            warning.setStyleSheet("color: #925517;")

        shell = QWidget()
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(172)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 24, 12, 20)
        side.addWidget(label("Parametric", "section"))
        side.addWidget(label("Your pedal, captured.", "muted"))
        side.addSpacing(24)
        self.nav_buttons = []
        self.pages = QStackedWidget()
        for i, stage in enumerate(STAGES):
            nav = button(stage, lambda checked=False, index=i: self.go_to(index))
            nav.setProperty("nav", True)
            nav.setCheckable(True)
            nav.setAccessibleName(f"{stage} stage")
            side.addWidget(nav)
            self.nav_buttons.append(nav)
        side.addStretch()
        self.activity_label = label("No job running", "muted")
        side.addWidget(self.activity_label)
        side.addWidget(label("Local capture & training\nContinuous knobs", "muted"))
        outer.addWidget(sidebar)
        right = QWidget()
        content = QVBoxLayout(right)
        content.setContentsMargins(24, 16, 24, 12)
        header = QHBoxLayout()
        self.project_title = label("Start with a pedal project", "section")
        header.addWidget(self.project_title, 1)
        self.new_button = button("New project", self._on_new_project)
        self.open_button = button("Open project", self._on_open_project)
        header.addWidget(self.new_button)
        header.addWidget(self.open_button)
        content.addLayout(header)
        content.addWidget(self.pages, 1)
        outer.addWidget(right, 1)
        self.setCentralWidget(shell)
        self._connect_page()
        self._plan_page()
        self._capture_page()
        self._train_page()
        self._review_page()
        # The next step stays visible when the page needs scrolling on a small Mac.
        self.stage_actions = QStackedWidget()
        for action in (self.connect_button, self.plan_button, self.capture_continue,
                       self.train_continue, self.save_model_button):
            footer = QWidget()
            row = QHBoxLayout(footer)
            row.setContentsMargins(8, 8, 8, 0)
            row.addStretch()
            row.addWidget(action)
            self.stage_actions.addWidget(footer)
        content.addWidget(self.stage_actions)
        self.train_tab = 3  # Kept for the Train.command launch option.
        self.go_to(0)

        self._mutating = [self.new_button, self.open_button, self.pedal_name,
                          self.knob_names, self.fixed_notes, self.audio_controls,
                          self.route_test_button, self.plan_advanced, self.quality_slider,
                          self.plan_button, self.check_button, self.train_button,
                          self.train_settings, self.capture_next_button,
                          self.capture_selected_button, self.check_captures_button,
                          self.clear_captures_button, self.export_concat_button,
                          self.separate_button, self.refresh_devices_button]
        self.knob_table.itemChanged.connect(self._custom_plan)
        for spin in (self.n_train_spin, self.n_validation_spin, self.seed_spin):
            spin.valueChanged.connect(self._custom_plan)
        self.include_corners_check.toggled.connect(self._custom_plan)
        self.confirm_knobs.toggled.connect(self._sync_states)
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            check.toggled.connect(self._sync_states)
        self.pedal_name.editingFinished.connect(self._save_details)
        self.fixed_notes.editingFinished.connect(self._save_details)
        self.knob_names.editingFinished.connect(self._set_knob_names)
        self.review_check.toggled.connect(self._save_review)

    def _page(self, title, intro):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 24, 8, 24)
        layout.setSpacing(16)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(intro, "muted"))
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

    def _connect_page(self):
        layout = self._page("Connect your pedal", "Set up once. Keep these levels fixed throughout the capture session.")
        details = QFormLayout()
        self.pedal_name = QLineEdit("My pedal")
        self.knob_names = QLineEdit("Drive, Tone")
        self.fixed_notes = QLineEdit("Level at 5; all switches fixed")
        for text, widget in (("Pedal name", self.pedal_name), ("Knobs to model", self.knob_names),
                             ("Keep fixed", self.fixed_notes)):
            widget.setAccessibleName(text)
            details.addRow(text, widget)
        layout.addLayout(details)
        layout.addWidget(label("UMC22 wiring", "section"))
        layout.addWidget(label("OUTPUT L  →  reamp box  →  pedal input\nPedal output  →  MIC/LINE 1 (¼-inch jack)"))
        layout.addWidget(label("You’ll need a reamp box, audio cables and the pedal’s correct power supply. "
                               "Set the UMC22 to 48 kHz in Audio MIDI Setup.", "muted"))
        self.reamp_check = QCheckBox("Reamp box and powered pedal are connected")
        self.monitor_check = QCheckBox("Direct Monitor and DAW monitoring are off; capture outputs are not connected to speakers")
        self.level_check = QCheckBox("Loudest pedal setting has headroom; interface and reamp levels will stay fixed")
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            # Long instructions wrap in the label; the checkbox keeps a compact hit target.
            if check is self.monitor_check:
                check.setText("Monitoring off; no speakers on capture outputs")
            if check is self.level_check:
                check.setText("Loudest setting has headroom; keep all levels fixed")
            layout.addWidget(check)
        self.audio_controls = QWidget()
        form = QFormLayout(self.audio_controls)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Audio interface", self.device_combo)
        form.addRow("To pedal · output", self.output_channel_spin)
        form.addRow("From pedal · input", self.input_channel_spin)
        advanced = QWidget()
        extra = QFormLayout(advanced)
        self.loopback_check.setText("Use optional clean timing loopback")
        extra.addRow(self.loopback_check)
        extra.addRow(label("Optional: OUTPUT R → INST 2, gain low. Keep both routes on the UMC22.", "muted"))
        extra.addRow("Loopback output", self.loopback_output_channel_spin)
        extra.addRow("Loopback input", self.loopback_input_channel_spin)
        extra.addRow("Buffer size", self.buffer_size_combo)
        extra.addRow("Stream latency", self.latency_combo)
        # Unpatched loopback is not assumed on a first launch.
        self.loopback_check.setChecked(False)
        layout.addWidget(self.audio_controls)
        self.audio_advanced_toggle = disclosure(layout, "Advanced audio routing", advanced)
        # Disable advanced routing along with normal settings during any job.
        self.audio_advanced = advanced
        layout.addWidget(self.no_devices_label)
        layout.addWidget(self.sample_rate_warning_label)
        row = QHBoxLayout()
        self.refresh_devices_button = button("Refresh interfaces", self._refresh_devices)
        self.route_test_button.setText("Test connection")
        row.addWidget(self.refresh_devices_button)
        row.addWidget(self.route_test_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.route_test_progress)
        layout.addWidget(self.route_test_result_label)
        self.connect_button = button("Continue to plan", lambda: self.go_to(1), True)
        layout.addWidget(self.connect_button, alignment=Qt.AlignRight)
        layout.addStretch()

    def _plan_page(self):
        layout = self._page("Choose your capture quality", "One control sets the sampling and knob precision. You turn the real pedal’s knobs when prompted.")
        self.quality_name = label("Good · Recommended", "quality")
        layout.addWidget(self.quality_name)
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(0, 4)
        self.quality_slider.setValue(2)
        self.quality_slider.setTickInterval(1)
        self.quality_slider.setTickPosition(QSlider.TicksBelow)
        self.quality_slider.setAccessibleName("Capture quality")
        self.quality_slider.setMinimumHeight(40)
        self.quality_slider.valueChanged.connect(self._apply_quality)
        layout.addWidget(self.quality_slider)
        layout.addWidget(QualityStops())
        self.quality_description = label(QUALITIES[2].description)
        layout.addWidget(self.quality_description)
        self.effort_label = label("", "section")
        layout.addWidget(self.effort_label)
        self.plan_summary = label("", "muted")
        layout.addWidget(self.plan_summary)
        layout.addWidget(label("Coverage is a starting point, not a promise of sound quality. Training time is separate. "
                               "Listen at unseen settings before deciding your model is finished.", "muted"))
        self.plan_lock_label = label("")
        layout.addWidget(self.plan_lock_label)
        self.plan_advanced = QWidget()
        extra = QVBoxLayout(self.plan_advanced)
        extra.setContentsMargins(0, 8, 0, 8)
        extra.addWidget(label("Physical dial ranges", "section"))
        extra.addWidget(label("Defaults use a 0–10 dial. Change Min/Max to match your pedal. Drive avoids zero to prevent silent captures. "
                              "Level and switches stay fixed; use a new project for another switch position.", "muted"))
        extra.addWidget(self.knob_table)
        form = QFormLayout()
        form.addRow("Random training settings", self.n_train_spin)
        form.addRow("Unseen test settings", self.n_validation_spin)
        form.addRow("Repeatable seed", self.seed_spin)
        extra.addLayout(form)
        extra.addWidget(self.include_corners_check)
        extra.addWidget(self.corner_count_label)
        self.advanced_plan_hint = label("Manual changes show Custom. Moving the quality slider restores preset counts and steps, "
                                        "while keeping physical ranges and knob roles.", "muted")
        extra.addWidget(self.advanced_plan_hint)
        self.plan_advanced_toggle = disclosure(layout, "Advanced capture settings", self.plan_advanced)
        queue = QWidget()
        queue_layout = QVBoxLayout(queue)
        queue_layout.addWidget(self.plan_table)
        disclosure(layout, "View saved capture plan", queue)
        self.separate_button = button("Create a separate project…", self._on_new_project)
        self.separate_button.setVisible(False)
        layout.addWidget(self.separate_button, alignment=Qt.AlignLeft)
        self.plan_button = button("Start capturing", self._commit_plan, True)
        layout.addWidget(self.plan_button, alignment=Qt.AlignRight)
        layout.addStretch()

    def _capture_page(self):
        layout = self._page("Capture one setting at a time", "Set the knobs, confirm their positions, then record. Keep all other controls fixed.")
        self.capture_count = label("Create a plan to begin.", "section")
        layout.addWidget(self.capture_count)
        self.target_label = label("No setting queued", "section")
        layout.addWidget(self.target_label)
        self.knob_targets = KnobTargets()
        layout.addWidget(self.knob_targets)
        self.capture_hint = label("", "muted")
        layout.addWidget(self.capture_hint)
        self.confirm_knobs = QCheckBox("The pedal’s knobs match these positions")
        layout.addWidget(self.confirm_knobs)
        row = QHBoxLayout()
        self.capture_next_button.setText("Record this setting")
        self.capture_next_button.setProperty("primary", True)
        self.cancel_button.setText("Cancel recording")
        row.addWidget(self.capture_next_button)
        row.addWidget(self.cancel_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.capture_sample_rate_warning_label)
        layout.addWidget(self.capture_progress)
        self.capture_feedback = label("Your recordings are saved after each take. You can close and return later.")
        layout.addWidget(self.capture_feedback)
        details = QWidget()
        extra = QVBoxLayout(details)
        extra.addWidget(label("Select a row to rerecord its exact saved setting. Confirm the selected positions before recording.", "muted"))
        extra.addWidget(self.capture_table)
        self.capture_table.itemSelectionChanged.connect(self._show_selected_target)
        row = QHBoxLayout()
        self.capture_selected_button.setText("Rerecord selected setting")
        row.addWidget(self.capture_selected_button)
        row.addWidget(self.check_captures_button)
        extra.addLayout(row)
        extra.addWidget(self.capture_log)
        disclosure(layout, "Queue and recording details", details)
        maintenance = QWidget()
        extra = QVBoxLayout(maintenance)
        extra.addWidget(self.clear_captures_button)
        extra.addWidget(self.export_concat_button)
        disclosure(layout, "Advanced capture tools", maintenance)
        self.capture_continue = button("Continue to training", lambda: self.go_to(3), True)
        layout.addWidget(self.capture_continue, alignment=Qt.AlignRight)
        layout.addStretch()

    def _train_page(self):
        layout = self._page("Train your pedal model", "Your Mac learns how the pedal changes as you turn its knobs. Each run gets its own folder.")
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
        options.addWidget(self.training_mode)
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
        row.addWidget(self.stop_button)
        row.addStretch()
        layout.addLayout(row)
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
        self.train_log = QPlainTextEdit()
        self.train_log.setReadOnly(True)
        self.train_log.setMaximumBlockCount(10000)
        self.train_log.setAccessibleName("Training log")
        self.train_log.setMinimumHeight(200)
        disclosure(layout, "Training log and errors", self.train_log)
        self.train_continue = button("Review saved runs", lambda: self.go_to(4))
        layout.addWidget(self.train_continue, alignment=Qt.AlignRight)
        layout.addStretch()

    def _review_page(self):
        layout = self._page("Review your model", "An export is the beginning of review. Check unseen settings and listen before sharing it.")
        self.run_combo = QComboBox()
        self.run_combo.setAccessibleName("Saved training run")
        self.run_combo.currentIndexChanged.connect(self._show_run)
        layout.addWidget(self.run_combo)
        self.review_status = label("No saved training runs yet.", "section")
        self.review_metric = label("", "muted")
        self.model_path = label("", "muted")
        layout.addWidget(self.review_status)
        layout.addWidget(self.review_metric)
        layout.addWidget(self.model_path)
        layout.addWidget(label("Listen in NamParametricPlugin", "section"))
        layout.addWidget(label("This parametric architecture needs the matching player. The stock NAM plugin cannot load it. "
                               "Use the model’s same knob ranges, and compare against your saved test recordings.", "muted"))
        layout.addWidget(button("Get compatible player", lambda: QDesktopServices.openUrl(QUrl("https://github.com/phillipmself/NamParametricPlugin"))), alignment=Qt.AlignLeft)
        layout.addWidget(label("Check low, middle and high positions of each modeled knob; sweep between them and listen for differences, noise and level changes. "
                               "Test settings were held out of training. There is no built-in A/B player in this version.", "muted"))
        self.review_check = QCheckBox("I listened in the compatible player and checked unseen settings")
        layout.addWidget(self.review_check)
        self.review_note = label("", "muted")
        layout.addWidget(self.review_note)
        row = QHBoxLayout()
        self.save_model_button = button("Save model…", self._save_model, True)
        self.folder_button = button("Open run folder", self._open_outputs)
        self.recordings_button = button("Open test recordings", self._open_recordings)
        row.addWidget(self.save_model_button)
        row.addWidget(self.folder_button)
        row.addWidget(self.recordings_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()

    def go_to(self, index):
        self.pages.setCurrentIndex(index)
        if hasattr(self, "stage_actions"):
            self.stage_actions.setCurrentIndex(index)
        for i, nav in enumerate(self.nav_buttons):
            nav.setChecked(i == index)
        if index == 4:
            self._refresh_runs()

    def _busy(self):
        return self.process is not None or self._worker is not None

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

    def _plan_locked(self):
        # Sticky once any take was accepted, including if a file goes missing later.
        return bool(self.project and (self.project.captured_entries() or self._workflow.get("plan_locked")))

    def _apply_quality(self, level):
        if not self._ready or self._busy() or self._plan_locked():
            return
        try:
            knobs = knob_rows_to_specs(self._knob_table_rows())
            knobs, train, tests = quality_settings(knobs, level)
            self._applying = True
            for row, knob in enumerate(knobs):
                self.knob_table.setItem(row, 3, QTableWidgetItem(str(knob.step)))
            self.n_train_spin.setValue(train)
            self.n_validation_spin.setValue(tests)
            self.seed_spin.setValue(0)
            self.include_corners_check.setChecked(True)
            self._quality = level
            self.quality_slider.setAccessibleDescription(QUALITIES[level].name + ". " + QUALITIES[level].description)
        except ValueError as exc:
            self.plan_summary.setText(str(exc))
        finally:
            self._applying = False
        self._refresh_preview()

    def _custom_plan(self, *args):
        if not self._ready or self._applying:
            return
        if args and isinstance(args[0], QTableWidgetItem) and args[0].column() == 0:
            self.knob_names.setText(", ".join(row[0] for row in self._knob_table_rows()))
        self._quality = None
        self._refresh_preview()

    def _refresh_preview(self):
        if not self._ready:
            return
        quality = QUALITIES[self._quality] if self._quality is not None else None
        self.quality_name.setText((quality.name + (" · Recommended" if self._quality == 2 else "")) if quality else "Custom capture plan")
        self.quality_description.setText(quality.description if quality else "Advanced settings are active. Move the quality slider to restore a complete preset.")
        if self._plan_locked():
            self.quality_description.setText("Recording has started. Continue with the saved capture settings.")
        try:
            if self._plan_locked():
                self._preview = self.project
            else:
                self._preview = make_plan(knob_rows_to_specs(self._knob_table_rows()), self.n_train_spin.value(),
                                          self.n_validation_spin.value(), self.seed_spin.value(), self.include_corners_check.isChecked())
            train = len(self._preview.entries_for_split("train"))
            tests = len(self._preview.entries_for_split("validation"))
            seconds = self._input_durations()
            self.effort_label.setText(f"{train + tests} recordings · about {recording_minutes(self._preview, *seconds)} minutes")
            self.plan_summary.setText(f"{train} training recordings · {tests} unseen test recordings\n"
                                      + "Modeling: " + ", ".join(k.name for k in self._preview.knob_specs())
                                      + f" · Keep fixed: {self.fixed_notes.text()}\nEstimate allows 10 seconds to turn knobs; breaks and retries add time.")
        except ValueError as exc:
            self._preview = None
            self.effort_label.setText("Adjust your capture settings")
            self.plan_summary.setText(str(exc))
        self._sync_states()

    def _input_durations(self):
        if self.project and self.project_dir:
            import soundfile as sf
            try:
                return tuple(sf.info(self.project_dir / self.project.input_for_split(s)).duration for s in ("train", "validation"))
            except (OSError, RuntimeError):
                pass
        return 38, 7

    def _set_knob_names(self):
        if self._busy() or self._plan_locked():
            return
        names = [name.strip() for name in self.knob_names.text().split(",") if name.strip()]
        if not names or len(names) > 8 or len(set(names)) != len(names):
            self.plan_summary.setText("Enter 1–8 unique knob names, separated by commas.")
            self.knob_names.setText(", ".join(row[0] for row in self._knob_table_rows()))
            return
        rows = {row[0]: row for row in self._knob_table_rows()}
        self._applying = True
        self.knob_table.setRowCount(0)
        gain_seen = False
        for name in names:
            values = list(rows.get(name, (name, 0, 10, .5, name.lower() in ("drive", "gain"), name.lower() in ("drive", "gain"))))
            if values[5] and gain_seen:
                values[5] = False
            gain_seen |= bool(values[5])
            self._add_knob_row(*values)
        self._applying = False
        if self._quality is not None:
            self._apply_quality(self._quality)
        else:
            self._refresh_preview()

    def _save_details(self):
        if not self.project or self._busy() or self._plan_locked():
            return
        self.project.name = self.pedal_name.text().strip() or self.project_dir.name
        save_project(self.project, self.project_dir)
        self._workflow["fixed_notes"] = self.fixed_notes.text()
        write_state(self.project_dir, self._workflow)
        self._refresh_all()

    def _on_new_project(self):
        if self._busy():
            return
        directory = QFileDialog.getExistingDirectory(self, "Choose an empty folder for this pedal project")
        if directory:
            try:
                self._create_project(Path(directory))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not create project", str(exc))

    def _create_project(self, directory, inputs=None):
        directory = Path(directory)
        if any(directory.iterdir()):
            raise ValueError("Choose an empty folder. Your existing project and recordings have been left untouched.")
        inputs = Path(inputs) if inputs else Path(__file__).resolve().parents[1] / "inputs"
        for name, digest in FILES.items():
            path = inputs / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Capture signals are missing or changed. Run Install.command before creating a project.")
        for source, dest in (("inputTrunc.wav", "input_train.wav"), ("validation.wav", "input_validation.wav")):
            shutil.copy2(inputs / source, directory / dest)
        audio = self._current_audio_settings().model_copy(deep=True)
        self.project = CaptureProject(name=self.pedal_name.text().strip() or directory.name, knobs=[], audio=audio)
        self.project_dir = directory
        self._train_input_name, self._validation_input_name = "input_train.wav", "input_validation.wav"
        self.session = CaptureSession(self.project, directory)
        self._workflow = {"quality": self._quality, "fixed_notes": self.fixed_notes.text(), "plan_locked": False}
        self._route_fingerprint = None
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            check.setChecked(False)
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.retry_button.hide()
        save_project(self.project, directory)
        write_state(directory, self._workflow)
        self.status_label.setText("Project created. Connect your pedal and test the connection.")
        self.go_to(0)
        self._refresh_all()
        self._refresh_preview()

    def _on_open_project(self):
        if self._busy():
            return
        directory = QFileDialog.getExistingDirectory(self, "Open pedal project")
        if directory:
            try:
                self._open_project(Path(directory))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not open project", str(exc))

    def _open_project(self, directory):
        project = load_project(directory)
        self._applying = True
        self.project, self.project_dir = project, Path(directory)
        self.session = CaptureSession(project, self.project_dir)
        self._train_input_name, self._validation_input_name = project.train_input, project.validation_input
        self._workflow = read_state(directory)
        if project.captured_entries():
            self._workflow["plan_locked"] = True
            write_state(directory, self._workflow)
        stored_quality = self._workflow.get("quality")
        self._quality = stored_quality if type(stored_quality) is int and 0 <= stored_quality <= 4 else None
        self.pedal_name.setText(project.name)
        self.fixed_notes.setText(self._workflow.get("fixed_notes", "Keep unmodeled controls at their recorded positions"))
        self._load_knobs_into_ui()
        if not project.knobs:
            self._add_knob_row("Drive", 0, 10, .5, True, True)
            self._add_knob_row("Tone", 0, 10, .5)
        self.knob_names.setText(", ".join(row[0] for row in self._knob_table_rows()))
        self.quality_slider.setValue(self._quality if self._quality is not None else 2)
        self._applying = False
        self._route_fingerprint = None
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.train_metric.setText("Validation results will appear during training.")
        self.retry_button.hide()
        self.status_label.setText("Project opened. Check completed recordings before training.")
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            check.setChecked(False)
        notes = self._recover_and_reconcile()
        if notes:
            self.capture_feedback.setText("\n".join(notes))
            self.capture_log.appendPlainText("\n".join(notes))
        self._load_audio_settings_into_ui()
        if not project.entries and self._quality is not None:
            self._apply_quality(self._quality)
        self._refresh_all()
        self._refresh_preview()
        self._refresh_runs()
        self.go_to(3 if project.entries and not project.pending_entries() else 0)

    def _commit_plan(self):
        if self._busy() or self.project_dir is None:
            return
        if self._plan_locked():
            self.go_to(2)
            return
        self._set_knob_names()
        self._refresh_preview()
        if self._preview is None:
            return
        project = self._preview.model_copy(deep=True)
        project.name = self.pedal_name.text().strip() or self.project_dir.name
        project.audio = self.project.audio.model_copy(deep=True)
        project.train_input, project.validation_input = self._train_input_name, self._validation_input_name
        project.created_with_version = self.project.created_with_version or project.created_with_version
        project.alignment_reference = self.project.alignment_reference
        save_project(project, self.project_dir)
        self.project = project
        self.session = CaptureSession(project, self.project_dir)
        self._workflow.update(quality=self._quality, fixed_notes=self.fixed_notes.text(), plan_locked=False)
        write_state(self.project_dir, self._workflow)
        self._refresh_all()
        self.go_to(2)

    def _route_ready(self):
        return (self._route_fingerprint is not None
                and self._route_fingerprint == self._current_audio_settings().stream_fingerprint()
                and all(c.isChecked() for c in (self.reamp_check, self.monitor_check, self.level_check)))

    def _on_route_test(self):
        if self._busy():
            return
        self._route_fingerprint = None
        super()._on_route_test()
        self._sync_states()

    def _on_route_test_success(self, result):
        super()._on_route_test_success(result)
        if result.ok and not result.loopback_failed and not result.loopback_disagreement and result.peak < -1:
            self._route_fingerprint = self._current_audio_settings().stream_fingerprint()
        else:
            self._route_fingerprint = None
            if result.ok and result.peak >= -1:
                self.route_test_result_label.setText("Signal is too close to clipping. Lower levels, then test again before recording.")
        self._sync_states()

    def _show_selected_target(self):
        self.confirm_knobs.setChecked(False)
        row = self.capture_table.currentRow()
        if 0 <= row < len(self._displayed_entries):
            entry = self._displayed_entries[row]
            self.target_label.setText(" · ".join(f"{k}: {v:g}" for k, v in entry.params.items()))
            self.knob_targets.set_targets(entry, self.project.knob_specs())
            self.capture_hint.setText("Selected setting for rerecording. Use Rerecord selected setting below. Record this setting resumes the next pending take.")
        self._sync_states()

    def _begin_capture(self, entry):
        if self._busy() or not self.confirm_knobs.isChecked() or not self._route_ready():
            return
        # A selected row must never confirm a different pending setting.
        expected = " · ".join(f"{k}: {v:g}" for k, v in entry.params.items())
        if self.target_label.text() != expected:
            self.target_label.setText(expected)
            self.knob_targets.set_targets(entry, self.project.knob_specs())
            self.confirm_knobs.setChecked(False)
            self.capture_hint.setText("Confirm these positions before recording this setting.")
            return
        self.capture_feedback.setText("Recording… Keep the pedal still until this take is saved.")
        super()._begin_capture(entry)
        self._sync_states()

    def _on_capture_success(self, qa):
        self.confirm_knobs.setChecked(False)
        self._workflow["plan_locked"] = True
        write_state(self.project_dir, self._workflow)
        self.capture_feedback.setText("Take saved." + (f" Peak {qa.peak:.1f} dBFS." if qa.peak is not None else "")
                                      + (" QA needs attention: " + "; ".join(qa.messages) if qa.messages else " Timing and signal checks completed."))
        super()._on_capture_success(qa)
        self._refresh_preview()

    def _on_capture_failure(self, message):
        self.confirm_knobs.setChecked(False)
        self.capture_feedback.setText("Take not accepted. Check the recording details, correct the problem and retry the same setting. If you change levels, use a separate project.")
        super()._on_capture_failure(message)

    def _on_capture_cancelled(self):
        self.confirm_knobs.setChecked(False)
        self.capture_feedback.setText("Recording cancelled. This setting is still pending.")
        super()._on_capture_cancelled()

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

    def _refresh_all(self):
        super()._refresh_all()
        if not self._ready:
            return
        self.project_title.setText((self.project.name or self.project_dir.name) if self.project else
                                   self.project_dir.name if self.project_dir else "Start with a pedal project")
        if self.project:
            captured = len(self.project.captured_entries())
            total = len(self.project.entries)
            self.capture_count.setText(f"{captured} of {total} recordings saved" if total else "Choose a capture quality in Plan.")
            entry = self._next_pending_entry()
            self.knob_targets.set_targets(entry, self.project.knob_specs())
            self.target_label.setText(" · ".join(f"{k}: {v:g}" for k, v in entry.params.items()) if entry else "All planned settings recorded" if total else "No setting queued")
            self.capture_hint.setText(("Unseen test setting" if entry.split == "validation" else "Training setting") + f" · Keep fixed: {self.fixed_notes.text()}" if entry else "Continue to training when the recordings are ready.")
            self.train_readiness.setText(f"{captured}/{total} recordings saved. " + ("Ready to check and train." if total and captured == total else "Finish your capture plan first."))
        self.confirm_knobs.setChecked(False)
        self._sync_states()

    def _refresh_sample_rate_warning(self):
        super()._refresh_sample_rate_warning()
        if self._ready:
            self._sync_states()

    def _refresh_status_bar(self):
        if not self.project:
            self.status_bar.showMessage("Create or open a pedal project to begin.")
            return
        self.status_bar.showMessage(f"{len(self.project.captured_entries())} of {len(self.project.entries)} recordings saved")

    def _sync_states(self, *args):
        if not self._ready:
            return
        busy = self._busy()
        for widget in self._mutating:
            widget.setEnabled(not busy)
        self.audio_advanced.setEnabled(not busy)
        locked = self._plan_locked()
        self.advanced_plan_hint.setText("These are the saved settings used to label this project’s recordings." if locked else
                                        "Manual changes show Custom. Moving the quality slider restores preset counts and steps, while keeping physical ranges and knob roles.")
        for widget in (self.quality_slider, self.plan_advanced, self.knob_names, self.fixed_notes, self.pedal_name):
            widget.setEnabled(not busy and not locked)
        self.plan_lock_label.setText("This plan is locked because recording has started. Create a separate project to change quality, knobs or levels." if locked else "Create or open a project using the buttons above." if not self.project else "")
        self.separate_button.setVisible(locked)
        self.plan_button.setText("Continue capturing" if locked else "Start capturing")
        self.plan_button.setEnabled(not busy and self.project is not None and self._preview is not None)
        self.connect_button.setEnabled(not busy and self.project is not None and self._route_ready())
        self.route_test_button.setEnabled(not busy and self.device_combo.currentData() is not None
                                          and self.reamp_check.isChecked() and self.monitor_check.isChecked() and self.level_check.isChecked())
        complete = bool(self.project and self.project.entries and not self.project.pending_entries())
        can_record = not busy and self._route_ready() and self.confirm_knobs.isChecked() and not self._current_sample_rate_warnings()
        self.capture_next_button.setEnabled(can_record and self._next_pending_entry() is not None)
        self.capture_selected_button.setEnabled(can_record and self.capture_table.currentRow() >= 0)
        self.capture_continue.setEnabled(complete)
        self.check_button.setEnabled(not busy and self.project_dir is not None)
        # Legacy config-only projects may be checked/trained without a capture manifest.
        self.train_button.setEnabled(not busy and (complete or (self.project is None and self.project_dir is not None)))
        self.confirm_knobs.setEnabled(not busy and bool(self.project and self.project.entries))
        self.cancel_button.setEnabled(self._worker is not None and self._cancel_token is not None)
        self.stop_button.setEnabled(self.process is not None and not self.stopping)
        self.review_check.setEnabled(not busy and self._exported_run() is not None)
        self.save_model_button.setEnabled(not busy and self._exported_run() is not None)
        self.activity_label.setText("Checking recordings…" if self.process and self.command == "check" else "Training in progress…" if self.process else "Audio operation running…" if self._worker else "No job running")
        if self.project and self.project.entries and not self._route_ready() and not busy:
            self.capture_hint.setText("Return to Connect: confirm the setup and pass Test connection before recording. "
                                      + f"Keep fixed: {self.fixed_notes.text()}")

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
            self.train_log.setVisible(True)
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
            self.train_log.setVisible(True)
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

    def _refresh_runs(self):
        selected = self.run_combo.currentData()
        self.run_combo.blockSignals(True)
        self.run_combo.clear()
        folder = self.project_dir / "outputs" if self.project_dir else None
        if folder and folder.is_dir():
            runs = (p for p in folder.iterdir() if p.is_dir() and (p / "manifest.json").is_file())
            for run in sorted(runs, key=lambda p: (p / "manifest.json").stat().st_mtime_ns, reverse=True):
                self.run_combo.addItem(run.name, str(run))
        index = self.run_combo.findData(selected)
        self.run_combo.setCurrentIndex(index if index >= 0 else 0)
        self.run_combo.blockSignals(False)
        self._show_run()

    @staticmethod
    def _run_json(run, name):
        try:
            value = json.loads((run / name).read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _exported_run(self):
        data = self.run_combo.currentData()
        run = Path(data) if data else None
        return run if run and (run / "model_parametric.nam").is_file() else None

    def _show_run(self, *args):
        data = self.run_combo.currentData()
        run = Path(data) if data else None
        exported = self._exported_run()
        state = self._run_json(run, "status.json") if run else {}
        reviewed = self._run_json(run, "review.json").get("listened", False) if run else False
        self.review_status.setText("Model exported · listening recorded" if exported and reviewed else "Model exported · needs listening" if exported else f"Run: {state.get('status', 'configs saved; no export')}" if run else "No saved training runs yet.")
        self.model_path.setText(str(run / "model_parametric.nam") if exported else state.get("error", "Capture and train a project to create a model."))
        metrics = self._run_json(run, "metrics.json") if run else {}
        esr = metrics.get("ESR")
        self.review_metric.setText(f"Last logged validation ESR: {esr:.6g} · epoch {metrics.get('epoch')}\nThis is the last epoch, not a separate evaluation of the exported checkpoint. Lower is better; listen too." if isinstance(esr, (int, float)) else "No validation metric recorded for this run. Inspect training.log for details.")
        self.review_check.blockSignals(True)
        self.review_check.setChecked(bool(reviewed))
        self.review_check.blockSignals(False)
        self.review_note.setText("Listening is your assessment, not an automatic quality certification.")
        self.save_model_button.setEnabled(exported is not None)
        self.folder_button.setEnabled(run is not None)
        self.recordings_button.setEnabled(self.project_dir is not None)
        self._sync_states()

    def _save_review(self, checked):
        run = self._exported_run()
        if run and not self._busy():
            try:
                atomic_write_json(run / "review.json", {"listened": checked})
            except OSError as exc:
                self.review_note.setText(f"Could not save listening status: {exc}")
                return
            self._show_run()

    def _save_model(self):
        if self._busy():
            return
        run = self._exported_run()
        if run:
            dest, _ = QFileDialog.getSaveFileName(self, "Save parametric model", f"{self.project.name if self.project else 'pedal'}-parametric.nam", "NAM model (*.nam)")
            if dest:
                source = run / "model_parametric.nam"
                try:
                    if Path(dest).resolve() != source.resolve():
                        shutil.copy2(source, dest)
                    self.review_note.setText(f"Model saved to {dest}. Load it in NamParametricPlugin.")
                except OSError as exc:
                    self.review_note.setText(f"Could not save model: {exc}")

    def _open_outputs(self):
        data = self.run_combo.currentData()
        if data:
            QDesktopServices.openUrl(QUrl.fromLocalFile(data))

    def _open_recordings(self):
        if self.project_dir:
            # Captures are named val_lhs_* for held-out settings, alongside training WAVs.
            folder = self.project_dir / "captures"
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            self.review_note.setText("Unseen test recordings are the val_lhs_*.wav files. Their exact settings are in the capture queue.")

    def closeEvent(self, event):
        if self.process or self._worker:
            QMessageBox.information(self, "Job running", "Stop the job or cancel the recording and wait before closing.")
            event.ignore()
            return
        super().closeEvent(event)


def launch(train_tab=False):
    app = QApplication.instance() or QApplication(sys.argv)
    window = MacWindow()
    if train_tab:
        window.go_to(3)
    window.show()
    return app.exec()
