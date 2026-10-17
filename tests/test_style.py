import re
from pathlib import Path

from parametric_mac.ui.style import build_style_sheet
from parametric_mac.ui.tokens import DARK, LIGHT

ROOT = Path(__file__).resolve().parents[1]
HEX = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b")
# Files that still hold old literals; later tasks delete or convert them and shrink this set to empty (Task 12 asserts empty).
LEGACY_COLOR_FILES = {"parametric_mac/gui.py", "parametric_mac/control_editor.py"}
COLOR = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b|QColor\(\s*\d|rgba?\(")


def test_style_sheet_uses_only_palette_colors():
    for palette in (DARK, LIGHT):
        css = build_style_sheet(palette, Path("x"))
        allowed = {v.lower() for v in vars(palette).values()}
        assert {c.lower() for c in HEX.findall(css)} <= allowed
        assert "rgb" not in css


def test_style_sheet_has_new_selectors():
    css = build_style_sheet(DARK, Path("x"))
    for selector in ('QPushButton[outline="true"]', 'QPushButton[link="true"]', 'QFrame[card="true"]',
                     'QFrame[card="true"][selected="true"]', 'QFrame[alert="error"]', 'QFrame[stage="true"]',
                     "QWidget#topBar", "QWidget#footer", "QWidget#aside", 'QPushButton[primary="true"]'):
        assert selector in css, selector


def test_style_sheet_resolves_asset_paths():
    css = build_style_sheet(DARK, Path("/opt/assets"))
    assert "@assets" not in css and "/opt/assets/chevron-down.svg" in css


def test_no_color_literals_outside_tokens():
    for path in (ROOT / "parametric_mac").rglob("*.py"):
        relative = str(path.relative_to(ROOT))
        if path.name != "tokens.py" and relative not in LEGACY_COLOR_FILES:
            assert not COLOR.search(path.read_text()), relative


def test_appearance_controller_saves_applies_and_ignores_bad_values():
    from gui_harness import run_gui
    run_gui("""
import os
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from parametric_mac.ui.style import AppearanceController, SETTINGS_KEY, settings_from_env
from parametric_mac.ui.tokens import DARK, LIGHT
app = QApplication([])
settings = settings_from_env()
assert settings.fileName().startswith(os.environ["PARAMETRIC_SETTINGS_DIR"]), settings.fileName()
controller = AppearanceController(app, settings)
assert controller.choice() == "system"
fired = []
controller.changed.connect(fired.append)
controller.set_choice("light")
assert LIGHT.bg in app.styleSheet() and fired == [LIGHT], fired
assert controller.palette() is LIGHT
controller.set_choice("dark")
settings.sync()
again = AppearanceController(app, settings_from_env())
assert again.choice() == "dark" and DARK.bg in app.styleSheet()
settings.setValue(SETTINGS_KEY, "purple")
assert AppearanceController(app, settings).choice() == "system"
# A system change matters only when the choice is "system".
fired.clear()
controller.set_choice("dark")
fired.clear()
controller.on_system_scheme_changed()
assert fired == [], fired
controller.set_choice("system")
fired.clear()
controller.on_system_scheme_changed()
assert len(fired) == 1, fired
print("OK")
""")


def test_style_sheet_icons_use_palette_colors(tmp_path, monkeypatch):
    from parametric_mac.ui.style import tinted_assets
    monkeypatch.setenv("PARAMETRIC_SETTINGS_DIR", str(tmp_path))
    for palette in (DARK, LIGHT):
        folder = tinted_assets(palette)
        assert folder.is_relative_to(tmp_path)
        css = build_style_sheet(palette, folder)
        urls = re.findall(r'url\("([^"]+\.svg)"\)', css)
        assert urls
        allowed = {v.lower() for v in vars(palette).values()}
        for url in urls:
            text = Path(url).read_text()
            assert {c.lower() for c in HEX.findall(text)} <= allowed, (url, HEX.findall(text))
    assert LIGHT.on_accent in (tinted_assets(LIGHT) / "check-dark.svg").read_text()


def test_primary_and_outline_buttons_show_focus():
    css = build_style_sheet(DARK, Path("x"))
    assert 'QPushButton[primary="true"]:focus' in css and 'QPushButton[outline="true"]:focus' in css


def test_tinted_assets_falls_back_when_folder_is_not_writable(tmp_path, monkeypatch):
    from parametric_mac.theme import ASSETS
    from parametric_mac.ui.style import tinted_assets
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    monkeypatch.setenv("PARAMETRIC_SETTINGS_DIR", str(blocker))
    assert tinted_assets(DARK) == ASSETS
