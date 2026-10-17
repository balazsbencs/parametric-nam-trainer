"""Token-based Qt style sheet and the light / dark / match-macOS appearance switch."""
import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ..theme import ASSETS
from .tokens import APPEARANCES, Appearance, Palette, palette_for, resolve_mode

SETTINGS_KEY = "ui/appearance"
SETTINGS_ENV = "PARAMETRIC_SETTINGS_DIR"

_STYLE = Template("""
QWidget { font-size: 13px; color: $text; }
QMainWindow, QScrollArea, QWidget#page, QStackedWidget { background: $bg; }
QWidget#sidebar { background: $panel; border-right: 1px solid $line; }
QWidget#topBar { background: $bg; border-bottom: 1px solid $line; }
QWidget#footer { background: $bg; border-top: 1px solid $line; }
QWidget#aside { background: $panel; border-left: 1px solid $line; }
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 28px; font-weight: 600; }
QLabel[role="section"] { font-size: 13px; font-weight: 600; }
QLabel[role="quality"] { font-size: 28px; font-weight: 600; }
QLabel[role="muted"] { font-size: 12px; color: $muted; }
QLabel[role="ok"] { color: $ok; }
QLabel[role="danger"] { color: $danger; }
QLabel[role="accent"] { color: $accent_text; }
QLabel[role="warn"] { font-size: 12px; color: $warn; }
QLabel[tag="ok"] { color: $ok; background: $ok_surface; padding: 5px 9px; border-radius: 4px; }
QLabel[tag="accent"] { color: $accent_text; background: $accent_surface; padding: 3px 8px; border-radius: 4px; }
QLabel[listRow="true"] { padding: 12px 0; border-bottom: 1px solid $line; }
QLabel[routeSymbol="true"] { border: 1px solid $line_strong; border-radius: 5px; }
QStackedWidget#stageActions { border-top: 1px solid $line; }
QPushButton { font-size: 13px; font-weight: 500; padding: 8px 14px; border: 1px solid $line_strong; border-radius: 7px; background: $raised; color: $text; }
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: $line; }
QPushButton:focus { border-color: $accent_text; }
QPushButton:disabled { color: $muted; background: $panel; border-color: $line; }
QPushButton[primary="true"] { background: $accent_fill; color: $on_accent; border-color: $accent_fill; font-weight: 600; padding: 10px 18px; }
QPushButton[primary="true"]:hover { background: $accent_fill; border-color: $accent_text; }
QPushButton[primary="true"]:focus { border: 2px solid $text; }
QPushButton[primary="true"]:disabled { background: $panel; color: $muted; border-color: $line; }
QPushButton[outline="true"] { background: transparent; color: $accent_text; border: 2px solid $accent_text; font-weight: 600; }
QPushButton[outline="true"]:hover { background: $accent_surface; }
QPushButton[outline="true"]:focus { background: $accent_surface; border-color: $text; }
QPushButton[outline="true"]:disabled { color: $muted; border-color: $line_strong; background: transparent; }
QPushButton[link="true"] { background: transparent; color: $accent_text; border: 1px solid transparent; padding: 2px 0; text-align: left; }
QPushButton[link="true"]:hover { text-decoration: underline; background: transparent; }
QPushButton[link="true"]:disabled { color: $muted; }
QPushButton[quiet="true"] { border-color: transparent; color: $muted; padding: 7px 10px; background: transparent; }
QPushButton[quiet="true"]:hover { background: $hover; color: $text; }
QPushButton[quiet="true"]:focus { border-color: $accent_text; }
QPushButton[nav="true"] { text-align: left; background: transparent; border: 1px solid transparent; padding: 0; border-radius: 7px; }
QPushButton[nav="true"]:hover { background: $hover; }
QPushButton[nav="true"]:checked { background: $accent_surface; }
QPushButton[nav="true"]:focus { border-color: $accent_text; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px; color: $muted; }
QToolButton:hover { background: $hover; color: $text; }
QToolButton[disclosure="true"] { font-size: 12px; color: $muted; text-align: left; border: none; border-top: 1px solid $line; border-radius: 0; padding: 12px 0; }
QToolButton[disclosure="true"]:hover { color: $accent_text; background: transparent; }
QToolButton[disclosure="true"]:focus { border: 1px solid $accent_text; border-radius: 4px; }
QFrame[card="true"] { background: $raised; border: 1px solid $line_strong; border-radius: 10px; }
QFrame[card="true"][selected="true"] { border: 2px solid $accent_text; }
QFrame[card="true"]:disabled { background: $panel; }
QFrame[stage="true"] { background: $raised; border: 1px solid $line_strong; border-radius: 10px; }
QFrame[stage="true"][done="true"] { border-color: $ok; }
QFrame[alert="error"] { background: $danger_surface; border: 1px solid $danger_border; border-radius: 10px; }
QFrame[alert="error"] QLabel { color: $text; }
QFrame[tag="accent"] { background: $accent_surface; border-radius: 4px; }
QFrame[tag="ok"] { background: $ok_surface; border-radius: 4px; }
QFrame[tag="warn"] { background: $warn_surface; border-radius: 4px; }
QFrame[tag="danger"] { background: $danger_surface; border-radius: 4px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit { background: $panel; color: $text; border: 1px solid $line_strong; border-radius: 7px; padding: 7px 10px; min-height: 20px; selection-background-color: $accent_surface; selection-color: $text; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: $muted; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus { border-color: $accent_text; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { background: $bg; color: $muted; border-color: $line; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; }
QComboBox::down-arrow { image: url("$assets/chevron-down.svg"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: $raised; color: $text; border: 1px solid $line_strong; padding: 5px; selection-background-color: $accent_surface; selection-color: $text; outline: none; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 3px 7px; }
QSpinBox, QDoubleSpinBox { padding-right: 26px; }
QSpinBox QLineEdit, QDoubleSpinBox QLineEdit { border: none; background: transparent; padding: 0; min-height: 0; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 24px; border: none; margin: 3px 3px 0 0; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 24px; border: none; margin: 0 3px 3px 0; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("$assets/chevron-up.svg"); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("$assets/chevron-down.svg"); width: 10px; height: 10px; }
QCheckBox { font-size: 13px; spacing: 9px; padding: 6px 0; border: 1px solid transparent; color: $text; }
QCheckBox:focus { border-color: $accent_text; border-radius: 4px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid $muted; border-radius: 4px; background: $panel; }
QCheckBox::indicator:hover { border-color: $accent_text; }
QCheckBox::indicator:checked { background: $accent_fill; border-color: $accent_fill; image: url("$assets/check-dark.svg"); }
QCheckBox::indicator:disabled { background: $bg; border-color: $line_strong; }
QCheckBox::indicator:checked:disabled { background: $line_strong; image: url("$assets/check-muted.svg"); }
QTableWidget, QListWidget { background: $panel; color: $text; border: 1px solid $line; border-radius: 7px; gridline-color: $line; selection-background-color: $accent_surface; selection-color: $text; }
QHeaderView::section { background: $panel; color: $muted; padding: 8px; border: none; border-bottom: 1px solid $line; font-weight: 500; }
QMenu { background: $raised; color: $text; border: 1px solid $line_strong; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: $accent_surface; }
QMenuBar { background: $bg; color: $text; }
QToolTip { background: $raised; color: $text; border: 1px solid $line_strong; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: $line_strong; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: $line_strong; border-radius: 3px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: $line_strong; }
QSlider::handle:horizontal { background: $accent_fill; border: 3px solid $bg; width: 20px; margin: -8px 0; border-radius: 12px; }
QSlider::groove:horizontal:disabled { background: $line; }
QSlider::handle:horizontal:disabled { background: $muted; }
QSlider:focus { border: 1px solid $accent_text; border-radius: 6px; }
QStatusBar { font-size: 11px; background: $panel; color: $muted; border-top: 1px solid $line; }
QStatusBar QLabel { font-size: 11px; color: $muted; }
QStatusBar::item { border: none; }
QWidget#route { background: $raised; border: 1px solid $line; border-radius: 10px; }
QWidget#signalRoute { background: $raised; border: 1px solid $line; border-radius: 8px; }
QLabel#routeCaption { background: $panel; color: $muted; padding: 12px 15px; border-bottom: 1px solid $line; font-size: 12px; }
QWidget[routeRow="true"] { border-bottom: 1px solid $line; }
QWidget#profiles { border: 1px solid $line_strong; background: $panel; border-radius: 7px; }
QPushButton[profile="true"] { background: transparent; color: $muted; border: 1px solid transparent; border-radius: 5px; padding: 7px 8px; }
QPushButton[profile="true"]:checked { background: $accent_fill; color: $on_accent; font-weight: 600; }
QPushButton[profile="true"]:focus { border-color: $accent_text; }
QPushButton[profile="true"]:disabled { color: $muted; background: transparent; border-color: transparent; }
QPushButton[profile="true"]:checked:disabled { color: $muted; background: $line; font-weight: 400; }
QProgressBar { background: $line; color: $text; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { background: $accent_fill; border-radius: 3px; }
""")


