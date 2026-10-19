"""Create, open and persist capture projects; route readiness."""
from pathlib import Path
import hashlib
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
        self._route_fingerprint = None
        self._preview = None
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.retry_button.hide()
        self.train_alert.hide()
        self._reset_connect()
        self._reset_record_loop()
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
        self._route_fingerprint = None
        self._reset_connect()
        self._reset_record_loop()
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.retry_button.hide()
        self.train_alert.hide()
        save_project(self.project, directory)
        write_state(directory, self._workflow)
        self.status_label.setText("")
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
            try:
                self._open_project(Path(directory))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not open project", str(exc))

    def _open_project(self, directory):
        project = load_project(directory)
        self._applying = True
        self.project, self.project_dir = project, Path(directory)
        self.session = CaptureSession(project, self.project_dir)
        self._train_input_name, self._validation_input_name = project.train_input, project.validation_input
        self._workflow = read_state(directory)
        architecture_index = self.model_architecture.findData(self._workflow.get("model_architecture", "auto"))
        self.model_architecture.setCurrentIndex(max(0, architecture_index))
        if project.captured_entries():
            self._workflow["plan_locked"] = True
            write_state(directory, self._workflow)
        stored_quality = self._workflow.get("quality")
        self._quality = stored_quality if type(stored_quality) is int and 0 <= stored_quality <= 4 else None
        self.pedal_name.setText(project.name)
        self.fixed_notes.setText(self._workflow.get("fixed_notes", "Keep unmodeled controls at their recorded positions"))
        controls = project.knob_specs() or starter()
        if not self._plan_locked() and self._workflow.get('draft_controls'):
            controls = tuple(ControlModel.model_validate(c).to_knob_spec() for c in self._workflow['draft_controls'])
        self.control_editor.set_controls(controls)
        self._mirror_controls()
        self.gear_kind.setCurrentIndex(1 if self._workflow.get("gear_kind") == "amp" else 0)
        self._gear_changed()
        self.knob_names.setText(", ".join(row[0] for row in self._knob_table_rows()))
        self._sync_card_selection()
        self._applying = False
        self._route_fingerprint = None
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.train_metric.setText("")
        self.retry_button.hide()
        self.train_alert.hide()
        self.status_label.setText("")
        self._reset_connect()
        self._reset_record_loop()
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
        self._gear_folder = None
        self._remember_project()
        self._refresh_gear()
        self.go_to_step(resume_step(project_status(self.project_dir)))

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
