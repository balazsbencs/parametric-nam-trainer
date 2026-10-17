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
from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QUrl, QRectF, QPointF, QSize
from PySide6.QtGui import QDesktopServices, QPainter, QPen, QColor, QPalette, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QPlainTextEdit, QMessageBox, QStackedWidget,
    QScrollArea, QSlider, QCheckBox, QLineEdit, QFileDialog, QTableWidgetItem,
    QProgressBar, QSizePolicy, QBoxLayout, QLayout, QToolButton, QButtonGroup, QStyleOptionSlider, QStyle,
)
from nam.capture.gui.main import MainWindow, knob_rows_to_specs
from nam.capture.project import save_project, atomic_write_json
from .controls import ControlProject as CaptureProject, ControlModel, SwitchSpec, load_project, format_controls, model_config, switch_combinations
from .control_editor import ControlEditor, starter
from nam.capture.session import CaptureSession
from .assets import FILES
from .theme import install_typography, icon
from .ui.style import AppearanceController, settings_from_env
from .workflow import QUALITIES, quality_settings, make_plan, recording_minutes, read_state, write_state

STAGES = ("Connect", "Plan", "Capture", "Train", "Review")


def label(text, role=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    policy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    policy.setHeightForWidth(True)
    widget.setSizePolicy(policy)
    widget.setTextFormat(Qt.PlainText)
    if role:
        widget.setProperty("role", role)
    if role == 'title':
        font = widget.font()
        font.setLetterSpacing(QFont.AbsoluteSpacing, -.6)
        widget.setFont(font)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    widget.clicked.connect(callback)
    return widget


def disclosure(layout, title, widget):
    toggle = QToolButton()
    toggle.setText(title)
    toggle.setProperty('disclosure', True)
    toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    toggle.setIcon(icon('chevron-right'))
    toggle.setIconSize(QSize(12, 12))
    toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    toggle.setCheckable(True)
    toggle.setAccessibleName(title)
    widget.setVisible(False)
    def reveal(opened):
        toggle.setIcon(icon('chevron-down' if opened else 'chevron-right'))
        widget.setVisible(opened)
    toggle.toggled.connect(reveal)
    layout.addWidget(toggle)
    layout.addWidget(widget)
    return toggle


def field(caption, widget):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    title = label(caption)
    title.setStyleSheet('font-size: 12px;')
    title.setBuddy(widget)
    widget.setAccessibleName(caption)
    layout.addWidget(title)
    layout.addWidget(widget)
    return container


class TrainingProfiles(QWidget):
    def __init__(self, combo):
        super().__init__()
        self.setObjectName('profiles')
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.buttons = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(('Full training', 'Quick test', 'Custom')):
            choice = QPushButton(text)
            choice.setProperty('profile', True)
            choice.setCheckable(True)
            choice.setAccessibleName(combo.itemText(i))
            choice.clicked.connect(lambda checked=False, index=i: combo.setCurrentIndex(index))
            self.group.addButton(choice, i)
            layout.addWidget(choice, 1)
            self.buttons.append(choice)
        def selected(index):
            for i, choice in enumerate(self.buttons):
                choice.setChecked(i == index)
                choice.setAccessibleName(combo.itemText(i))
        combo.currentIndexChanged.connect(selected)
        combo.currentTextChanged.connect(lambda _: selected(combo.currentIndex()))
        selected(combo.currentIndex())


class StageButton(QPushButton):
    def __init__(self, index, stage, detail, callback):
        super().__init__()
        self.index, self.stage, self.detail = index, stage, detail
        self.setProperty('nav', True)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.TabFocus)
        self.setMinimumHeight(62)
        self.clicked.connect(callback)
        self.setAccessibleName(f'{stage} stage: {detail}')

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        active = self.isChecked()
        painter.setPen(QPen(QColor('#175cd3' if active else '#b8c2d3'), 1))
        painter.setBrush(QColor('#175cd3') if active else Qt.NoBrush)
        painter.drawEllipse(QRectF(12, 15, 16, 16))
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor('#ffffff' if active else '#606773'))
        painter.drawText(QRectF(12, 15, 16, 16), Qt.AlignCenter, str(self.index + 1))
        font.setPixelSize(14)
        font.setWeight(QFont.DemiBold if active else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor('#175cd3' if active else '#252a32'))
        painter.drawText(QRectF(40, 10, self.width()-46, 22), Qt.AlignLeft | Qt.AlignVCenter, self.stage)
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor('#606773'))
        painter.drawText(QRectF(40, 32, self.width()-46, 20), Qt.AlignLeft | Qt.AlignVCenter, self.detail)


