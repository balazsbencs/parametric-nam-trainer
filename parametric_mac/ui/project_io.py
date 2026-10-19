"""Create, open and persist capture projects; route readiness."""
from pathlib import Path
import hashlib
import logging
import math
import shutil
from PySide6.QtWidgets import (
    QMessageBox, QFileDialog,
)
from nam.capture.project import atomic_write_json, save_project
from ..controls import ControlProject as CaptureProject, ControlModel, load_project, model_config
from ..control_editor import starter
from nam.capture.session import CaptureSession
from ..assets import FILES
from ..recent import project_status, resume_step

# The verified capture signals that Install.command downloads into the repository.
DEFAULT_INPUTS = Path(__file__).resolve().parents[2] / "inputs"
from ..workflow import RECOMMENDED_LEVEL, read_state, write_state


class ProjectMixin:
    def _reset_project_state(self) -> None:
        """No project open: the state the app starts in."""
        self.project = None
        self.project_dir = None
        self.session = None
        self._workflow = {}
        self._preview = None
        self._project_switched()
        # A new capture never inherits the old project's level or runs.
        self._quality = RECOMMENDED_LEVEL
        self._apply_quality(RECOMMENDED_LEVEL)
        self._refresh_runs()

    def _create_project(self, directory, inputs=None):
        directory = Path(directory)
        if any(directory.iterdir()):
            raise ValueError("Choose an empty folder. Your existing project and recordings have been left untouched.")
        inputs = Path(inputs) if inputs else DEFAULT_INPUTS
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
        self._project_switched()
        save_project(self.project, directory)
        write_state(directory, self._workflow)
        self._remember_project()
        self._refresh_runs()
        self.go_to_step("connect")
        self._refresh_all()
        self._refresh_preview()

    def _on_open_project(self):
        if self._busy():
            return
        directory = QFileDialog.getExistingDirectory(self, "Open pedal project")
        if directory:
            message = self._try_open(Path(directory))
            if message:
                QMessageBox.warning(self, "Could not open project", message)

    def _try_open(self, directory: Path) -> str | None:
        """Open a project; on any failure return a one-line message (the full error goes to the log)."""
        try:
            self._open_project(directory)
        except Exception as exc:  # noqa: BLE001 - every failure must reach the user as a message
            logging.getLogger(__name__).exception("Could not open %s", directory)
            first_line = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            return f"Could not open {directory.name}: {first_line}"
        return None

    def _read_project(self, directory) -> dict:
        """Load and validate everything a project needs before the window changes. Raises on a bad project."""
        project = load_project(directory)
        workflow = read_state(directory)
        quality = workflow.get("quality")
        notes = workflow.get("fixed_notes", "Keep unmodeled controls at their recorded positions")
        controls = project.knob_specs() or starter()
        drafts = workflow.get("draft_controls")
        locked = bool(project.captured_entries() or workflow.get("plan_locked"))
        draft_error = None
        if not locked and isinstance(drafts, list) and drafts:
            try:
                controls = tuple(ControlModel.model_validate(c).to_knob_spec() for c in drafts)
            except ValueError as exc:  # unsaved edits only: fall back to the saved controls
                draft_error = f"The draft controls could not be read, so the saved controls are used: {exc}"
        return {"project": project, "workflow": workflow, "controls": controls, "draft_error": draft_error,
                "quality": quality if type(quality) is int and 0 <= quality <= 4 else None,
                "notes": notes if isinstance(notes, str) else "",
                "amp": workflow.get("gear_kind") == "amp"}

    def _open_project(self, directory):
        opened = self._read_project(directory)  # raises before anything changes
        try:
            self._apply_opened(opened, Path(directory))
        except Exception:
            # The window already changed: end in a known state with no project, never half-open.
            self._applying = False
            self._reset_project_state()
            raise

    def _apply_opened(self, opened: dict, directory: Path) -> None:
        project = opened["project"]
        self._applying = True
        try:
            self.project, self.project_dir = project, directory
            self.session = CaptureSession(project, directory)
            self._train_input_name, self._validation_input_name = project.train_input, project.validation_input
            self._workflow = opened["workflow"]
            self._project_switched()
            architecture_index = self.model_architecture.findData(self._workflow.get("model_architecture", "auto"))
            self.model_architecture.setCurrentIndex(max(0, architecture_index))
            if project.captured_entries() and not self._workflow.get("plan_locked"):
                self._workflow["plan_locked"] = True
                try:
                    write_state(directory, self._workflow)
                except OSError as exc:  # the lock still holds in memory: it is derived from the takes
                    self.capture_log.appendPlainText(f"Could not save workflow.json: {exc}")
            self._quality = opened["quality"]
            self.pedal_name.setText(project.name)
            self.fixed_notes.setText(opened["notes"])
            self.control_editor.set_controls(opened["controls"])
            self._mirror_controls()
            self.gear_kind.setCurrentIndex(1 if opened["amp"] else 0)
            self._gear_changed()
            self.knob_names.setText(", ".join(row[0] for row in self._knob_table_rows()))
            self._sync_card_selection()
            if opened["draft_error"]:
                self.capture_log.appendPlainText(opened["draft_error"])
        finally:
            self._applying = False
        self._finish_open(project)

    def _finish_open(self, project) -> None:
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
        self._remember_project()
        self._refresh_gear()
        self.go_to_step(resume_step(project_status(self.project_dir)))

    def _project_switched(self) -> None:
        """Clear every piece of page state that belongs to one project. Used by new, create and open."""
        self._route_fingerprint = None
        self._record_choosing = False
        self._gear_folder = None
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.train_metric.setText("")
        self.retry_button.hide()
        self.train_alert.hide()
        self.status_label.setText("")
        self._reset_connect()
        self._reset_record_loop()
        self.footer.clear_message()
        # "Try again on CPU" settings belong to one run; they must not slow down the next project.
        self.device.setCurrentIndex(max(0, self.device.findData("auto")))
        self.batch.setValue(4)
        mapping = self._workflow.get("playback_calibration", {})
        if (not isinstance(mapping, dict) or isinstance(mapping.get("input_pad_db", 0), bool)
                or not isinstance(mapping.get("input_pad_db", 0), (int, float))
                or not math.isfinite(mapping.get("input_pad_db", 0)) or not 0 <= mapping.get("input_pad_db", 0) <= 30):
            mapping = {}
        for widget in (self.playback_pad, self.playback_confirm):
            widget.blockSignals(True)
        self.playback_pad.setValue(mapping.get("input_pad_db", 0))
        self.playback_confirm.setChecked(mapping.get("confirmed") is True)
        for widget in (self.playback_pad, self.playback_confirm):
            widget.blockSignals(False)

    def _route_ready(self):
        return self._connect_ready()

    def _on_route_test(self):
        if self._busy():
            return
        self._route_fingerprint = None
        self._show_level(None)
        self.route_test_progress.show()
        super()._on_route_test()
        self._sync_states()

    def _on_route_test_success(self, result):
        super()._on_route_test_success(result)
        self.route_test_progress.hide()
        reason = self.level_result.text().replace("⚠", "").strip()
        clean = result.ok and not result.loopback_failed and not result.loopback_disagreement
        self._show_level(result.peak if clean else None)
        if clean and self._level_state == "ok":
            self._route_fingerprint = self._current_audio_settings().stream_fingerprint()
        else:
            self._route_fingerprint = None
            if not clean:  # Keep upstream's specific reason, without the warning sign.
                self.level_result.setText(reason or "The check did not pass. Check the cables and channels, then check again.")
        self._sync_states()

    def _refresh_sample_rate_warning(self):
        super()._refresh_sample_rate_warning()
        for warning in (self.sample_rate_warning_label, self.capture_sample_rate_warning_label):
            warning.setText(warning.text().replace('⚠', '').strip())
        if self._ready:
            self._sync_states()

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
        from ..architectures import is_film
        self._export_configs('FiLM A2' if is_film(self.model_architecture.currentData()) else 'ConcatWaveNet', writer)
