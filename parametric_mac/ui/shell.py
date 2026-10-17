"""Window shell: page stack, navigation and shared state refresh."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox, QStackedWidget, QMenu,
    QScrollArea,
)
from ..controls import format_controls
from .widgets.common import PAGE_MARGIN, themed, label, PageScroll
# StepBar is re-exported: tests and later pages import it from here.
from .widgets.shell_bars import Footer, Step, StepBar, TopBar  # noqa: F401

# Transitional order: later page tasks edit only this tuple (final: start, gear, connect, record, train, listen).
STEPS: tuple[Step, ...] = (
    Step("start", "Start", False),
    Step("gear", "Gear", True),
    Step("connect", "Connect", True),
    Step("plan", "Plan", True),
    Step("capture", "Capture", True),
    Step("train", "Train", True),
    Step("review", "Review", True),
)
STEP_KEYS = tuple(step.key for step in STEPS)
# Final step names that do not exist yet in the transitional STEPS (removed by Tasks 7, 9 and 12).
STEP_ALIASES = {"record": "capture", "listen": "review"}
APPEARANCE_CHOICES = (("system", "Match macOS"), ("light", "Light"), ("dark", "Dark"))


class ShellMixin:
    def _build_ui(self):
        # Build upstream controls once, then place those exact controls in the new flow.
        # Their signal connections, device polling, recorder and QA remain intact.
        super()._build_ui()
        self._prepare_legacy()
        self._build_shell()
        self._build_pages()
        self._build_menus()
        self._wire_signals()
        self.go_to_step("start")

    def _prepare_legacy(self):
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

    def _build_shell(self):
        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.top_bar = TopBar(STEPS)
        for step_button in self.top_bar.step_bar.buttons():
            themed(step_button, self.appearance)
        self.top_bar.step_bar.selected.connect(self.go_to_step)
        self.top_bar.brand_button.clicked.connect(lambda: self.go_to_step("start"))
        self.project_title = self.top_bar.project_title
        outer.addWidget(self.top_bar)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        content.addWidget(self.pages)
        outer.addWidget(body, 1)
        self.footer = Footer()
        self.activity_label = self.footer.status
        outer.addWidget(self.footer)
        self.setCentralWidget(shell)
        self.statusBar().hide()
        # Upstream still reports some results through the status bar; show them in the footer.
        self.statusBar().messageChanged.connect(lambda text: text and self.footer.set_status(text))

    def _build_pages(self):
        self._build_start_page()
        self._build_gear_page()
        self._connect_page()
        self._plan_page()
        self._capture_page()
        self._train_page()
        self._review_page()
        # Transitional until Task 10: Record keeps one filled button (Record this setting).
        self.capture_continue.setProperty("primary", False)
        self.capture_continue.setProperty("outline", True)
        actions = {"start": None, "gear": self._gear_footer, "connect": self.connect_button, "plan": self.plan_button,
                   "capture": self.capture_continue, "train": self.train_continue, "review": self.save_model_button}
        for key in STEP_KEYS:
            self.footer.add_action(key, actions[key])

    def _build_menus(self):
        group = QActionGroup(self)
        group.setExclusive(True)
        self.appearance_actions = []
        for choice, text in APPEARANCE_CHOICES:
            action = QAction(text, self)
            action.setCheckable(True)
            action.setChecked(self.appearance.choice() == choice)
            action.triggered.connect(lambda checked=False, value=choice: self.appearance.set_choice(value))
            group.addAction(action)
            self.appearance_actions.append(action)
        menu = QMenu(self)
        menu.addActions(self.appearance_actions)
        self.top_bar.appearance_button.setMenu(menu)
        file_menu = self.menuBar().addMenu("File")
        self.new_action = file_menu.addAction("New capture…", lambda: self._start_new_capture())
        self.new_action.setShortcut(QKeySequence.New)
        self.open_action = file_menu.addAction("Open folder…", lambda: self._on_open_project())
        self.open_action.setShortcut(QKeySequence.Open)
        view = self.menuBar().addMenu("View")
        view.addMenu("Appearance").addActions(self.appearance_actions)
        about = self.menuBar().addMenu("Help").addAction("About Parametric")
        about.setMenuRole(QAction.AboutRole)
        about.triggered.connect(self._show_about)

    def _show_about(self):
        QMessageBox.about(self, "About Parametric", f"Parametric capture and training\n{self.version_label.text()}")

    def _wire_signals(self):
        self._mutating = [self.new_button, self.open_button, self.new_action, self.open_action, self.pedal_name,
                          self.device_combo, self.wire_check,
                          self.gear_next_button, self.gear_change_link, self.gear_new_link,
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
        self.pedal_name.editingFinished.connect(self._save_details)
        self.fixed_notes.editingFinished.connect(self._save_details)
        self.pedal_name.textChanged.connect(lambda *_: self._refresh_gear(effort=False))
        self.fixed_notes.textChanged.connect(lambda *_: self._refresh_gear(effort=False))
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
        layout.setContentsMargins(PAGE_MARGIN, 24, PAGE_MARGIN, 24)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(intro, "muted"))
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

    def go_to_step(self, key: str) -> None:
        key = STEP_ALIASES.get(key, key) if key not in STEP_KEYS else key
        self.pages.setCurrentIndex(STEP_KEYS.index(key))
        self.footer.show_step(key)
        if key == "review":
            self._refresh_runs()
        if key == "start":
            self._refresh_recent()
        self._refresh_steps()
        self.footer.set_status(self._status_text())

    def go_to(self, index: int) -> None:
        """Old index-based navigation, in STEPS order."""
        self.go_to_step(STEP_KEYS[index])

    def current_step(self) -> str:
        return STEP_KEYS[self.pages.currentIndex()]

    def step_states(self) -> dict[str, str]:
        done, current = self._done_steps(), self.current_step()
        return {key: "current" if key == current else "done" if key in done else "todo" for key in STEP_KEYS}

    def _done_steps(self) -> set[str]:
        project = getattr(self, "project", None)
        complete = bool(project and project.entries and not project.pending_entries())
        flags = {"start": getattr(self, "project_dir", None) is not None,
                 "gear": getattr(self, "project_dir", None) is not None,
                 "connect": bool(project) and self._route_ready(),
                 "plan": bool(project and project.entries), "capture": complete,
                 "train": self._exported_run() is not None, "review": False}
        return {key for key, value in flags.items() if value}

    def _refresh_steps(self) -> None:
        if not hasattr(self, "top_bar") or not hasattr(self, "run_combo"):
            return
        bar = self.top_bar.step_bar
        bar.set_states(self.step_states())
        numbered = [step.key for step in STEPS if step.numbered]
        bar.set_enabled_steps(set(numbered) if getattr(self, "project_dir", None) else {numbered[0]})

    def _status_text(self) -> str:
        if self.process:
            return "Checking recordings…" if self.command == "check" else "Training in progress…"
        if self._worker:
            return "Audio operation running…"
        if not self.project:
            starting = hasattr(self, "pages") and self.current_step() in ("start", "gear")
            return "" if starting else "Go to Start to create or open a project."
        if not self.project.entries:
            return "No recordings planned yet"
        return f"{len(self.project.captured_entries())} of {len(self.project.entries)} recordings saved"

    def _refresh_all(self):
        super()._refresh_all()
        if not self._ready:
            return
        self.project_title.setText((self.project.name or self.project_dir.name) if self.project else
                                   self.project_dir.name if self.project_dir else "No project open")
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
        self.confirm_knobs.setChecked(False)
        self._sync_states()

    def _refresh_status_bar(self):
        if hasattr(self, "footer"):
            self.footer.set_status(self._status_text())

    def _sync_states(self, *args):
        if not self._ready:
            return
        self._refresh_rates()
        busy = self._busy()
        for widget in self._mutating:
            widget.setEnabled(not busy)
        self.audio_advanced.setEnabled(not busy)
        locked = self._plan_locked()
        self.advanced_plan_hint.setText("These are the saved settings used to label this project’s recordings." if locked else
                                        "Manual changes show Custom. Moving the quality slider restores preset counts and steps, while keeping physical ranges and knob roles.")
        for widget in (self.quality_slider, self.plan_advanced, self.control_editor, self.gear_kind, self.fixed_notes, self.pedal_name):
            widget.setEnabled(not busy and not locked)
        self.plan_lock_label.setText("This plan is locked because recording has started. Create a separate project to change quality, knobs or levels." if locked else "Go to Start to create or open a project." if not self.project else "")
        self.separate_button.setVisible(locked)
        self.plan_button.setText("Continue capturing" if locked else "Start capturing")
        self.plan_button.setEnabled(not busy and self.project is not None and self._preview is not None)
        self.connect_button.setEnabled(not busy and self.project is not None and self._route_ready())
        self.route_test_button.setEnabled(not busy and self._has_device() and self.wire_check.isChecked()
                                          and self._rate_problem() is None)
        self._sync_connect()
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
        self.footer.set_status(self._status_text())
        self._sync_recent_rows()
        self._sync_gear_lock()
        self._refresh_steps()
        if self.project and self.project.entries and not self._route_ready() and not busy:
            self.capture_hint.setText("Go to Connect and check the level before recording. "
                                      + f"Keep fixed: {self.fixed_notes.text()}")

    def closeEvent(self, event):
        if self.process or self._worker:
            QMessageBox.information(self, "Job running", "Stop the job or cancel the recording and wait before closing.")
            event.ignore()
            return
        super().closeEvent(event)
