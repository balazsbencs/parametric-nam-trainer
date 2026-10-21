from gui_harness import run_gui

SETUP = r'''
import hashlib, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication
app = QApplication([])
from nam.capture.audio import DeviceInfo
import nam.capture.audio as audio
import nam.capture.gui.main as upstream
from parametric_mac import device_rates
from parametric_mac.ui import project_io
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
def dev(i, ins, outs, name="USB Audio CODEC"):
    return DeviceInfo(i, name, "Core Audio", ins, outs, 48000)
blackhole = dev(0, 2, 2, "BlackHole 2ch")
pair = [dev(2, 0, 2), dev(3, 2, 0)]
devices = [blackhole, *pair, dev(4, 1, 0, "Microphone")]
upstream._list_devices = lambda **kw: devices
audio.list_devices = lambda **kw: devices
device_rates.live_half_transports = lambda: {}
device_rates.live_half_rates = lambda: {}
device_rates.live_device_state = lambda: (device_rates.live_half_rates(), device_rates.live_half_transports())
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window.resize(1140, 900); window.show(); app.processEvents()
window._start_new_capture(); window.gear_next_button.click(); app.processEvents()
def choose(name):
    window.device_combo.setCurrentIndex(next(i for i in range(window.device_combo.count())
                                           if window.device_combo.itemData(i).name == name))
    app.processEvents()
def refresh():
    window._refresh_devices(); window._sync_states(); app.processEvents()
'''


def test_cards_list_save_and_notices():
    run_gui(SETUP + r'''
assert [window.device_combo.itemText(i) for i in range(window.device_combo.count())] == [
    "BlackHole 2ch (Core Audio) · 2 in · 2 out", "USB Audio CODEC (Core Audio) · 2 in · 2 out"]
assert window.device_combo.placeholderText() == "Choose a sound card"
assert not window.project.audio.loopback_enabled
assert window.device_combo.currentIndex() == -1
choose("USB Audio CODEC")
assert window.project.audio.input_device == window.project.audio.output_device == "USB Audio CODEC"
devices = [*pair, dev(4, 1, 0, "Microphone"), dev(5, 0, 2, "Speakers")]
refresh()
assert window.device_combo.count() == 1 and window.no_devices_label.isHidden()
devices = [blackhole, *pair, dev(6, 0, 2), dev(7, 2, 0)]
refresh()
assert window.device_combo.count() == 1 and window.device_combo.currentIndex() == -1
assert 'Two sound cards are called “USB Audio CODEC”' in window.card_notice.text()
choose("BlackHole 2ch"); window.wire_check.setChecked(True); app.processEvents()
assert window.find_button.isEnabled()
assert "Two sound cards with the same name: unplug one, then press refresh." in window.connect_help.text()
print("OK")
''')


def test_missing_project_card_is_never_saved_over_and_returns_on_refresh():
    run_gui(SETUP + r'''
choose("USB Audio CODEC")
folder = window.project_dir
project_file = folder / "capture_project.json"
before = project_file.read_bytes()
devices = [blackhole]
refresh(); window._open_project(folder); app.processEvents()
assert window.device_combo.currentIndex() == -1
assert 'This project used “USB Audio CODEC”, which is not connected.' in window.card_notice.text()
window.wire_check.setChecked(True); window._sync_states()
assert not window.find_button.isEnabled() and not window.check_level_button.isEnabled()
assert not window.connect_button.isEnabled()
window._save_audio_settings()
assert project_file.read_bytes() == before
assert window.project.audio.output_device == "USB Audio CODEC"
devices = [blackhole, *pair]; refresh()
assert window.device_combo.currentData().name == "USB Audio CODEC"
assert window.card_notice.isHidden()
# Identical duplex cards also make a saved name ambiguous.
choose("BlackHole 2ch")
devices = [blackhole, dev(9, 2, 2, "BlackHole 2ch")]; refresh()
assert window.device_combo.currentIndex() == -1
assert 'This project used “BlackHole 2ch”' not in window.card_notice.text()
assert 'Two sound cards are called “BlackHole 2ch”' in window.card_notice.text()
print("OK")
''')


def test_split_rate_blocks_every_action_and_names_the_wrong_half():
    run_gui(SETUP + r'''
choose("USB Audio CODEC")
device_rates.live_half_rates = lambda: {("USB Audio CODEC", "input"): 44100,
                                      ("USB Audio CODEC", "output"): 48000}
window.wire_check.setChecked(True); window._sync_states(); app.processEvents()
assert window.sample_rate_label.text() == "in 44.1 kHz · out 48 kHz"
window.resize(800, 680); app.processEvents()
assert window.sample_rate_label.width() >= window.sample_rate_label.sizeHint().width()
assert window.device_combo.width() > 100
assert window.sample_rate_message_label.text().startswith("The input of your sound card runs at 44.1 kHz.")
for widget in (window.find_button, window.check_level_button, window.connect_button):
    assert not widget.isEnabled()
assert window._current_sample_rate_warnings()
device_rates.live_half_rates = lambda: {("USB Audio CODEC", "input"): 48000,
                                      ("USB Audio CODEC", "output"): 44100}
window._sync_states()
assert window.sample_rate_message_label.text().startswith("The output of your sound card")
print("OK")
''')


def test_find_resolves_split_indexes_again_and_refuses_missing_or_ambiguous_cards():
    run_gui(SETUP + r'''
from parametric_mac.find_route import FindResult, Route
from parametric_mac.ui.copy import FIND_FAILED_TEXT
from PySide6.QtTest import QTest
choose("USB Audio CODEC"); window.wire_check.setChecked(True)
assert window.device_combo.currentData().input_index == 3
seen = []
def scan(target, progress, cancel):
    seen.append(target)
    return FindResult("found", (Route(1, 1, -18, ()),), ())
window._scan_outputs = scan
devices = [blackhole, dev(4, 0, 2), dev(5, 2, 0)]
window.find_button.click()
for _ in range(250):
    if window._worker is None:
        break
    QTest.qWait(20)
assert len(seen) == 1
assert (seen[0].input_index, seen[0].output_index) == (5, 4)
assert window.find_result.text() == "Found: Output 1 → Input 1."
for devices in ([blackhole], [blackhole, *pair, dev(6, 0, 2), dev(7, 2, 0)]):
    window.find_button.click(); app.processEvents()
    assert len(seen) == 1
    assert window.find_result.text() == FIND_FAILED_TEXT
    assert window.find_try_again.isVisible()
print("OK")
''')
