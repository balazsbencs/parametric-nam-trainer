"""Record page: choose how detailed the capture is, then record one setting at a time."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFormLayout, QHBoxLayout, QStackedWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from nam.capture.project import save_project
from nam.capture.session import CaptureSession

from ...controls import SwitchSpec, switch_combinations
from ...workflow import (MAIN_LEVELS, QUALITIES, RECOMMENDED_LEVEL, level_label, make_plan, quality_settings,
                         recording_minutes, write_state)
from ..widgets.common import PAGE_MARGIN, ChoiceCard, PageScroll, button, disclosure, label

CARD_TEXT = {0: "Test your setup from start to finish. Not for a final model.",
             1: "Fewer knob positions than Good. Fine changes between settings may be missed.",
             2: "A good first model for most pedals.",
             3: "More knob positions. Use it when Good misses some settings.",
             4: "Much more recording. The model may improve only a little."}
SLOT_FOR_LEVEL = {0: 0, 1: 0, 2: 1, 3: 2, 4: 2}  # Expert levels show in the nearest card


class RecordPageMixin:
    def _build_record_page(self):
        self._record_choosing = False
        self.record_stack = QStackedWidget()
        self.record_choose = self._record_choose_widget()
        self.record_stack.addWidget(self.record_choose)
        self._capture_page(stack=self.record_stack)
        self.record_loop = self.record_stack.widget(1)
        self.change_level_link = button("Change detail level", self._choose_level_again)
        self.change_level_link.setProperty("link", True)
        self.record_loop.widget().layout().insertWidget(2, self.change_level_link, 0, Qt.AlignLeft)
        self.pages.addWidget(self.record_stack)
        self._record_footer = QWidget()
        row = QHBoxLayout(self._record_footer)
        row.setContentsMargins(0, 0, 0, 0)
        self.record_start_button = button("Start recording →", self._commit_plan, True)
        row.addWidget(self.record_start_button)
        row.addWidget(self.capture_continue)

    def _record_choose_widget(self) -> QWidget:
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(PageScroll.NoFrame)
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(PAGE_MARGIN, 36, PAGE_MARGIN, 24)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label("How detailed should the capture be?", "title"))
        layout.addWidget(label("More recordings teach the model more knob positions. "
                               "You cannot change this after the first take.", "muted"))
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.quality_cards = tuple(ChoiceCard() for _ in MAIN_LEVELS)
        for card, (_, level) in zip(self.quality_cards, MAIN_LEVELS):
            card.clicked.connect(lambda level=level: self._select_level(level))
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        self.record_lock_label = label("", "warn")
        layout.addWidget(self.record_lock_label)
        self.separate_button = button("Start a new capture with these controls", lambda: self._new_capture_from_gear())
        self.separate_button.setProperty("link", True)
        self.separate_button.setVisible(False)
        layout.addWidget(self.separate_button, alignment=Qt.AlignLeft)
        layout.addWidget(label("The app picks the knob positions for you. Coverage is a starting point, "
                               "not a promise of sound quality; training time is separate.", "muted"))
        self._record_expert(layout)
        scroll.setWidget(page)
        return scroll

    def _record_expert(self, layout) -> None:
        self.plan_advanced = QWidget()
        extra = QVBoxLayout(self.plan_advanced)
        extra.setContentsMargins(0, 8, 0, 8)
        levels = QHBoxLayout()
        levels.addWidget(label("More levels", "muted"))
        self.more_level_buttons = (button("Decent", lambda: self._select_level(1)),
                                   button("Overkill", lambda: self._select_level(4)))
        for more in self.more_level_buttons:
            levels.addWidget(more)
        levels.addStretch()
        extra.addLayout(levels)
        self.plan_summary = label("", "muted")
        extra.addWidget(self.plan_summary)
        form = QFormLayout()
        form.addRow("Random training settings", self.n_train_spin)
        form.addRow("Unseen test settings", self.n_validation_spin)
        form.addRow("Repeatable seed", self.seed_spin)
        extra.addLayout(form)
        extra.addWidget(self.include_corners_check)
        extra.addWidget(self.corner_count_label)
        self.advanced_plan_hint = label("", "muted")
        extra.addWidget(self.advanced_plan_hint)
        extra.addWidget(label("The saved capture plan", "section"))
        extra.addWidget(self.plan_table)
        self.plan_advanced_toggle = disclosure(layout, "Expert settings", self.plan_advanced)

    # ---- level cards ----------------------------------------------------------------

    def _select_level(self, level: int) -> None:
        if self._busy() or self._plan_locked():
            return
        self._apply_quality(level)
        self._refresh_level_cards()

    def _level_effort(self, level: int) -> tuple[int, int] | None:
        """(takes, minutes) for a level. Building plans is slow with many controls, so results are cached."""
        durations = self._input_durations()
        key = (repr(self.control_editor.controls), durations, level)
        cache = self.__dict__.setdefault("_effort_cache", {})
        if key not in cache:
            try:
                plan = make_plan(*quality_settings(self.control_editor.controls, level))
                cache[key] = (len(plan.entries), recording_minutes(plan, *durations))
            except ValueError:
                cache[key] = None
        return cache[key]

    def _refresh_level_cards(self) -> None:
        """Card numbers come from the real planner (spec: the mockup numbers are placeholders)."""
        locked = self._plan_locked()
        stored = self._quality
        for slot, (card, (title, level)) in enumerate(zip(self.quality_cards, MAIN_LEVELS)):
            shown = stored if stored is not None and SLOT_FOR_LEVEL.get(stored) == slot and stored != level else level
            if locked and shown == stored and self.project is not None:
                count, minutes = len(self.project.entries), recording_minutes(self.project, *self._input_durations())
                body = "Locked after the first take."
            elif locked:  # Disabled cards: the numbers are not needed.
                card.set_content(level_label(shown), "—", "", CARD_TEXT[shown], None)
                continue
            else:
                effort = self._level_effort(shown)
                count, minutes = effort if effort else (0, 0)
                body = CARD_TEXT[shown] if effort else "Not possible with these controls."
            tag = "Recommended" if shown == RECOMMENDED_LEVEL else None
            card.set_content(level_label(shown), str(count), f"takes · ~{minutes} min", body, tag)
        self._sync_card_selection()

    def _sync_card_selection(self) -> None:
        slot = SLOT_FOR_LEVEL.get(self._quality) if self._quality is not None else None
        for index, card in enumerate(self.quality_cards):
            card.set_selected(index == slot)

    def _choose_level_again(self) -> None:
        """Before the first take the level can still change: back to the cards."""
        if self._busy() or self._plan_locked():
            return
        self._record_choosing = True
        self._refresh_level_cards()
        self._show_record_state()

    def _show_record_state(self) -> None:
        recording = bool(self.project and self.project.entries) and not self._record_choosing
        self.record_stack.setCurrentWidget(self.record_loop if recording else self.record_choose)
        self.record_start_button.setVisible(not recording)
        self.capture_continue.setVisible(recording)
        self.change_level_link.setVisible(recording and not self._plan_locked())

    # ---- plan (moved from the old Plan page) --------------------------------------------

    def _plan_locked(self):
        # Sticky once any take was accepted, including if a file goes missing later.
        return bool(self.project and (self.project.captured_entries() or self._workflow.get("plan_locked")))

    def _apply_quality(self, level):
        if not self._ready or self._busy() or self._plan_locked():
            return
        try:
            knobs, train, tests = quality_settings(self.control_editor.controls, level)
            self._applying = True
            self.control_editor.controls = knobs
            for row, knob in enumerate(knobs):
                self.knob_table.setItem(row, 3, QTableWidgetItem(str(knob.step)))
            self.n_train_spin.setValue(train)
            self.n_validation_spin.setValue(tests)
            self.seed_spin.setValue(0)
            self.include_corners_check.setChecked(True)
            self._quality = level
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
        quality = QUALITIES[self._quality].name if self._quality is not None else "Custom counts"
        try:
            if self._plan_locked():
                self._preview = self.project
            else:
                self._preview = make_plan(self.control_editor.controls, self.n_train_spin.value(),
                                          self.n_validation_spin.value(), self.seed_spin.value(), self.include_corners_check.isChecked())
            train = len(self._preview.entries_for_split("train"))
            tests = len(self._preview.entries_for_split("validation"))
            self.plan_summary.setText(f"Using: {quality}. {train} training recordings · {tests} test recordings · "
                                      + f"{switch_combinations(self._preview.knob_specs())} switch combination(s).\n"
                                      + "The estimate allows 10 seconds to set the controls; breaks and retries add time.")
        except ValueError as exc:
            self._preview = None
            self.plan_summary.setText(str(exc))
        self._refresh_corner_count()
        if hasattr(self, "quality_cards"):
            self._sync_card_selection()
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
            self._show_record_state()
            self.go_to_step("record")
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
        self._workflow.update(quality=self._quality, fixed_notes=self.fixed_notes.text(), plan_locked=False,
                              gear_kind="amp" if self.gear_kind.currentIndex() else "pedal")
        write_state(self.project_dir, self._workflow)
        self._record_choosing = False
        self._refresh_all()
        self._show_record_state()
        self.go_to_step("record")