# Which palette role each bundled icon is drawn in. Icons not listed use `muted`.
ICON_ROLES = {"check-dark.svg": "on_accent", "check-white.svg": "on_accent", "check-muted.svg": "muted"}
_SVG_COLOR = re.compile(r'(stroke|fill)="#[0-9a-fA-F]{6}"')


def tinted_assets(palette: Palette) -> Path:
    """A folder with every bundled SVG recolored to `palette`. Cached per palette."""
    key = hashlib.sha1(repr(sorted(vars(palette).items())).encode()).hexdigest()[:12]
    base = Path(os.environ[SETTINGS_ENV]) if os.environ.get(SETTINGS_ENV) else Path(tempfile.gettempdir())
    folder = base / "parametric-icons" / key
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for source in ASSETS.glob("*.svg"):
            color = getattr(palette, ICON_ROLES.get(source.name, "muted"))
            target = folder / source.name
            text = _SVG_COLOR.sub(lambda m: f'{m.group(1)}="{color}"', source.read_text())
            if not target.is_file() or target.read_text() != text:
                target.write_text(text)
    except OSError as exc:
        # Icons keep their bundled colors; the app still works.
        logging.getLogger(__name__).warning("Could not write tinted icons to %s: %s", folder, exc)
        return ASSETS
    return folder


