"""Capture page."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
)
from ...controls import format_controls
from ...workflow import write_state
from ..widgets.common import themed, label, button, disclosure, Columns
from ..widgets.knobs import KnobTargets


class CapturePageMixin:
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
        self.knob_targets = themed(KnobTargets(), self.appearance)
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
