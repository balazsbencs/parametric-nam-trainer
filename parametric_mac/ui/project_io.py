"""Create, open and persist capture projects; route readiness."""
from pathlib import Path
import hashlib
import shutil
from PySide6.QtWidgets import (
    QMessageBox, QFileDialog,
)
from nam.capture.project import save_project
from ..controls import ControlProject as CaptureProject, ControlModel, load_project
from ..control_editor import starter
from nam.capture.session import CaptureSession
from ..assets import FILES
from ..workflow import read_state, write_state


class ProjectMixin:
    def _on_new_project(self):
        if self._busy():
            return
        directory = QFileDialog.getExistingDirectory(self, "Choose an empty folder for this pedal project")
        if directory:
            try:
                self._create_project(Path(directory))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not create project", str(exc))

    def _create_project(self, directory, inputs=None):
        directory = Path(directory)
        if any(directory.iterdir()):
            raise ValueError("Choose an empty folder. Your existing project and recordings have been left untouched.")
        inputs = Path(inputs) if inputs else Path(__file__).resolve().parents[1] / "inputs"
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
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            check.setChecked(False)
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.retry_button.hide()
        save_project(self.project, directory)
        write_state(directory, self._workflow)
        self.status_label.setText("Project created. Connect your pedal and test the connection.")
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
        self.quality_slider.setValue(self._quality if self._quality is not None else 2)
        self._applying = False
        self._route_fingerprint = None
        self.capture_log.clear()
        self.train_log.clear()
        self.train_progress.setValue(0)
        self.train_metric.setText("Validation results will appear during training.")
        self.retry_button.hide()
        self.status_label.setText("Project opened. Check completed recordings before training.")
        for check in (self.reamp_check, self.monitor_check, self.level_check):
            check.setChecked(False)
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
        self.go_to_step("train" if project.entries and not project.pending_entries() else "connect")

    def _route_ready(self):
        return (self._route_fingerprint is not None
                and self._route_fingerprint == self._current_audio_settings().stream_fingerprint()
                and all(c.isChecked() for c in (self.reamp_check, self.monitor_check, self.level_check)))

    def _on_route_test(self):
        if self._busy():
            return
        self._route_fingerprint = None
        super()._on_route_test()
        self._sync_states()

    def _on_route_test_success(self, result):
        super()._on_route_test_success(result)
        if result.ok and not result.loopback_failed and not result.loopback_disagreement and result.peak < -1:
            self._route_fingerprint = self._current_audio_settings().stream_fingerprint()
        else:
            self._route_fingerprint = None
            if result.ok and result.peak >= -1:
                self.route_test_result_label.setText("Signal is too close to clipping. Lower levels, then test again before recording.")
        self._sync_states()

    def _refresh_sample_rate_warning(self):
        super()._refresh_sample_rate_warning()
        for warning in (self.sample_rate_warning_label, self.capture_sample_rate_warning_label):
            warning.setText(warning.text().replace('⚠', '').strip())
        if self._ready:
            self._sync_states()