def build_style_sheet(palette: Palette, assets: Path) -> str:
    """The whole application style sheet, with every color taken from `palette`."""
    return _STYLE.substitute(vars(palette), assets=Path(assets).as_posix())


def qt_palette(palette: Palette) -> QPalette:
    """A QPalette for native widgets that QSS does not reach."""
    result = QPalette()
    roles = ((QPalette.Window, palette.bg), (QPalette.WindowText, palette.text), (QPalette.Base, palette.panel),
             (QPalette.AlternateBase, palette.raised), (QPalette.Text, palette.text), (QPalette.Button, palette.raised),
             (QPalette.ButtonText, palette.text), (QPalette.Highlight, palette.accent_fill),
             (QPalette.HighlightedText, palette.on_accent), (QPalette.PlaceholderText, palette.muted),
             (QPalette.ToolTipBase, palette.raised), (QPalette.ToolTipText, palette.text))
    for role, color in roles:
        result.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        result.setColor(QPalette.Disabled, role, QColor(palette.muted))
    return result


def settings_from_env() -> QSettings:
    """Settings for this app. With PARAMETRIC_SETTINGS_DIR set, every QSettings in the process uses INI files there."""
    folder = os.environ.get(SETTINGS_ENV)
    if folder:
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, folder)
        return QSettings(QSettings.IniFormat, QSettings.UserScope, "Parametric", "Parametric")
    return QSettings("Parametric", "Parametric")


class AppearanceController(QObject):
    """Applies Match macOS / Light / Dark to the whole app at once and remembers the choice."""

    changed = Signal(object)

    def __init__(self, app: QApplication, settings: QSettings):
        super().__init__()
        self._app = app
        self._settings = settings
        self._setting_scheme = False
        saved = settings.value(SETTINGS_KEY, "system")
        self._choice: Appearance = saved if saved in APPEARANCES else "system"
        self._palette = palette_for("dark")
        hints = app.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self.on_system_scheme_changed())
        self._apply(emit=False)

    def choice(self) -> Appearance:
        return self._choice

    def palette(self) -> Palette:
        return self._palette

    def set_choice(self, choice: Appearance) -> None:
        if choice not in APPEARANCES:
            raise ValueError(f"Unknown appearance {choice!r}")
        self._choice = choice
        self._settings.setValue(SETTINGS_KEY, choice)
        self._apply()

    def on_system_scheme_changed(self) -> None:
        """React to a macOS light/dark change. Only "system" follows it; our own scheme calls are ignored."""
        if self._setting_scheme or self._choice != "system":
            return
        self._apply()

    def _apply(self, emit: bool = True) -> None:
        hints = self._app.styleHints()
        self._setting_scheme = True
        try:
            if self._choice == "system":
                if hasattr(hints, "unsetColorScheme"):
                    hints.unsetColorScheme()
            elif hasattr(hints, "setColorScheme"):
                hints.setColorScheme(Qt.ColorScheme.Dark if self._choice == "dark" else Qt.ColorScheme.Light)
            system_dark = hints.colorScheme() == Qt.ColorScheme.Dark
        finally:
            self._setting_scheme = False
        self._palette = palette_for(resolve_mode(self._choice, system_dark))
        self._app.setPalette(qt_palette(self._palette))
        self._app.setStyleSheet(build_style_sheet(self._palette, tinted_assets(self._palette)))
        if emit:
            self.changed.emit(self._palette)
