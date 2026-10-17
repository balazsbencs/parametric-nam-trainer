"""Gear page: name, type, the knobs and switches to capture, and where the project is saved."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget
from nam.capture.project import save_project

from ...control_editor import ControlEditor, starter, swap_starter
from ...controls import ControlModel
from ...recent import default_project_dir, projects_root
from ...workflow import RECOMMENDED_LEVEL, make_plan, quality_settings, recording_minutes, write_state
from ..widgets.common import PAGE_MARGIN, PageScroll, Segmented, button, field, label, themed
from ..widgets.knobs import GearDrawing
from ..widgets.shell_bars import ElidedLabel

PEDAL_FIXED, AMP_FIXED = "Level at 5", "Cabinet / load-box settings fixed"


def display_path(path: Path) -> str:
    """The path with the home folder shown as ~."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def link(text: str, callback) -> QPushButton:
    widget = QPushButton(text)
    widget.setProperty("link", True)
    widget.setCursor(Qt.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


class GearPageMixin:
    def _build_gear_page(self):
        self._gear_folder: Path | None = None
        self.pedal_name = QLineEdit("My pedal")
        self.gear_kind = Segmented(("Pedal", "Amp"))
        self.fixed_notes = QLineEdit(PEDAL_FIXED)
        self.knob_names = QLineEdit("Drive, Tone")
        self.knob_names.hide()
        self.control_editor = ControlEditor(self.appearance)
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(PageScroll.NoFrame)
        content = QWidget()
        content.setObjectName("page")
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        columns.addWidget(self._gear_main(), 3)
        columns.addWidget(self._gear_aside(), 2)
        scroll.setWidget(content)
        self.pages.addWidget(scroll)
        self._gear_footer = self._gear_footer_widget()
        self.gear_kind.currentIndexChanged.connect(self._gear_kind_changed)
        self._refresh_gear()

    def _gear_main(self) -> QWidget:
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(PAGE_MARGIN, 28, PAGE_MARGIN, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label("What are you capturing?", "title"))
        layout.addWidget(label("Add only the knobs you want to turn later. Every extra knob makes the recording longer.", "muted"))
        identity = QHBoxLayout()
        identity.setSpacing(12)
        identity.addWidget(field("Name", self.pedal_name), 3)
        identity.addWidget(field("Type", self.gear_kind), 0)
        layout.addLayout(identity)
        layout.addWidget(label("Knobs and switches to capture", "muted"))
        layout.addWidget(self.control_editor)
        layout.addWidget(label("Click a name or range to change it.", "muted"))
        layout.addWidget(field("Other controls stay where they are — write them down", self.fixed_notes))
        self.gear_lock_note = label("Locked after the first take. Your recordings depend on these controls.", "warn")
        self.gear_new_link = link("Start a new capture with these controls", lambda: self._new_capture_from_gear())
        self.gear_error = label("", "danger")
        for widget in (self.gear_lock_note, self.gear_new_link, self.gear_error):
            widget.hide()
            layout.addWidget(widget, 0, Qt.AlignLeft)
        return main

    def _gear_aside(self) -> QWidget:
        aside = QWidget()
        aside.setObjectName("aside")
        aside.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(aside)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(16)
        self.gear_aside_title = label("Your pedal", "muted")
        layout.addWidget(self.gear_aside_title)
        self.gear_drawing = themed(GearDrawing(), self.appearance)
        layout.addWidget(self.gear_drawing, 0, Qt.AlignHCenter)
        self.effort_label = label("", "section")
        layout.addWidget(self.effort_label)
        layout.addStretch()
        return aside

    def _gear_footer_widget(self) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.gear_folder_label = ElidedLabel("")
        self.gear_folder_label.setProperty("role", "muted")
        self.gear_folder_label.setMinimumWidth(160)
        self.gear_change_link = link("Change", lambda: self._change_gear_folder())
        self.gear_next_button = button("Next: Connect →", lambda: self._gear_next(), True)
        row.addWidget(self.gear_folder_label, 1)
        row.addWidget(self.gear_change_link)
        row.addSpacing(16)
        row.addWidget(self.gear_next_button)
        return holder

    # ---- state ----------------------------------------------------------------------

    def _gear_locked(self) -> bool:
        return self._plan_locked()

    def _gear_target(self) -> Path:
        return self._gear_folder or default_project_dir(projects_root(), self.pedal_name.text())

    def _refresh_gear(self, effort: bool = True) -> None:
        """Effort builds a plan, so typing in the text fields refreshes without it."""
        if not hasattr(self, "gear_drawing"):
            return
        controls = self.control_editor.controls
        amp = self.gear_kind.currentIndex() == 1
        self.gear_aside_title.setText("Your amp" if amp else "Your pedal")
        self.gear_drawing.set_gear(self.pedal_name.text(), controls, self.fixed_notes.text())
        if effort:
            self.effort_label.setText(self._gear_effort(controls))
        folder = self.project_dir if self.project_dir else self._gear_target()
        self.gear_folder_label.setText("Saved in " + display_path(Path(folder)))
        self.gear_change_link.setVisible(self.project_dir is None)
        self._sync_gear_lock()

    def _sync_gear_lock(self) -> None:
        """Cheap: called from every state sync."""
        if not hasattr(self, "gear_lock_note"):
            return
        locked = self._gear_locked()
        self.gear_lock_note.setVisible(locked)
        self.gear_new_link.setVisible(locked)
        self.gear_change_link.setVisible(self.project_dir is None)

    @staticmethod
    def _gear_effort(controls) -> str:
        try:
            levelled, train, tests = quality_settings(controls, RECOMMENDED_LEVEL)
            plan = make_plan(levelled, train, tests)
        except ValueError as exc:
            return str(exc)
        return f"~{len(plan.entries)} recordings · ~{recording_minutes(plan)} min to record"

    # ---- actions --------------------------------------------------------------------

    def _gear_kind_changed(self, index: int) -> None:
        if self._applying or self._busy() or self._gear_locked():
            return
        amp = index == 1
        swapped = swap_starter(self.control_editor.controls, amp)
        if swapped is not self.control_editor.controls:
            self.control_editor.set_controls(swapped)
            if self.fixed_notes.text() in (PEDAL_FIXED, AMP_FIXED):
                self.fixed_notes.setText(AMP_FIXED if amp else PEDAL_FIXED)
            self._controls_changed()
        self._refresh_gear()

    def _use_starter(self, amp):
        """Replace the controls with a starter, whatever the current list is."""
        if self._busy() or self._plan_locked():
            return
        self._applying = True
        self.gear_kind.setCurrentIndex(int(amp))
        self._applying = False
        self._gear_changed()
        self.control_editor.set_controls(starter(amp))
        self.fixed_notes.setText(AMP_FIXED if amp else PEDAL_FIXED)
        self._controls_changed()
        self._save_details()

    def _ask_gear_folder(self) -> str:
        return QFileDialog.getExistingDirectory(self, "Choose an empty folder for this capture")

    def _change_gear_folder(self) -> None:
        chosen = self._ask_gear_folder()
        if not chosen:
            return
        folder = Path(chosen)
        if folder.exists() and any(folder.iterdir()):
            self._show_gear_error("Choose an empty folder.")
            return
        self._gear_folder = folder
        self.gear_error.hide()
        self._refresh_gear()

    def _show_gear_error(self, text: str) -> None:
        self.gear_error.setText(text)
        self.gear_error.show()

    def _gear_next(self) -> None:
        if self._busy():
            return
        if self.project is not None:
            self._save_details()
            self.go_to_step("connect")
            return
        target = self._gear_target()
        existed = target.exists()
        try:
            target.mkdir(parents=True, exist_ok=True)
            self._create_project(target, inputs=self._inputs_dir)
        except (OSError, ValueError) as exc:
            if not existed and target.is_dir() and not any(target.iterdir()):
                target.rmdir()  # Do not leave an empty folder that makes the next name "… 2".
            self._show_gear_error(str(exc))
            return
        self.gear_error.hide()
        self._refresh_gear()

    def _start_new_capture(self) -> None:
        """Start: a fresh Gear page for a new project."""
        if self._busy():
            return
        self._reset_project_state()
        self._fill_gear("My pedal", 0, starter(False), PEDAL_FIXED)
        self.go_to_step("gear")

    def _new_capture_from_gear(self) -> None:
        """A new project with the same gear; the old project stays untouched."""
        if self._busy():
            return
        name, kind = self.pedal_name.text(), self.gear_kind.currentIndex()
        controls, fixed = self.control_editor.controls, self.fixed_notes.text()
        self._reset_project_state()
        self._fill_gear(name, kind, controls, fixed)
        self._gear_next()

    def _fill_gear(self, name: str, kind: int, controls, fixed: str) -> None:
        self._applying = True
        self.pedal_name.setText(name)
        self.gear_kind.setCurrentIndex(kind)
        self.fixed_notes.setText(fixed)
        self.control_editor.set_controls(controls)
        self._applying = False
        self._gear_folder = None
        self.gear_error.hide()
        self._gear_changed()
        self._controls_changed()
        self._refresh_all()
        self._refresh_gear()

    # ---- moved from the old Connect page ------------------------------------------------

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
        self._refresh_gear()

    def _save_details(self):
        self._refresh_gear()
        if not self.project or self._busy() or self._plan_locked():
            return
        self.project.name = self.pedal_name.text().strip() or self.project_dir.name
        save_project(self.project, self.project_dir)
        self._workflow["fixed_notes"] = self.fixed_notes.text()
        self._workflow["gear_kind"] = "amp" if self.gear_kind.currentIndex() else "pedal"
        write_state(self.project_dir, self._workflow)
        self._refresh_all()
