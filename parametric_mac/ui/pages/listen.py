"""Listen page: the model file, the test settings, a listening checklist, and earlier models."""
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
                               QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from nam.capture.project import atomic_write_json

from ...recent import safe_folder_name
from ...review import qualified_model, save_model
from ...theme import mono_font
from ..copy import CHECKPOINT_NOTE, metric_lines
from ..widgets.common import PAGE_MARGIN, PageScroll, button, disclosure, label
from ..widgets.knobs import control_value_text

LISTEN_CHECKS = ("The test settings sound like the real pedal", "Knob moves sound smooth, with no clicks")
PLAYER_TEXT = ("Load the file in a player that supports parametric models, like Ardor. "
               "The normal NAM player cannot open it.")
LOAD_STEPS = ("In Ardor, upload the file under Assets › NAM models.\n"
              "Then add it from the modules drawer under Amp and drive.\n"
              "Use the same knob ranges as on your gear, and compare with your saved test recordings.\n"
              "Single concat models also open in NamParametricPlugin.")
PLUGIN_URL = "https://github.com/phillipmself/NamParametricPlugin"
DATE_FORMAT = "%Y-%m-%d %H:%M"  # not localized: the interface is English


def link(text: str, callback):
    widget = button(text, callback)
    widget.setProperty("link", True)
    return widget


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


RUN_STATES = {"exported": "Model ready", "failed_or_interrupted": "Did not finish",
              "running": "Was running when the app closed"}


def run_model_type(run: Path) -> str:
    """The model type the run recorded in its manifest, or "" when it recorded none."""
    from ...architectures import ARCHITECTURES
    return ARCHITECTURES.get(read_json(run / "manifest.json").get("model_architecture", ""), "")


def run_state_text(run: Path) -> str:
    if (run / "model_parametric.nam").is_file():
        return "Model ready"
    return RUN_STATES.get(read_json(run / "status.json").get("status", ""), "No model")


def review_checks(review: dict) -> list[bool]:
    """The two checklist answers; an old {"listened": true} file means both were done."""
    checks = review.get("checks")
    if isinstance(checks, list) and len(checks) == len(LISTEN_CHECKS) and all(isinstance(c, bool) for c in checks):
        return list(checks)
    return [bool(review.get("listened", False))] * len(LISTEN_CHECKS)


