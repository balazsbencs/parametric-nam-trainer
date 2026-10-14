"""The approved mockup's typography and vector control chrome, rendered by Qt."""
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).with_name('ui_assets')
_FONT_FAMILY = None


def install_typography():
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        for weight in ('Regular', 'Medium', 'SemiBold'):
            font_id = QFontDatabase.addApplicationFont(str(ASSETS/f'Inter-{weight}.ttf'))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if not families:
                raise RuntimeError('The bundled interface font could not load. Reinstall the application source.')
        _FONT_FAMILY = families[0]
    font = QFont(_FONT_FAMILY)
    font.setPixelSize(13)
    font.setWeight(QFont.Normal)
    QApplication.instance().setFont(font)
    return font


def icon(name):
    return QIcon(str(ASSETS/f'{name}.svg'))


def style_sheet():
    return STYLE.replace('@assets', ASSETS.as_posix())


STYLE = """
QWidget { font-size: 13px; color: #252a32; }
QMainWindow, QScrollArea, QWidget#page { background: #ffffff; }
QWidget#sidebar { background: #f6f7f9; border-right: 1px solid #e1e5ec; }
QLabel[role="title"] { font-size: 27px; font-weight: 600; }
QLabel[role="section"] { font-size: 13px; font-weight: 600; }
QLabel[role="quality"] { font-size: 28px; font-weight: 600; }
QLabel[role="muted"] { font-size: 12px; color: #606773; }
QPushButton { font-size: 12px; font-weight: 500; padding: 8px 13px; border: 1px solid #cdd6e3; border-radius: 6px; background: #ffffff; }
QPushButton:hover { background: #f4f7fc; border-color: #a8bbd6; }
QPushButton:pressed { background: #eaf0fa; }
QPushButton:focus { border-color: #175cd3; }
QPushButton:disabled { color: #687382; background: #f3f5f8; border-color: #dfe5ee; }
QPushButton[primary="true"] { background: #175cd3; color: #ffffff; border-color: #175cd3; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #124db5; border-color: #124db5; }
QPushButton[primary="true"]:pressed { background: #1047a4; }
QPushButton[primary="true"]:disabled { background: #edf1f7; color: #687382; border-color: #dfe5ee; }
QPushButton[quiet="true"] { border-color: transparent; color: #52617a; padding: 7px 10px; background: transparent; }
QPushButton[quiet="true"]:hover { background: #eef3fa; color: #175cd3; }
QPushButton[quiet="true"]:focus { border-color: #175cd3; }
QPushButton[quiet="true"]:disabled { color: #687382; }
QPushButton[nav="true"] { text-align: left; background: transparent; border: 1px solid transparent; padding: 0; border-radius: 7px; }
QPushButton[nav="true"]:hover { background: #edf1f8; }
QPushButton[nav="true"]:checked { background: #e4ecfc; }
QPushButton[nav="true"]:focus { border-color: #175cd3; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #cdd6e3; border-radius: 6px; padding: 7px 10px; min-height: 20px; selection-background-color: #dce8ff; selection-color: #163e83; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #a8bbd6; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #175cd3; background: #fbfcff; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { background: #f6f8fb; color: #687382; border-color: #dfe5ee; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; }
QComboBox::down-arrow { image: url("@assets/chevron-down.svg"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #cdd6e3; padding: 5px; selection-background-color: #e4ecfc; selection-color: #174aab; outline: none; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 3px 7px; }
QSpinBox, QDoubleSpinBox { padding-right: 26px; }
QSpinBox QLineEdit, QDoubleSpinBox QLineEdit { border: none; background: transparent; padding: 0; min-height: 0; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 24px; border: none; margin: 3px 3px 0 0; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 24px; border: none; margin: 0 3px 3px 0; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("@assets/chevron-up.svg"); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("@assets/chevron-down.svg"); width: 10px; height: 10px; }
QCheckBox { font-size: 12px; spacing: 9px; padding: 6px 0; border: 1px solid transparent; }
QCheckBox:focus { border-color: #175cd3; border-radius: 4px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #a6b2c4; border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:hover { border-color: #175cd3; }
QCheckBox::indicator:checked { background: #175cd3; border-color: #175cd3; image: url("@assets/check-white.svg"); }
QCheckBox::indicator:disabled { background: #f3f5f8; border-color: #cdd6e3; }
QCheckBox::indicator:checked:disabled { background: #e4eaf3; image: url("@assets/check-muted.svg"); }
QToolButton[disclosure="true"] { font-size: 12px; color: #52617a; text-align: left; background: transparent; border: none; border-top: 1px solid #e1e5ec; padding: 12px 0; }
QToolButton[disclosure="true"]:hover { color: #175cd3; }
QToolButton[disclosure="true"]:focus { border: 1px solid #175cd3; border-radius: 4px; }
QPlainTextEdit, QTableWidget { background: #f8fafc; border: 1px solid #e1e5ec; border-radius: 6px; }
QHeaderView::section { background: #f6f8fb; padding: 8px; border: none; border-bottom: 1px solid #e1e5ec; font-weight: 500; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #b9c3d2; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #8c9db5; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: #b9c3d2; border-radius: 3px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QSlider::groove:horizontal { height: 7px; border-radius: 3px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #e2c79e,stop:0.25 #b6d2c1,stop:0.75 #b6d2c1,stop:1 #d3d9e2); }
QSlider::handle:horizontal { background: #175cd3; border: 3px solid #ffffff; width: 20px; margin: -8px 0; border-radius: 12px; }
QSlider::groove:horizontal:disabled { background: #e1e5ec; }
QSlider::handle:horizontal:disabled { background: #929aa6; }
QSlider:focus { border: 1px solid #175cd3; border-radius: 6px; }
QStatusBar { font-size: 11px; background: #fafbfc; color: #606773; border-top: 1px solid #e1e5ec; }
QStatusBar QLabel { font-size: 11px; color: #606773; }
QStatusBar::item { border: none; }
QWidget#route { background: #f8fafc; border: 1px solid #e1e7f0; border-radius: 10px; }
QWidget#signalRoute { background: #ffffff; border: 1px solid #e1e5ec; border-radius: 8px; }
QLabel#routeCaption { background: #f8fafc; color: #606773; padding: 12px 15px; border-bottom: 1px solid #e1e5ec; font-size: 12px; }
QWidget[routeRow="true"] { border-bottom: 1px solid #e1e5ec; }
QWidget#profiles { border: 1px solid #cdd6e3; background: #f8fafc; border-radius: 7px; }
QPushButton[profile="true"] { background: transparent; color: #606773; border: 1px solid transparent; border-radius: 4px; padding: 7px 8px; }
QPushButton[profile="true"]:checked { background: #ffffff; color: #252a32; border-color: #dce3ed; font-weight: 600; }
QPushButton[profile="true"]:focus { border-color: #175cd3; }
QWidget#profiles:disabled { background: #f6f8fb; border-color: #dfe5ee; }
QPushButton[profile="true"]:disabled { color: #687382; background: transparent; border-color: transparent; }
QPushButton[profile="true"]:checked:disabled { color: #687382; background: #edf1f7; border-color: #dfe5ee; font-weight: 400; }
QProgressBar { background: #e7ecf3; color: #252a32; border: none; border-radius: 3px; min-height: 5px; max-height: 5px; }
QProgressBar::chunk { background: #175cd3; border-radius: 3px; }
"""
