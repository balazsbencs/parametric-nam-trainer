"""The recording loop: set the shown positions, press Record, read the take check, repeat."""
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QHBoxLayout, QLineEdit, QPlainTextEdit,
                               QProgressBar, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget)

from ...controls import format_controls
from ...theme import mono_font
from ...workflow import write_state
from ..copy import take_message
from ..widgets.common import PAGE_MARGIN, AlertBox, PageScroll, button, disclosure, label, set_style_property, themed
from ..widgets.knobs import TargetControls, changed_controls

TEXT_INPUTS = (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)
SECONDS_TO_SET = 10  # the same allowance as workflow.recording_minutes


class RecordLoopMixin:
    def _build_record_loop(self) -> QWidget:
        self._shown_entry = self._retry_entry = self._recording_entry = None
        self._last_params = None
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(PageScroll.NoFrame)
        scroll.setFocusPolicy(Qt.StrongFocus)
        content = QWidget()
        content.setObjectName("page")
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        columns.addWidget(self._loop_main(), 3)
        columns.addWidget(self._loop_aside(), 2)
        scroll.setWidget(content)
        self.capture_continue = button("Next: Train →", lambda: self.go_to_step("train"), True)
        shortcut = QShortcut(QKeySequence(Qt.Key_Space), scroll)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self._space_pressed)
        return scroll

    def _loop_main(self) -> QWidget:
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(PAGE_MARGIN, 28, PAGE_MARGIN, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)
        self.setting_label = label("", "muted")
        self.setting_label.setFont(mono_font(12))
        self.record_title = label("Set your pedal like this", "title")
        self.target_label = label("", "muted")
        self.knob_targets = themed(TargetControls(), self.appearance)
        self.capture_hint = label("", "muted")
        for widget in (self.setting_label, self.record_title, self.target_label, self.knob_targets, self.capture_hint):
            layout.addWidget(widget)
        self.take_alert = AlertBox()
        self.take_alert_new_capture = button("Start a new capture with these controls", lambda: self._new_capture_from_gear())
        self.take_alert_new_capture.setProperty("link", True)
        self.take_alert.actions.addWidget(self.take_alert_new_capture)
        self.take_alert_keep = button("Keep this take and continue", self._keep_take)
        self.take_alert_keep.setProperty("link", True)
        self.take_alert.actions.addWidget(self.take_alert_keep)
        self.take_alert.actions.addStretch()
        layout.addWidget(self.take_alert)
        row = QHBoxLayout()
        self.record_button = QPushButton("Record")
        self.record_button.setProperty("outline", True)
        self.record_button.setFocusPolicy(Qt.NoFocus)  # Space goes to the shortcut, never twice
        self.record_button.setMinimumHeight(44)
        self.record_button.clicked.connect(self._record_clicked)
        row.addWidget(self.record_button)
        space_hint = label("or press Space", "muted")
        space_hint.setWordWrap(False)
        space_hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        row.addWidget(space_hint)
        row.addStretch()
        self.change_level_link = button("Change detail level", self._choose_level_again)
        self.change_level_link.setProperty("link", True)
        row.addWidget(self.change_level_link)
        layout.addLayout(row)
        layout.addWidget(self.capture_progress)
        self.capture_progress.hide()
        self.capture_feedback = label("Every take is saved at once. You can close the app and continue later.", "muted")
        layout.addWidget(self.capture_feedback)
        return main

    def _loop_aside(self) -> QWidget:
        aside = QWidget()
        aside.setObjectName("aside")
        aside.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(aside)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(label("Progress", "muted"))
        self.progress_count = label("", "section")
        self.progress_count.setFont(mono_font(13))
        self.progress_count.setAlignment(Qt.AlignRight)
        head.addWidget(self.progress_count)
        layout.addLayout(head)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        self.time_left_label = label("", "muted")
        layout.addWidget(self.time_left_label)
        layout.addSpacing(8)
        layout.addWidget(label("Last take", "muted"))
        self.last_take_label = label("No take yet", "muted")
        layout.addWidget(self.last_take_label)
        layout.addSpacing(8)
        layout.addWidget(label("Up next", "muted"))
        self.up_next_labels = [label("", "") for _ in range(2)]
        for item in self.up_next_labels:
            item.setProperty("listRow", True)
            layout.addWidget(item)
        layout.addStretch()
        disclosure(layout, "All takes", self._all_takes_panel())
        return aside

    def _all_takes_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("Select a take to see its positions, then record it again.", "muted"))
        layout.addWidget(self.capture_table)
        self.capture_table.itemSelectionChanged.connect(self._show_selected_target)
        self.capture_selected_button.setText("Record this one again")
        self.capture_selected_button.clicked.disconnect()
        self.capture_selected_button.clicked.connect(self._record_selected)
        row = QHBoxLayout()
        row.addWidget(self.capture_selected_button)
        row.addWidget(self.check_captures_button)
        layout.addLayout(row)
        layout.addWidget(self.capture_log)
        self.export_concat_button.setText("Export training configs")
        tools = QHBoxLayout()
        tools.addWidget(self.clear_captures_button)
        tools.addWidget(self.export_concat_button)
        layout.addLayout(tools)
        return panel

    # ---- actions --------------------------------------------------------------------

    def _record_clicked(self) -> None:
        if self._worker is not None:
            self._on_cancel_capture()
            return
        entry = self._retry_entry or self._shown_entry
        if entry is not None:
            self._begin_capture(entry)

    def _record_selected(self) -> None:
        row = self.capture_table.currentRow()
        if 0 <= row < len(self._displayed_entries):
            self._retry_entry = self._displayed_entries[row]
            self._show_target(self._retry_entry)
            self._begin_capture(self._retry_entry)

    def _space_pressed(self) -> None:
        if self.current_step() != "record" or self.record_stack.currentWidget() is not self.record_loop:
            return
        if isinstance(QApplication.focusWidget(), TEXT_INPUTS) or not self.record_button.isEnabled():
            return
        if self._worker is not None:  # A quick double press must not cancel the take; Cancel stays on the button.
            return
        self._record_clicked()

    def _begin_capture(self, entry):
        if self._busy() or not self._route_ready():
            return
        # Record always captures what the page shows: a different entry is shown first, never recorded blind.
        if self._shown_entry is None or entry.params != self._shown_entry.params or entry.split != self._shown_entry.split:
            self._show_target(entry)
            self.capture_feedback.setText("Check these positions, then press Record.")
            return
        self._recording_entry = entry
        self.capture_feedback.setText("Recording… Keep your gear still until this take is saved.")
        self.capture_progress.show()
        super()._begin_capture(entry)
        self._sync_states()

    def _on_capture_success(self, qa):
        self._workflow["plan_locked"] = True
        write_state(self.project_dir, self._workflow)
        for message in qa.messages:
            self.capture_log.appendPlainText(f"QA: {message}")
        # The take alert replaces upstream's modal QA box, so upstream gets no messages to show.
        super()._on_capture_success(qa.model_copy(update={"messages": []}))
        self._show_take_result(qa, self._recording_entry)
        self._refresh_preview()

    def _show_take_result(self, qa, recorded) -> None:
        message = take_message(qa.clipping, qa.messages)
        peak = f" · Peak {qa.peak:.1f} dB".replace("-", "−") if qa.peak is not None else ""
        self.last_take_label.setText(message.title + peak)
        set_style_property(self.last_take_label, "role", {"ok": "ok", "clipped": "danger"}.get(message.kind, "warn"))
        self.capture_progress.hide()
        if recorded is not None:  # The knobs now sit at these positions, whatever the check says.
            self._last_params = dict(recorded.params)
        if message.kind == "ok" or recorded is None:
            self.take_alert.hide()
            self._retry_entry = None
            self._show_next_target()
            return
        self.take_alert.show_message(message.title, message.body, "error" if message.kind == "clipped" else "warning")
        self.take_alert_new_capture.setVisible(message.kind == "clipped")
        self.take_alert_keep.setVisible(message.kind == "warning")
        self._retry_entry = recorded
        self._show_target(recorded)
        self._sync_states()

    def _keep_take(self) -> None:
        """A warning is advisory: the user may keep the saved take and move on. Clipped takes cannot."""
        self._retry_entry = None
        self.take_alert.hide()
        self._show_next_target()
        self._sync_states()

    def _on_capture_failure(self, message):
        self.capture_progress.hide()
        self.take_alert.show_message("Take not saved", "The take did not finish. Check the cables, then record it again.")
        self.take_alert_new_capture.hide()
        self.take_alert_keep.hide()
        self._retry_entry = self._recording_entry
        super()._on_capture_failure(message)

    def _on_capture_cancelled(self):
        self.capture_progress.hide()
        self.capture_feedback.setText("Recording cancelled. This setting is still waiting.")
        super()._on_capture_cancelled()

    def _show_selected_target(self):
        row = self.capture_table.currentRow()
        if 0 <= row < len(self._displayed_entries):
            self._show_target(self._displayed_entries[row])
            self.capture_feedback.setText("This is a saved take. Use Record this one again to replace it.")
        self._sync_states()

    # ---- display --------------------------------------------------------------------

    def _reset_record_loop(self) -> None:
        """Another project: no shown, retried or recording take, no alert."""
        if not hasattr(self, "record_button"):
            return
        self._shown_entry = self._retry_entry = self._recording_entry = None
        self._last_params = None
        self.take_alert.hide()
        self.last_take_label.setText("No take yet")

    def _show_target(self, entry) -> None:
        self._shown_entry = entry
        specs = self.project.knob_specs() if self.project else ()
        changed = changed_controls(self._last_params, entry.params) if entry is not None else frozenset()
        self.knob_targets.set_targets(entry, specs, changed)
        total = len(self.project.entries) if self.project else 0
        if entry is None:
            self.setting_label.setText("ALL TAKES SAVED")
            self.record_title.setText(f"All {total} takes are saved." if total else "No takes planned yet.")
            self.target_label.setText("")
            self.capture_hint.setText("")
            return
        order = self._setting_number(entry)
        self.setting_label.setText(f"SETTING {order} / {total}")
        self.record_title.setText("Set your amp like this" if self.gear_kind.currentIndex() else "Set your pedal like this")
        self.target_label.setText(format_controls(entry.params, specs))
        self.capture_hint.setText(("Test setting" if entry.split == "validation" else "Training setting")
                                  + f" · Keep fixed: {self.fixed_notes.text()}")

    def _setting_number(self, entry) -> int:
        """The take number in recording order, also for a take that is recorded again."""
        order = self._entries_in_display_order()
        for position, candidate in enumerate(order, start=1):
            if candidate is entry or (candidate.params == entry.params and candidate.split == entry.split):
                return position
        return len(self.project.captured_entries()) + 1

    def _show_next_target(self) -> None:
        self._show_target(self._next_pending_entry() if self.project else None)
        self._show_up_next()

    def _show_up_next(self) -> None:
        pending = [e for e in self._entries_in_display_order() if e.status == "pending" and e is not self._shown_entry]
        specs = self.project.knob_specs()
        for item, entry in zip(self.up_next_labels, pending[:2] + [None, None]):
            item.setText(format_controls(entry.params, specs) if entry is not None else "")
            item.setVisible(entry is not None)

    def _refresh_record_loop(self) -> None:
        if not hasattr(self, "record_button") or not self.project:
            return
        captured, total = len(self.project.captured_entries()), len(self.project.entries)
        self.progress_count.setText(f"{captured} / {total}")
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(captured)
        pending = self.project.pending_entries()
        train_s, test_s = self._input_durations()
        minutes = math.ceil(sum((train_s if e.split == "train" else test_s) + SECONDS_TO_SET for e in pending) / 60)
        self.time_left_label.setText(f"About {minutes} minutes left · saved after every take" if pending else "Every take is saved.")
        if self._worker is None and self._retry_entry is None:
            self._show_next_target()

    def _sync_record_loop(self, busy: bool, can_record: bool, complete: bool) -> None:
        if not hasattr(self, "record_button"):
            return
        recording = self._worker is not None
        self.record_button.setText("Cancel" if recording else "Record again" if self._retry_entry else "Record")
        target = self._retry_entry or self._shown_entry
        self.record_button.setEnabled(self._cancel_token is not None if recording else can_record and target is not None)
        self.capture_selected_button.setEnabled(can_record and self.capture_table.currentRow() >= 0)
        self.capture_continue.setEnabled(complete and not busy)
        self.change_level_link.setVisible(bool(self.project and self.project.entries) and not self._plan_locked())
        if self.project and self.project.entries and not self._route_ready() and not busy:
            self.capture_hint.setText("Go to Connect and check the level before recording. "
                                      + f"Keep fixed: {self.fixed_notes.text()}")