class ListenPageMixin:
    def _listen_page(self):
        self._runs: list[Path] = []
        self._selected_run: Path | None = None
        scroll = PageScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(PageScroll.NoFrame)
        content = QWidget()
        content.setObjectName("page")
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        columns.addWidget(self._listen_main(), 3)
        columns.addWidget(self._listen_aside(), 2)
        scroll.setWidget(content)
        self.pages.addWidget(scroll)
        self.save_model_button = button("Save model…", self._save_model, True)

    def _listen_main(self) -> QWidget:
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(PAGE_MARGIN, 32, PAGE_MARGIN, 24)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignTop)
        self.listen_title = label("Your model is ready", "title")
        layout.addWidget(self.listen_title)
        layout.addWidget(label("Listen to it before you share it. A good number does not always mean a good sound.", "muted"))
        self.model_card = QFrame()
        self.model_card.setProperty("card", True)
        card = QHBoxLayout(self.model_card)
        card.setContentsMargins(14, 12, 14, 12)
        badge = label(".nam", "accent")
        badge.setWordWrap(False)
        badge.setFont(mono_font(12))
        badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        card.addWidget(badge)
        words = QVBoxLayout()
        self.model_file_label = label("", "section")
        self.model_details = label("", "muted")
        words.addWidget(self.model_file_label)
        words.addWidget(self.model_details)
        card.addLayout(words, 1)
        layout.addWidget(self.model_card)
        self.review_status = label("", "muted")
        layout.addWidget(self.review_status)
        self.qualification_status = label("", "muted")
        layout.addWidget(self.qualification_status)
        self.qualify_button = button("Qualify saved run", lambda: self._start("qualify"))
        layout.addWidget(self.qualify_button, alignment=Qt.AlignLeft)
        layout.addWidget(label("Test settings — not used to train the model", "muted"))
        self.test_table = QTableWidget()
        self.test_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.test_table.verticalHeader().hide()
        self.test_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.test_table)
        layout.addStretch(1)
        return main

    def _listen_aside(self) -> QWidget:
        aside = QWidget()
        aside.setObjectName("aside")
        aside.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(aside)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(label("Use it in a player", "muted"))
        layout.addWidget(label(PLAYER_TEXT))
        steps = QWidget()
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.addWidget(label(LOAD_STEPS, "muted"))
        steps_layout.addWidget(link("Get NamParametricPlugin", lambda: QDesktopServices.openUrl(QUrl(PLUGIN_URL))))
        disclosure(layout, "How to load it", steps)
        layout.addSpacing(8)
        layout.addWidget(label("Did it pass your ears?", "muted"))
        self.listen_checks = tuple(QCheckBox(text) for text in LISTEN_CHECKS)
        for check in self.listen_checks:
            layout.addWidget(check)
        self.review_note = label("Listening is your judgement, not an automatic quality score.", "muted")
        layout.addWidget(self.review_note)
        layout.addStretch()
        self._listen_earlier(layout)
        layout.addWidget(link("Open project folder", self._open_project_folder))
        self._listen_expert(layout)
        return aside

    def _listen_earlier(self, layout) -> None:
        panel = QWidget()
        self._earlier_layout = QVBoxLayout(panel)
        self._earlier_layout.setContentsMargins(0, 0, 0, 0)
        self.earlier_rows: list[QWidget] = []
        self.folder_button = link("Open run folder", self._open_outputs)
        self._earlier_layout.addWidget(self.folder_button)
        disclosure(layout, "Earlier models", panel)

    def _listen_expert(self, layout) -> None:
        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(0, 0, 0, 0)
        self.review_metric = label("", "muted")
        self.checkpoint_note = label(CHECKPOINT_NOTE, "muted")
        self.recordings_button = link("Open test recordings", self._open_recordings)
        for widget in (self.review_metric, self.checkpoint_note, self.recordings_button):
            box.addWidget(widget)
        disclosure(layout, "Expert settings", panel)

    def listen_expert_text(self) -> str:
        return "\n".join((self.review_metric.text(), self.checkpoint_note.text()))

    # ---- runs -----------------------------------------------------------------------

    def _exported_run(self) -> Path | None:
        run = getattr(self, "_selected_run", None)
        return run if run and qualified_model(run) is not None else None

    def _refresh_runs(self) -> None:
        folder = self.project_dir / "outputs" if self.project_dir else None
        runs = [p for p in folder.iterdir() if p.is_dir() and (p / "manifest.json").is_file()] if folder and folder.is_dir() else []
        self._runs = sorted(runs, key=lambda p: (p / "manifest.json").stat().st_mtime_ns, reverse=True)
        if self._selected_run not in self._runs:
            with_model = [r for r in self._runs if qualified_model(r) is not None]
            self._selected_run = (with_model or self._runs or [None])[0]
        self._show_earlier()
        self._show_run()

    def _select_run(self, run: Path) -> None:
        self._selected_run = Path(run)
        self._show_earlier()
        self._show_run()

    def _show_earlier(self) -> None:
        for row in self.earlier_rows:
            row.hide()
            row.deleteLater()
        self.earlier_rows = []
        for run in self._runs:
            stamp = datetime.fromtimestamp((run / "manifest.json").stat().st_mtime).strftime(DATE_FORMAT)
            parts = [stamp, run_state_text(run), run_model_type(run)] + (["shown"] if run == self._selected_run else [])
            row = link(" · ".join(p for p in parts if p), lambda checked=False, r=run: self._select_run(r))
            self._earlier_layout.addWidget(row)
            self.earlier_rows.append(row)

    def _show_run(self, *args) -> None:
        run, exported = self._selected_run, self._exported_run()
        name = (self.project.name if self.project else "") or (self.project_dir.name if self.project_dir else "model")
        self.listen_title.setText("Your model is ready" if exported else "No model yet")
        self.model_card.setVisible(exported is not None)
        self.model_file_label.setText(f"{name}.nam")
        if exported:
            trained = datetime.fromtimestamp((exported / "playback/model_playback.nam").stat().st_mtime).strftime(DATE_FORMAT)
            controls = ", ".join(k.name for k in self.project.knob_specs()) if self.project else ""
            parts = (run_model_type(exported), controls, f"trained {trained}")
            self.model_details.setText(" · ".join(p for p in parts if p))
        state = read_json(run / "status.json") if run else {}
        self.review_status.setText("" if exported else state.get("error", "Train a model on the Train page first."))
        self.review_metric.setText("\n".join(metric_lines(read_json(run / "metrics.json") if run else {})))
        checks = review_checks(read_json(run / "review.json")) if run else [False, False]
        for check, value in zip(self.listen_checks, checks):
            check.blockSignals(True)
            check.setChecked(value)
            check.blockSignals(False)
        qualification = read_json(run / "playback/qualification.json") if run else {}
        self.qualification_status.setText("Playback checks passed. Listening and pedal timing still need assessment." if exported else
            qualification.get("error", "A qualified playback model is required before saving. Confirm input mapping in Train → Expert settings, then qualify this run.") +
            (" Re-qualify the run if its model file was changed." if qualification.get("passed") else ""))
        if exported and "mean_validation_esr" in qualification:
            self.review_metric.setText(f"Playback held-out ESR: mean {qualification['mean_validation_esr']:.6g} · worst {qualification['max_validation_esr']:.6g}\n"
                                       f"Stress-tested {len(qualification.get('stress', []))} control settings. Listening is still required.")
        self._show_test_settings()
        self._sync_states()

    def _show_test_settings(self) -> None:
        entries = self.project.entries_for_split("validation") if self.project else []
        specs = self.project.knob_specs() if self.project else ()
        names = [k.name for k in specs]
        self.test_table.clear()
        self.test_table.setColumnCount(len(names) + 1)
        self.test_table.setHorizontalHeaderLabels([*names, "Match"])
        self.test_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for column, control in enumerate(specs):
                value = entry.params.get(control.name)
                text = control_value_text(control, value) if value is not None else ""
                self.test_table.setItem(row, column, QTableWidgetItem(text))
            self.test_table.setItem(row, len(names), QTableWidgetItem("—"))
        rows_height = sum(self.test_table.rowHeight(r) for r in range(len(entries)))
        self.test_table.setFixedHeight(self.test_table.horizontalHeader().height() + rows_height + 4)

    def _save_review(self, *args) -> None:
        run = self._exported_run()
        if run is None or self._busy():
            return
        checks = [check.isChecked() for check in self.listen_checks]
        try:
            atomic_write_json(run / "review.json", {"listened": all(checks), "checks": checks})
        except OSError as exc:
            self.review_note.setText(f"Could not save your answers: {exc}")

    def _save_model(self):
        run = self._exported_run()
        if self._busy() or run is None:
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save model", self._default_model_name(), "NAM model (*.nam)")
        if not dest:
            return
        try:
            save_model(run, dest)
            self.review_note.setText(f"Model saved to {dest}.")
        except (OSError, ValueError) as exc:
            self.review_note.setText(f"Could not save the model: {exc}")

    def _default_model_name(self) -> str:
        """The project name as a safe file name (a "/" in the name must not become a folder)."""
        return safe_folder_name((self.project.name if self.project else "") or "model") + ".nam"

    def _open_outputs(self):
        if self._selected_run:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._selected_run)))

    def _open_project_folder(self):
        if self.project_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project_dir)))

    def _open_recordings(self):
        if self.project_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project_dir / "captures")))
            self.review_note.setText("The test recordings are the val_lhs_*.wav files.")