class Columns(QWidget):
    """The mockup's working area and reference column, stacked on narrow windows."""
    def __init__(self, parent_layout):
        super().__init__()
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.box.setSizeConstraint(QLayout.SetNoConstraint)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(28)
        self.box.setAlignment(Qt.AlignTop)
        self.columns = []
        for _ in range(2):
            panel = QWidget()
            policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            policy.setHeightForWidth(True)
            panel.setSizePolicy(policy)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            layout.setSizeConstraint(QLayout.SetNoConstraint)
            layout.setAlignment(Qt.AlignTop)
            self.box.addWidget(panel, 1, Qt.AlignTop)
            self.columns.append(layout)
        parent_layout.addWidget(self)

    def reflow(self, available):
        direction = QBoxLayout.TopToBottom if available < 780 else QBoxLayout.LeftToRight
        if self.box.direction() != direction:
            self.box.setDirection(direction)
            for index in range(self.box.count()):
                self.box.setStretch(index, 0 if direction == QBoxLayout.TopToBottom else 1)
            self.updateGeometry()


class PageScroll(QScrollArea):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        for columns in self.findChildren(Columns):
            columns.reflow(self.viewport().width() - 16)




class KnobTargets(QWidget):
    """Read-only physical dial positions, never software controls."""
    def __init__(self):
        super().__init__()
        self.targets = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setAccessibleName("Physical knob positions")

    def set_targets(self, entry, knobs):
        self.targets = [(k, entry.params[k.name]) for k in knobs if not isinstance(k, SwitchSpec)] if entry else []
        self.setAccessibleDescription(", ".join(f"{k.name} {v:g}, range {k.min:g} to {k.max:g}" for k, v in self.targets))
        self._size_targets()
        self.update()

    def _size_targets(self):
        columns = max(1, min(3, self.width() // 170))
        self.setMinimumHeight(math.ceil(len(self.targets) / columns) * 190)
        self.setVisible(bool(self.targets))
        self.updateGeometry()

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
            top = row * 190
            center = QPointF(width * (col + .5), top + 72)
            font = painter.font()
            font.setPixelSize(12)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor('#252a32'))
            painter.drawText(QRectF(col*width, top, width, 20), Qt.AlignCenter, knob.name)
            painter.setPen(QPen(QColor('#d2ddec'), 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(QRectF(center.x()-48, center.y()-48, 96, 96), 225*16, -270*16)
            painter.setBrush(QColor('#f3f6fb'))
            painter.setPen(QPen(QColor('#d2ddec'), 1.2))
            painter.drawEllipse(center, 37, 37)
            angle = math.radians(225 - 270 * (value - knob.min) / (knob.max - knob.min))
            direction = QPointF(math.cos(angle), -math.sin(angle))
            painter.setPen(QPen(QColor('#175cd3'), 2.5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(center + direction*20, center + direction*37)
            font.setPixelSize(11)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor('#606773'))
            painter.drawText(QRectF(center.x()-54, top+112, 45, 18), Qt.AlignLeft, f'{knob.min:g}')
            painter.drawText(QRectF(center.x()+9, top+112, 45, 18), Qt.AlignRight, f'{knob.max:g}')
            font.setPixelSize(30)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor('#252a32'))
            painter.drawText(QRectF(col*width, top+132, width, 35), Qt.AlignCenter, f'{value:g}')
            font.setPixelSize(11)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor('#606773'))
            painter.drawText(QRectF(col*width, top+170, width, 18), Qt.AlignCenter, 'Physical knob position')


class CoverageSlider(QSlider):
    def paintEvent(self, event):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        center = handle.center()
        half = handle.width()/2
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left, right = half, self.width()-half
        segment = (right-left-12)/4
        for start, end, color in [(left,left+segment,'#e2c79e'),
                                  (left+segment+6,right-segment-6,'#b6d2c1'),
                                  (right-segment,right,'#d3d9e2')]:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color if self.isEnabled() else '#e1e5ec'))
            painter.drawRoundedRect(QRectF(start,center.y()-3.5,end-start,7),3,3)
        painter.setBrush(QColor('#175cd3' if self.isEnabled() else '#929aa6'))
        painter.setPen(QPen(QColor('#ffffff'),3))
        painter.drawEllipse(QPointF(center),11,11)
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor('#175cd3'),1))
            painter.drawEllipse(QPointF(center),14,14)


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
        install_typography()
        # Created before super().__init__(): upstream builds the pages there, and pages read the palette.
        self.settings = settings_from_env()
        self.appearance = AppearanceController(QApplication.instance(), self.settings)
        super().__init__()
        self.setWindowTitle("Parametric — capture & training")
        # QMacStyle defaults squeeze fields and center forms. Make geometry explicit.
        for form in self.findChildren(QFormLayout):
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for field in self.findChildren((QLineEdit)) + self.findChildren(QComboBox):
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.version_label.setText("NAM engine " + self.version_label.text())
        self.resize(1140, 840)
        self.setMinimumSize(760, 580)
        self._ready = True
        self._applying = False
        self.loopback_check.setChecked(False)
        self._mirror_controls()
        self._apply_quality(2)
        self._refresh_all()
        for progress in self.findChildren(QProgressBar):
            progress.setTextVisible(False)
        self.centralWidget().setFocusPolicy(Qt.StrongFocus)
        self.centralWidget().setFocus(Qt.OtherFocusReason)

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
            warning.setProperty("role", "muted")
            warning.setStyleSheet("color: #925517;")

        shell = QWidget()
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 24, 16, 20)
        side.addWidget(label("Parametric", "section"))
        self.sidebar_summary = label("Knobs & switches · mono", "muted")
        side.addWidget(self.sidebar_summary)
        side.addSpacing(24)
        self.nav_buttons = []
        self.pages = QStackedWidget()
        for i, stage in enumerate(STAGES):
            nav = StageButton(i, stage, ("Audio & wiring", "Controls & coverage", "Record your gear", "Build the model", "Check & export")[i],
                              lambda checked=False, index=i: self.go_to(index))
            side.addWidget(nav)
            self.nav_buttons.append(nav)
        side.addStretch()
        self.activity_label = label("No job running", "muted")
        side.addWidget(self.activity_label)
        side.addWidget(label("A model with real controls.\nCapture several settings.\nTrain one controllable model.", "muted"))
        outer.addWidget(sidebar)
        right = QWidget()
        content = QVBoxLayout(right)
        content.setContentsMargins(30, 16, 30, 12)
        header = QHBoxLayout()
        self.project_title = label("Start a capture project", "section")
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
        self.stage_actions.setStyleSheet("QStackedWidget { border-top: 1px solid #e1e5ec; }")
        content.addWidget(self.stage_actions)
        self.train_tab = 3  # Kept for the Train.command launch option.
        self.go_to(0)

        self._mutating = [self.new_button, self.open_button, self.pedal_name,
                          self.control_editor, self.gear_kind, self.fixed_notes, self.audio_controls,
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
        self.control_editor.changed.connect(self._controls_changed)
        self.gear_kind.currentIndexChanged.connect(self._gear_changed)
        self.review_check.toggled.connect(self._save_review)

    def _page(self, title, intro):
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 24, 8, 24)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(intro, "muted"))
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

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
            symbol.setStyleSheet('border: 1px solid #d2ddec; border-radius: 5px;')
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
        self.connect_button = button("Continue to plan", lambda: self.go_to(1), True)
        layout.addWidget(self.connect_button, alignment=Qt.AlignRight)
        layout.addStretch()

    def _plan_page(self):
        layout = self._page("Choose your capture quality", "One slider sets coverage and dial precision for all your controls. You turn the real knobs when prompted.")
        outer = layout
        quality_panel = QWidget()
        quality_panel.setMaximumWidth(780)
        layout = QVBoxLayout(quality_panel)
        layout.setContentsMargins(24, 30, 24, 18)
        layout.setSpacing(16)
        centered = QHBoxLayout()
        centered.addStretch(0)
        centered.addWidget(quality_panel, 1)
        centered.addStretch(0)
        outer.addLayout(centered)
        layout.addWidget(label('Capture quality', 'section'))
        self.quality_name = label("Good", "quality")
        self.quality_name.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        self.quality_recommendation = label('Recommended')
        self.quality_recommendation.setStyleSheet('color: #25664d; background: #edf6f1; padding: 5px 9px; border-radius: 4px;')
        self.quality_recommendation.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        quality_heading = QHBoxLayout()
        quality_heading.addWidget(self.quality_name)
        quality_heading.addWidget(self.quality_recommendation)
        quality_heading.addStretch()
        layout.addLayout(quality_heading)
        self.quality_description = label(QUALITIES[2].description, 'muted')
        layout.addWidget(self.quality_description)
        layout.addSpacing(20)
        self.quality_slider = CoverageSlider(Qt.Horizontal)
        self.quality_slider.setRange(0, 4)
        self.quality_slider.setValue(2)
        self.quality_slider.setTickInterval(1)
        self.quality_slider.setTickPosition(QSlider.NoTicks)
        self.quality_slider.setAccessibleName("Capture quality")
        self.quality_slider.setMinimumHeight(40)
        self.quality_slider.valueChanged.connect(self._apply_quality)
        layout.addWidget(self.quality_slider)
        layout.addWidget(QualityStops())
        self.effort_label = label("", "section")
        layout.addWidget(self.effort_label)
        layout = outer
        self.plan_summary = label("", "muted")
        layout.addWidget(self.plan_summary)
        layout.addWidget(label("Coverage is a starting point, not a promise of sound quality. Training time is separate. "
                               "Listen at unseen settings before deciding your model is finished.", "muted"))
        self.plan_lock_label = label("")
        layout.addWidget(self.plan_lock_label)
        self.plan_advanced = QWidget()
        extra = QVBoxLayout(self.plan_advanced)
        extra.setContentsMargins(0, 8, 0, 8)
        extra.addWidget(label("Sampling settings", "section"))
        extra.addWidget(label("Edit physical ranges and switch positions in Connect. With more than eight knobs, boundary captures sweep each knob separately instead of every corner combination.", "muted"))
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
        columns = Columns(layout)
        layout, reference = columns.columns
        layout.parentWidget().setObjectName('route')
        layout.setContentsMargins(20, 18, 20, 18)
        reference.addWidget(label('The capture queue', 'section'))
        self.queue_preview = QWidget()
        self.queue_rows = QVBoxLayout(self.queue_preview)
        self.queue_rows.setContentsMargins(0, 0, 0, 0)
        self.queue_rows.setSpacing(0)
        reference.addWidget(self.queue_preview)
        reference.addWidget(label('Test settings follow training takes. They check how well the model works between recorded positions.', 'muted'))
        self.capture_count = label("Create a plan to begin.", "section")
        layout.addWidget(self.capture_count)
        self.target_label = label("No setting queued", "section")
        layout.addWidget(self.target_label)
        self.knob_targets = KnobTargets()
        layout.addWidget(self.knob_targets)
        self.capture_hint = label("", "muted")
        layout.addWidget(self.capture_hint)
        self.confirm_knobs = QCheckBox("The knobs and switches match these positions")
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
        disclosure(reference, "Queue and recording details", details)
        maintenance = QWidget()
        extra = QVBoxLayout(maintenance)
        extra.addWidget(self.clear_captures_button)
        self.export_concat_button.setText("Export training configs")
        extra.addWidget(self.export_concat_button)
        disclosure(reference, "Advanced capture tools", maintenance)
        self.capture_continue = button("Continue to training", lambda: self.go_to(3), True)
        layout.addWidget(self.capture_continue, alignment=Qt.AlignRight)

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
        from .architectures import ARCHITECTURES
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

    def _review_page(self):
        layout = self._page("Review your model", "An export is the beginning of review. Check unseen settings and listen before sharing it.")
        columns = Columns(layout)
        layout, reference = columns.columns
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
        reference.addWidget(label("Listen to the exported model", "section"))
        reference.addWidget(label("Upload this model in Ardor’s manager, then add it from the modules drawer. "
                               "Ardor supports concat and FiLM exports, including Standard + Nano files. "
                               "NamParametricPlugin supports individual concat exports. "
                               "Use the model’s same knob ranges, and compare against your saved test recordings.", "muted"))
        reference.addWidget(button("Get concat player", lambda: QDesktopServices.openUrl(QUrl("https://github.com/phillipmself/NamParametricPlugin"))), alignment=Qt.AlignLeft)
        reference.addWidget(label("Check low, middle and high positions of each modeled knob; sweep between them and listen for differences, noise and level changes. "
                               "Test settings were held out of training. There is no built-in A/B player in this version.", "muted"))
        self.review_check = QCheckBox("I listened and checked unseen settings")
        reference.addWidget(self.review_check)
        self.review_note = label("", "muted")
        reference.addWidget(self.review_note)
        row = QHBoxLayout()
        self.save_model_button = button("Save model…", self._save_model, True)
        self.folder_button = button("Open run folder", self._open_outputs)
        self.recordings_button = button("Open test recordings", self._open_recordings)
        row.addWidget(self.save_model_button)
        row.addWidget(self.folder_button)
        row.addWidget(self.recordings_button)
        row.addStretch()
        layout.addLayout(row)

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

    def _save_architecture(self, *args):
        from .architectures import is_film, is_dual
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

    def _plan_locked(self):
        # Sticky once any take was accepted, including if a file goes missing later.
        return bool(self.project and (self.project.captured_entries() or self._workflow.get("plan_locked")))

    def _apply_quality(self, level):
        if not self._ready or self._busy() or self._plan_locked():
            return
        try:
            knobs = self.control_editor.controls
            knobs, train, tests = quality_settings(knobs, level)
            self._applying = True
            self.control_editor.controls = knobs
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
        self.quality_name.setText(quality.name if quality else "Custom capture plan")
        self.quality_recommendation.setVisible(self._quality == 2)
        self.quality_description.setText(quality.description if quality else "Advanced settings are active. Move the quality slider to restore a complete preset.")
        if self._plan_locked():
            self.quality_description.setText("Recording has started. Continue with the saved capture settings.")
        try:
            if self._plan_locked():
                self._preview = self.project
            else:
                self._preview = make_plan(self.control_editor.controls, self.n_train_spin.value(),
                                          self.n_validation_spin.value(), self.seed_spin.value(), self.include_corners_check.isChecked())
            train = len(self._preview.entries_for_split("train"))
            tests = len(self._preview.entries_for_split("validation"))
            seconds = self._input_durations()
            self.effort_label.setText(f"{train + tests} recordings · about {recording_minutes(self._preview, *seconds)} minutes")
            self.plan_summary.setText(f"{train} training recordings · {tests} unseen test recordings\n"
                                      + "Modeling: " + ", ".join(k.name for k in self._preview.knob_specs())
                                      + f" · {switch_combinations(self._preview.knob_specs())} switch combination(s)\nKeep fixed: {self.fixed_notes.text()}\nEstimate allows 10 seconds to set controls; breaks and retries add time.")
        except ValueError as exc:
            self._preview = None
            self.effort_label.setText("Adjust your capture settings")
            self.plan_summary.setText(str(exc))
        self._refresh_corner_count()
        self._sync_states()

    def _input_durations(self):
        if self.project and self.project_dir:
            import soundfile as sf
            try:
                return tuple(sf.info(self.project_dir / self.project.input_for_split(s)).duration for s in ("train", "validation"))
            except (OSError, RuntimeError):
                pass
        return 38, 7

    def _refresh_corner_count(self):
        if not hasattr(self, 'corner_count_label') or not hasattr(self, 'control_editor'):
            return
        from nam.capture.planner import corner_capture_count
        from .controls import boundary_settings
        controls = self.control_editor.controls
        knobs = tuple(c for c in controls if not isinstance(c, SwitchSpec))
        if not knobs:
            return
        count = corner_capture_count(knobs) if len(knobs) <= 8 else len(boundary_settings(knobs))
        try:
            count *= switch_combinations(controls)
            self.corner_count_label.setText(f'Up to {count} boundary recordings, before removing duplicates.')
        except ValueError as exc:
            self.corner_count_label.setText(str(exc))

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
        self.sidebar_summary.setText(f'{len(self.control_editor.controls)} controls · mono')

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

    def _on_export_concat_configs(self):
        from nam.capture.export import write_concat_training_configs
        def writer(project, directory):
            selected_model = model_config(project, self.model_architecture.currentData())
            paths = write_concat_training_configs(project, directory)
            # The pinned upstream writer drops enums. Restore typed switch metadata.
            for path in paths:
                if 'model' in Path(path).name:
                    atomic_write_json(path, selected_model)
            return paths
        from .architectures import is_film
        self._export_configs('FiLM A2' if is_film(self.model_architecture.currentData()) else 'ConcatWaveNet', writer)

    def _save_details(self):
        if not self.project or self._busy() or self._plan_locked():
            return
        self.project.name = self.pedal_name.text().strip() or self.project_dir.name
        save_project(self.project, self.project_dir)
        self._workflow["fixed_notes"] = self.fixed_notes.text()
        self._workflow["gear_kind"] = "amp" if self.gear_kind.currentIndex() else "pedal"
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
        self.project = CaptureProject(name=self.pedal_name.text().strip() or directory.name, knobs=[ControlModel.from_spec(c) for c in self.control_editor.controls], audio=audio)
        self.project_dir = directory
        self._train_input_name, self._validation_input_name = "input_train.wav", "input_validation.wav"
        self.session = CaptureSession(self.project, directory)
        self._workflow = {"quality": self._quality, "fixed_notes": self.fixed_notes.text(), "plan_locked": False,
                          "gear_kind": "amp" if self.gear_kind.currentIndex() else "pedal",
                          "model_architecture": self.model_architecture.currentData()}
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
        architecture_index = self.model_architecture.findData(self._workflow.get("model_architecture", "auto"))
        self.model_architecture.setCurrentIndex(max(0, architecture_index))
        if project.captured_entries():
            self._workflow["plan_locked"] = True
            write_state(directory, self._workflow)
        stored_quality = self._workflow.get("quality")
        self._quality = stored_quality if type(stored_quality) is int and 0 <= stored_quality <= 4 else None
        self.pedal_name.setText(project.name)
        self.fixed_notes.setText(self._workflow.get("fixed_notes", "Keep unmodeled controls at their recorded positions"))
        controls = project.knob_specs() or starter()
        if not self._plan_locked() and self._workflow.get('draft_controls'):
            controls = tuple(ControlModel.model_validate(c).to_knob_spec() for c in self._workflow['draft_controls'])
        self.control_editor.set_controls(controls)
        self._mirror_controls()
        self.gear_kind.setCurrentIndex(1 if self._workflow.get("gear_kind") == "amp" else 0)
        self._gear_changed()
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
        self._workflow.pop("draft_controls", None)
        self._workflow.update(quality=self._quality, fixed_notes=self.fixed_notes.text(), plan_locked=False, gear_kind="amp" if self.gear_kind.currentIndex() else "pedal")
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
            self.target_label.setText(format_controls(entry.params, self.project.knob_specs()))
            self.knob_targets.set_targets(entry, self.project.knob_specs())
            self.capture_hint.setText("Selected setting for rerecording. Use Rerecord selected setting below. Record this setting resumes the next pending take.")
        self._sync_states()

    def _begin_capture(self, entry):
        if self._busy() or not self.confirm_knobs.isChecked() or not self._route_ready():
            return
        # A selected row must never confirm a different pending setting.
        expected = format_controls(entry.params, self.project.knob_specs())
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
                                   self.project_dir.name if self.project_dir else "Start a capture project")
        if self.project:
            captured = len(self.project.captured_entries())
            total = len(self.project.entries)
            self.capture_count.setText(f"{captured} of {total} recordings saved" if total else "Choose a capture quality in Plan.")
            entry = self._next_pending_entry()
            self.knob_targets.set_targets(entry, self.project.knob_specs())
            self.target_label.setText(format_controls(entry.params, self.project.knob_specs()) if entry else "All planned settings recorded" if total else "No setting queued")
            self.capture_hint.setText(("Unseen test setting" if entry.split == "validation" else "Training setting") + f" · Keep fixed: {self.fixed_notes.text()}" if entry else "Continue to training when the recordings are ready.")
            self.train_readiness.setText(f"{captured}/{total} recordings saved. " + ("Ready to check and train." if total and captured == total else "Finish your capture plan first."))
        if self.project:
            entries = [e for e in self._entries_in_display_order() if e.status == 'pending'][:5]
            while self.queue_rows.count():
                item = self.queue_rows.takeAt(0)
                item.widget().hide()
                item.widget().deleteLater()
            for i, entry in enumerate(entries):
                text = format_controls(entry.params, self.project.knob_specs()) + '\n' + (
                    'Set these positions next' if i == 0 else 'Unseen test setting' if entry.split == 'validation' else 'Training setting')
                row = label(text, 'muted')
                row.setStyleSheet('padding: 12px 0; border-bottom: 1px solid #e4e6e9;')
                self.queue_rows.addWidget(row)
            if not entries:
                self.queue_rows.addWidget(label('All planned takes are saved.' if self.project.entries else 'Create a capture plan to see the next settings.', 'muted'))
            self.sidebar_summary.setText(f'{len(self.control_editor.controls)} controls · mono')
        self.confirm_knobs.setChecked(False)
        self._sync_states()

    def _refresh_sample_rate_warning(self):
        super()._refresh_sample_rate_warning()
        for warning in (self.sample_rate_warning_label, self.capture_sample_rate_warning_label):
            warning.setText(warning.text().replace('⚠', '').strip())
        if self._ready:
            self._sync_states()

    def _refresh_status_bar(self):
        if not self.project:
            self.status_bar.showMessage("Create or open a project to begin.")
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
        for widget in (self.quality_slider, self.plan_advanced, self.control_editor, self.gear_kind, self.fixed_notes, self.pedal_name):
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
        self.model_architecture.setEnabled(not busy)
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
        if isinstance(metrics.get("tiers"), dict):
            lines = []
            for tier, values in metrics["tiers"].items():
                value = values.get("ESR")
                lines.append(f"{tier.capitalize()}: last validation ESR {value:.6g} · epoch {values.get('epoch')}"
                             if isinstance(value, (int, float)) else f"{tier.capitalize()}: no validation ESR recorded")
            lines.append("Last epochs, not separate evaluations of the exported checkpoints. Listen to both sizes.")
            self.review_metric.setText("\n".join(lines))
        else:
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
                    self.review_note.setText(f"Model saved to {dest}. Upload it in Ardor’s NAM models manager.")
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
