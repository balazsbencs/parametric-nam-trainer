"""Plan page."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSlider, QTableWidgetItem,
    QSizePolicy, QStyleOptionSlider, QStyle,
)
from nam.capture.project import save_project
from ...controls import SwitchSpec, switch_combinations
from nam.capture.session import CaptureSession
from ...workflow import QUALITIES, quality_settings, make_plan, recording_minutes, write_state
from ..widgets.common import Themed, themed, label, button, disclosure


class CoverageSlider(Themed, QSlider):
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
        p = self._palette
        for start, end, color in [(left,left+segment,p.warn),
                                  (left+segment+6,right-segment-6,p.ok),
                                  (right-segment,right,p.line_strong)]:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color if self.isEnabled() else p.line))
            painter.drawRoundedRect(QRectF(start,center.y()-3.5,end-start,7),3,3)
        painter.setBrush(QColor(p.accent_fill if self.isEnabled() else p.muted))
        painter.setPen(QPen(QColor(p.bg),3))
        painter.drawEllipse(QPointF(center),11,11)
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(p.accent_text),1))
            painter.drawEllipse(QPointF(center),14,14)


class QualityStops(Themed, QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(48)
        self.setAccessibleName("Quick test: setup only; Decent: starting point; Good: recommended; Thorough: more detail; Overkill: diminishing returns")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(self._palette.muted))
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        hints = ("Setup only", "Starting point", "Recommended", "More detail", "Little extra")
        for i, quality in enumerate(QUALITIES):
            x = 13 + (self.width() - 26) * i / 4
            rect = QRectF(max(0, min(self.width()-104, x-52)), 0, 104, 44)
            align = Qt.AlignLeft if i == 0 else Qt.AlignRight if i == 4 else Qt.AlignHCenter
            painter.drawText(rect, align | Qt.AlignTop, quality.name + "\n" + hints[i])


class PlanPageMixin:
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
        self.quality_recommendation.setProperty('tag', 'ok')
        self.quality_recommendation.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        quality_heading = QHBoxLayout()
        quality_heading.addWidget(self.quality_name)
        quality_heading.addWidget(self.quality_recommendation)
        quality_heading.addStretch()
        layout.addLayout(quality_heading)
        self.quality_description = label(QUALITIES[2].description, 'muted')
        layout.addWidget(self.quality_description)
        layout.addSpacing(20)
        self.quality_slider = themed(CoverageSlider(Qt.Horizontal), self.appearance)
        self.quality_slider.setRange(0, 4)
        self.quality_slider.setValue(2)
        self.quality_slider.setTickInterval(1)
        self.quality_slider.setTickPosition(QSlider.NoTicks)
        self.quality_slider.setAccessibleName("Capture quality")
        self.quality_slider.setMinimumHeight(40)
        self.quality_slider.valueChanged.connect(self._apply_quality)
        layout.addWidget(self.quality_slider)
        layout.addWidget(themed(QualityStops(), self.appearance))
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
        from ...controls import boundary_settings
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
