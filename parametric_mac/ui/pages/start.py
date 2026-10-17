"""Start page: create a capture, open a folder, or continue a recent project."""
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ...recent import (RECENT_KEY, ProjectStatus, dump_recent, forget, parse_recent, project_status,
                       remember)
from ...theme import mono_font
from ..widgets.common import button, label

ACTION_TEXT = {"new": "Continue", "recording": "Continue", "recorded": "Recorded", "ready": "Ready", "stopped": "Stopped"}


def link_button(text: str, callback) -> QPushButton:
    widget = QPushButton(text)
    widget.setProperty("link", True)
    widget.setCursor(Qt.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


class RecentRow(QFrame):
    """One recent project: name, saved state, and its action (or a remove link if it cannot open)."""

    def __init__(self, name: str, status: ProjectStatus, on_open, on_remove):
        super().__init__()
        self.name = name
        self.setProperty("listRow", True)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 10, 4, 10)
        words = QVBoxLayout()
        words.setSpacing(2)
        title = label(name, "section")
        self.detail = label(status.detail, "muted")
        words.addWidget(title)
        words.addWidget(self.detail)
        row.addLayout(words, 1)
        self.action = self.remove_button = None
        if status.state in ACTION_TEXT:
            self.action = link_button(ACTION_TEXT[status.state], on_open)
            self.action.setAccessibleName(f"{ACTION_TEXT[status.state]}: {name}")
            row.addWidget(self.action)
        else:
            self.remove_button = link_button("Remove from list", on_remove)
            self.remove_button.setAccessibleName(f"Remove {name} from the list")
            row.addWidget(self.remove_button)


class StartPageMixin:
    def _build_start_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        columns = QHBoxLayout(page)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        columns.addWidget(self._start_hero(), 1)
        columns.addWidget(self._start_aside(), 1)
        self.recent_rows: list[RecentRow] = []
        self.pages.addWidget(page)
        self._refresh_recent()
        return page

    def _start_aside(self) -> QWidget:
        aside = QWidget()
        aside.setObjectName("aside")
        aside.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(aside)
        layout.setContentsMargins(30, 40, 30, 20)
        self._recent_heading = label("", "muted")
        layout.addWidget(self._recent_heading)
        rows = QWidget()
        rows.setObjectName("asideRows")
        self._recent_layout = QVBoxLayout(rows)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setAlignment(Qt.AlignTop)
        self.recent_scroll = QScrollArea()
        self.recent_scroll.setFrameShape(QScrollArea.NoFrame)
        self.recent_scroll.setWidgetResizable(True)
        self.recent_scroll.setWidget(rows)
        layout.addWidget(self.recent_scroll, 1)
        return aside

    def _start_hero(self) -> QWidget:
        hero = QWidget()
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(40, 54, 40, 30)
        layout.setSpacing(18)
        eyebrow = label("CAPTURE · TRAIN · PLAY", "accent")
        eyebrow.setFont(mono_font(12))
        headline = label("Turn your pedal into a model you can still turn the knobs on.", "title")
        intro = label("You record your gear at many knob positions. Your Mac learns how it sounds. "
                      "You get one .nam file with real controls.", "muted")
        self.new_button = button("New capture", self._on_new_project, True)
        self.open_button = button("Open folder…", self._on_open_project)
        self.open_button.setProperty("outline", True)
        actions = QHBoxLayout()
        actions.addWidget(self.new_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        for widget in (eyebrow, headline, intro):
            layout.addWidget(widget)
        layout.addLayout(actions)
        layout.addStretch()
        layout.addWidget(label("You need: a sound card, a reamp box, your pedal or amp, and about 45 minutes.", "muted"))
        return hero

    def _recent_items(self):
        return parse_recent(self.settings.value(RECENT_KEY))

    def _save_recent(self, items) -> None:
        self.settings.setValue(RECENT_KEY, dump_recent(items))
        self.settings.sync()
        self._refresh_recent()

    def _remember_project(self) -> None:
        if self.project_dir is None:
            return
        name = (self.project.name if self.project else "") or self.project_dir.name
        self._save_recent(remember(self._recent_items(), self.project_dir, name, time.time()))

    def _refresh_recent(self) -> None:
        if not hasattr(self, "_recent_layout"):
            return
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        items = self._recent_items()
        self._recent_heading.setText("Continue where you stopped" if items else "Your captures appear here.")
        self.recent_rows = []
        for item in items:
            path = Path(item.path)
            row = RecentRow(item.name, project_status(path),
                            lambda checked=False, p=path: self._open_recent(p),
                            lambda checked=False, p=path: self._save_recent(forget(self._recent_items(), p)))
            row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self._recent_layout.addWidget(row)
            self.recent_rows.append(row)
        self._sync_recent_rows()

    def _sync_recent_rows(self) -> None:
        """No project switch while a job runs: one project per window during a job."""
        busy = self._busy()
        for row in getattr(self, "recent_rows", []):
            if row.action is not None:
                row.action.setEnabled(not busy)

    def _open_recent(self, path: Path) -> None:
        if self._busy():
            self.footer.set_status("Stop the running job before you open another project.")
            return
        try:
            self._open_project(path)
        except (OSError, ValueError) as exc:
            self.footer.set_status(f"Could not open {path.name}: {exc}")
            self._refresh_recent()
