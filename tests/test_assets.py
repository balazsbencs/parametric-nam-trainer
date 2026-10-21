import io
import hashlib
from pathlib import Path
import pytest
from parametric_mac import assets


def test_verified_download_and_repeat(tmp_path, monkeypatch):
    data = b'valid fixture'
    monkeypatch.setattr(assets, 'FILES', {'test.wav': hashlib.sha256(data).hexdigest()})
    monkeypatch.setattr(assets, 'urlopen', lambda *a, **kw: io.BytesIO(data))
    assets.download_inputs(tmp_path)
    assets.download_inputs(tmp_path)
    assert (tmp_path / 'test.wav').read_bytes() == data


def test_corrupt_download_is_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, 'FILES', {'test.wav': 'wrong'})
    monkeypatch.setattr(assets, 'urlopen', lambda *a, **kw: io.BytesIO(b'bad'))
    with pytest.raises(ValueError, match='Checksum mismatch'):
        assets.download_inputs(tmp_path)
    assert not list(tmp_path.iterdir())


def test_existing_file_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, 'FILES', {'test.wav': 'wrong'})
    (tmp_path / 'test.wav').write_bytes(b'user audio')
    with pytest.raises(ValueError, match='different contents'):
        assets.download_inputs(tmp_path)
    assert (tmp_path / 'test.wav').read_bytes() == b'user audio'


UI_ASSETS = Path(__file__).resolve().parents[1] / "parametric_mac" / "ui_assets"


def test_geist_fonts_are_bundled_with_license():
    names = {"Geist-Regular.ttf", "Geist-Medium.ttf", "Geist-SemiBold.ttf",
             "GeistMono-Regular.ttf", "GeistMono-Medium.ttf", "Geist-OFL.txt"}
    assert names <= {p.name for p in UI_ASSETS.iterdir()}
    assert not list(UI_ASSETS.glob("Inter-*"))


def test_geist_fonts_load_in_qt():
    from gui_harness import run_gui
    run_gui("""
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication
from parametric_mac.theme import ASSETS, FONT_FILES, MONO_FAMILY, install_typography, mono_font
app = QApplication([])
assert install_typography() == "Geist"
for name in FONT_FILES:
    families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(ASSETS / name)))
    # Fontconfig on Linux can also expose the font's weight-specific family alias.
    assert ("Geist Mono" if name.startswith("GeistMono") else "Geist") in families, (name, families)
assert {"Regular", "Medium", "SemiBold"} <= set(QFontDatabase.styles("Geist")), QFontDatabase.styles("Geist")
assert {"Regular", "Medium"} <= set(QFontDatabase.styles(MONO_FAMILY)), QFontDatabase.styles(MONO_FAMILY)
assert QFontInfo(app.font()).family() == "Geist", QFontInfo(app.font()).family()
semibold = QFont("Geist"); semibold.setWeight(QFont.DemiBold)
assert QFontInfo(semibold).styleName() == "SemiBold", QFontInfo(semibold).styleName()
mono = mono_font(13)
assert QFontInfo(mono).family() == MONO_FAMILY and mono.pixelSize() == 13
assert mono.isFeatureSet(QFont.Tag("tnum")) and mono.featureValue(QFont.Tag("tnum")) == 1
print("OK")
""")
