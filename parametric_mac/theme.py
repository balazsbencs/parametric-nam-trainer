"""Bundled Geist typography and vector icons, rendered by Qt."""
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).with_name('ui_assets')
UI_FAMILY = 'Geist'
MONO_FAMILY = 'Geist Mono'
FONT_FILES = ('Geist-Regular.ttf', 'Geist-Medium.ttf', 'Geist-SemiBold.ttf',
              'GeistMono-Regular.ttf', 'GeistMono-Medium.ttf')
_loaded = False


def _load_fonts() -> None:
    global _loaded
    if _loaded:
        return
    for name in FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(ASSETS / name))
        if not QFontDatabase.applicationFontFamilies(font_id):
            raise RuntimeError(f'Could not load bundled font {name}. Reinstall the application source.')
    _loaded = True


def install_typography() -> str:
    """Load the bundled fonts and set Geist as the application font. Returns the UI family."""
    _load_fonts()
    font = QFont(UI_FAMILY)
    font.setPixelSize(13)
    font.setWeight(QFont.Normal)
    QApplication.instance().setFont(font)
    return UI_FAMILY


def mono_font(pixel_size: int) -> QFont:
    """Geist Mono at `pixel_size` pixels with tabular figures, for numbers that change in place."""
    _load_fonts()
    font = QFont(MONO_FAMILY)
    font.setPixelSize(pixel_size)
    font.setFeature(QFont.Tag('tnum'), 1)
    return font


def icon(name):
    return QIcon(str(ASSETS/f'{name}.svg'))
