"""Review page."""
from pathlib import Path
import json
import shutil
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QComboBox, QCheckBox, QFileDialog,
)
from nam.capture.project import atomic_write_json
from ...controls import model_config
from ..widgets.common import label, button, Columns


class ReviewPageMixin:
    def _review_page(self):
        layout = self._page("Review your model", "An export is the beginning of review. Check unseen settings and listen before sharing it.")
        columns = Columns(layout)
        layout, reference = columns.columns
        self.run_combo = QComboBox()
        self.run_combo.setAccessibleName("Saved training run")
        self.run_combo.currentIndexChanged.connect(self._show_run)
        layout.addWidget(self.run_combo)
        self.review_status = label("No saved training runs yet.", "section")
        self.review_metric = label("", "muted")
        self.model_path = label("", "muted")
        layout.addWidget(self.review_status)
        layout.addWidget(self.review_metric)
        layout.addWidget(self.model_path)
        reference.addWidget(label("Listen to the exported model", "section"))
        reference.addWidget(label("Upload this model in Ardor’s manager, then add it from the modules drawer. "
                               "Ardor supports concat and FiLM exports, including Standard + Nano files. "
                               "NamParametricPlugin supports individual concat exports. "
                               "Use the model’s same knob ranges, and compare against your saved test recordings.", "muted"))
        reference.addWidget(button("Get concat player", lambda: QDesktopServices.openUrl(QUrl("https://github.com/phillipmself/NamParametricPlugin"))), alignment=Qt.AlignLeft)
        reference.addWidget(label("Check low, middle and high positions of each modeled knob; sweep between them and listen for differences, noise and level changes. "
                               "Test settings were held out of training. There is no built-in A/B player in this version.", "muted"))
        self.review_check = QCheckBox("I listened and checked unseen settings")
        reference.addWidget(self.review_check)
        self.review_note = label("", "muted")
        reference.addWidget(self.review_note)
        row = QHBoxLayout()
        self.save_model_button = button("Save model…", self._save_model, True)
        self.folder_button = button("Open run folder", self._open_outputs)
        self.recordings_button = button("Open test recordings", self._open_recordings)
        row.addWidget(self.save_model_button)
        row.addWidget(self.folder_button)
        row.addWidget(self.recordings_button)
        row.addStretch()
        layout.addLayout(row)

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
        from ...architectures import is_film
        self._export_configs('FiLM A2' if is_film(self.model_architecture.currentData()) else 'ConcatWaveNet', writer)

    def _refresh_runs(self):
        selected = self.run_combo.currentData()
        self.run_combo.blockSignals(True)
        self.run_combo.clear()
        folder = self.project_dir / "outputs" if self.project_dir else None
        if folder and folder.is_dir():
            runs = (p for p in folder.iterdir() if p.is_dir() and (p / "manifest.json").is_file())
            for run in sorted(runs, key=lambda p: (p / "manifest.json").stat().st_mtime_ns, reverse=True):
                self.run_combo.addItem(run.name, str(run))
        index = self.run_combo.findData(selected)
        self.run_combo.setCurrentIndex(index if index >= 0 else 0)
        self.run_combo.blockSignals(False)
        self._show_run()

    @staticmethod
    def _run_json(run, name):
        try:
            value = json.loads((run / name).read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _exported_run(self):
        data = self.run_combo.currentData()
        run = Path(data) if data else None
        return run if run and (run / "model_parametric.nam").is_file() else None

    def _show_run(self, *args):
        data = self.run_combo.currentData()
        run = Path(data) if data else None
        exported = self._exported_run()
        state = self._run_json(run, "status.json") if run else {}
        reviewed = self._run_json(run, "review.json").get("listened", False) if run else False
        self.review_status.setText("Model exported · listening recorded" if exported and reviewed else "Model exported · needs listening" if exported else f"Run: {state.get('status', 'configs saved; no export')}" if run else "No saved training runs yet.")
        self.model_path.setText(str(run / "model_parametric.nam") if exported else state.get("error", "Capture and train a project to create a model."))
        metrics = self._run_json(run, "metrics.json") if run else {}
        esr = metrics.get("ESR")
        if isinstance(metrics.get("tiers"), dict):
            lines = []
            for tier, values in metrics["tiers"].items():
                value = values.get("ESR")
                lines.append(f"{tier.capitalize()}: last validation ESR {value:.6g} · epoch {values.get('epoch')}"
                             if isinstance(value, (int, float)) else f"{tier.capitalize()}: no validation ESR recorded")
            lines.append("Last epochs, not separate evaluations of the exported checkpoints. Listen to both sizes.")
            self.review_metric.setText("\n".join(lines))
        else:
            self.review_metric.setText(f"Last logged validation ESR: {esr:.6g} · epoch {metrics.get('epoch')}\nThis is the last epoch, not a separate evaluation of the exported checkpoint. Lower is better; listen too." if isinstance(esr, (int, float)) else "No validation metric recorded for this run. Inspect training.log for details.")
        self.review_check.blockSignals(True)
        self.review_check.setChecked(bool(reviewed))
        self.review_check.blockSignals(False)
        self.review_note.setText("Listening is your assessment, not an automatic quality certification.")
        self.save_model_button.setEnabled(exported is not None)
        self.folder_button.setEnabled(run is not None)
        self.recordings_button.setEnabled(self.project_dir is not None)
        self._sync_states()

    def _save_review(self, checked):
        run = self._exported_run()
        if run and not self._busy():
            try:
                atomic_write_json(run / "review.json", {"listened": checked})
            except OSError as exc:
                self.review_note.setText(f"Could not save listening status: {exc}")
                return
            self._show_run()

    def _save_model(self):
        if self._busy():
            return
        run = self._exported_run()
        if run:
            dest, _ = QFileDialog.getSaveFileName(self, "Save parametric model", f"{self.project.name if self.project else 'pedal'}-parametric.nam", "NAM model (*.nam)")
            if dest:
                source = run / "model_parametric.nam"
                try:
                    if Path(dest).resolve() != source.resolve():
                        shutil.copy2(source, dest)
                    self.review_note.setText(f"Model saved to {dest}. Upload it in Ardor’s NAM models manager.")
                except OSError as exc:
                    self.review_note.setText(f"Could not save model: {exc}")

    def _open_outputs(self):
        data = self.run_combo.currentData()
        if data:
            QDesktopServices.openUrl(QUrl.fromLocalFile(data))

    def _open_recordings(self):
        if self.project_dir:
            # Captures are named val_lhs_* for held-out settings, alongside training WAVs.
            folder = self.project_dir / "captures"
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            self.review_note.setText("Unseen test recordings are the val_lhs_*.wav files. Their exact settings are in the capture queue.")
