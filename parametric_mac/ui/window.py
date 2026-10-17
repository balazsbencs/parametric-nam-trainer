"""The main window: upstream MainWindow plus the page mixins."""
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFormLayout, QComboBox, QLineEdit, QProgressBar, QSizePolicy,
)
from nam.capture.gui.main import MainWindow
from ..theme import install_typography
from .style import AppearanceController, settings_from_env
from .shell import ShellMixin
from .jobs import JobsMixin
from .project_io import ProjectMixin
from .pages.start import StartPageMixin
from .pages.connect import ConnectPageMixin
from .pages.plan import PlanPageMixin
from .pages.capture import CapturePageMixin
from .pages.train import TrainPageMixin
from .pages.review import ReviewPageMixin


class MacWindow(ShellMixin, ProjectMixin, JobsMixin, StartPageMixin, ConnectPageMixin, PlanPageMixin, CapturePageMixin,
                TrainPageMixin, ReviewPageMixin, MainWindow):
    def __init__(self):
        self.process = None
        self.stopping = False
        self.command = None
        self._applying = True
        self._ready = False
        self._route_fingerprint = None
        self._preview = None
        self._quality = 2
        self._run_folder = None
        self._log_buffer = ""
        self._workflow = {}
        install_typography()
        # Created before super().__init__(): upstream builds the pages there, and pages read the palette.
        self.settings = settings_from_env()
        self.appearance = AppearanceController(QApplication.instance(), self.settings)
        super().__init__()
        self.setWindowTitle("Parametric — capture & training")
        # QMacStyle defaults squeeze fields and center forms. Make geometry explicit.
        for form in self.findChildren(QFormLayout):
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for field in self.findChildren((QLineEdit)) + self.findChildren(QComboBox):
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.version_label.setText("NAM engine " + self.version_label.text())
        self.resize(1140, 840)
        self.setMinimumSize(760, 580)
        self._ready = True
        self._applying = False
        self.loopback_check.setChecked(False)
        self._mirror_controls()
        self._apply_quality(2)
        self._refresh_all()
        for progress in self.findChildren(QProgressBar):
            progress.setTextVisible(False)
        self.centralWidget().setFocusPolicy(Qt.StrongFocus)
        self.centralWidget().setFocus(Qt.OtherFocusReason)


def launch(train_tab: bool = False) -> int:
    """Open the app on Start.

    `train_tab` (from Train.command) is accepted for compatibility and ignored: the user picks the project on Start.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = MacWindow()
    window.show()
    return app.exec()
