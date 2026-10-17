"""Window shell: page stack, navigation and shared state refresh."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QStackedWidget,
    QScrollArea,
)
from ..controls import format_controls
from .widgets.common import themed, label, button, StageButton, PageScroll


STAGES = ("Connect", "Plan", "Capture", "Train", "Review")


class ShellMixin:
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
            warning.setProperty("role", "warn")

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
            nav = themed(StageButton(i, stage, ("Audio & wiring", "Controls & coverage", "Record your gear", "Build the model", "Check & export")[i],
                              lambda checked=False, index=i: self.go_to(index)), self.appearance)
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
        self.stage_actions.setObjectName("stageActions")
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

    def go_to(self, index):
        self.pages.setCurrentIndex(index)
        if hasattr(self, "stage_actions"):
            self.stage_actions.setCurrentIndex(index)
        for i, nav in enumerate(self.nav_buttons):
            nav.setChecked(i == index)
        if index == 4:
            self._refresh_runs()

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
                row.setProperty('listRow', True)
                self.queue_rows.addWidget(row)
            if not entries:
                self.queue_rows.addWidget(label('All planned takes are saved.' if self.project.entries else 'Create a capture plan to see the next settings.', 'muted'))
            self.sidebar_summary.setText(f'{len(self.control_editor.controls)} controls · mono')
        self.confirm_knobs.setChecked(False)
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

    def closeEvent(self, event):
        if self.process or self._worker:
            QMessageBox.information(self, "Job running", "Stop the job or cancel the recording and wait before closing.")
            event.ignore()
            return
        super().closeEvent(event)
