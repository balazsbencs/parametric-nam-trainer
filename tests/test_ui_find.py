from gui_harness import run_gui

SETUP = r"""
import threading, time
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
app = QApplication([])
import nam.capture.gui.main as upstream
upstream._QMessageBox.critical = staticmethod(lambda *args, **kwargs: None)  # upstream's modal boxes
upstream._QMessageBox.warning = staticmethod(lambda *args, **kwargs: None)
from nam.capture.audio import AudioDropoutError, CaptureCancelled, DeviceInfo
from parametric_mac.find_route import FindResult, Route
from parametric_mac.find_scan import ScanTarget
from parametric_mac.ui.copy import CLIP_TEXT
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show()
window._has_device = lambda: True; window._device_sample_rate = lambda: 48000
window.device_combo.addItem("Test interface", DeviceInfo(5, "Test interface", "Core Audio", 4, 4, 48000.0))
window.device_combo.setCurrentIndex(window.device_combo.count() - 1)
window.go_to_step("connect"); app.processEvents()

def wait_idle():
    end = time.monotonic() + 5
    while window._worker is not None and time.monotonic() < end:
        QTest.qWait(20)
    assert window._worker is None, "the scan did not finish"
    app.processEvents()

def run_find(scan):
    targets = []
    def fake(target, progress, cancel):
        assert isinstance(target, ScanTarget), type(target)  # plain values, never widgets
        targets.append(target)
        return scan(target, progress, cancel)
    window._scan_outputs = fake
    assert window.find_button.isEnabled()
    window.find_button.click(); wait_idle()
    return targets

def channels():
    return window.output_channel_spin.value(), window.input_channel_spin.value()

def saved():
    audio = window._current_audio_settings()
    return audio.output_channel, audio.input_channel

def set_channels(output, input_):
    window.output_channel_spin.setValue(output); window.input_channel_spin.setValue(input_)
    window._save_audio_settings(); app.processEvents()
"""


def test_find_results_set_or_keep_the_channels():
    run_gui(SETUP + r"""
# The stage is renamed and the channel fields live under Expert settings.
assert window.card_stage.title.text() == "Find the connection"
assert window.audio_advanced.isAncestorOf(window.output_channel_spin)
assert not window.output_channel_spin.isVisible()

# Enabled only after the safety checkbox, and never with a sample-rate problem.
assert not window.find_button.isEnabled()
window.wire_check.setChecked(True); app.processEvents()
assert window.find_button.isEnabled() and window.find_button.text() == "Find my connection"
window._device_sample_rate = lambda: 44100; window._file_sample_rate = lambda: 48000; window._sync_states()
assert not window.find_button.isEnabled()
window._device_sample_rate = lambda: 48000; window._sync_states()

# Found: channels set and saved, level check cleared, loopback listed in Expert settings.
set_channels(1, 2); window._show_level(-9.0); window._route_fingerprint = "old"
found = FindResult("found", (Route(2, 1, -18.0, ()),), (3,))
targets = run_find(lambda target, progress, cancel: found)
assert (targets[0].device_index, targets[0].output_channels, targets[0].input_channels) == (5, 4, 4)
assert targets[0].sample_rate == 48000 and targets[0].excluded_inputs == frozenset()
assert channels() == (2, 1) and saved() == (2, 1)
assert window.find_result.text().startswith("Found: Output 2 → Input 1."), window.find_result.text()
assert window.find_loopback_note.text() == "Input 3 looks like a loopback — ignored"
assert window.level_meter.peak is None and window._route_fingerprint is None
assert window.find_button.text() == "Find my connection" and window.find_button.isEnabled()
assert window.route_test_progress.isHidden()

# The user's own timing loopback input is never offered as the route.
window.loopback_check.setChecked(True); window.loopback_input_channel_spin.setValue(4)
targets = run_find(lambda target, progress, cancel: found)
assert targets[0].excluded_inputs == frozenset({4})
window.loopback_check.setChecked(False)

# None: channels kept, Try again and Choose channels myself offered.
set_channels(1, 2)
run_find(lambda target, progress, cancel: FindResult("none", (), ()))
assert channels() == (1, 2) and saved() == (1, 2)
assert window.find_result.text().startswith("No signal came back."), window.find_result.text()
assert window.find_try_again.isVisible() and window.find_manual.isVisible()
assert window.find_loopback_note.isHidden()
window.find_manual.click(); app.processEvents()
assert window.audio_advanced.isVisible() and window.output_channel_spin.isVisible()
assert "turn its volume" in window.find_result.text()
locked = window._plan_locked
window._plan_locked = lambda: True  # recording has started: levels stay fixed (spec §4.3)
run_find(lambda target, progress, cancel: FindResult("none", (), ()))
assert window.find_result.text().startswith("No signal came back.") and "turn its volume" not in window.find_result.text()
window._plan_locked = locked
window._route_fingerprint = "checked"  # a passed level check: "Do not touch the sound card gain"
run_find(lambda target, progress, cancel: FindResult("none", (), ()))
assert "turn its volume" not in window.find_result.text()
window._route_fingerprint = None

# Cancel: nothing changes.
def cancelled(target, progress, cancel):
    raise CaptureCancelled()
run_find(cancelled)
assert channels() == (1, 2) and saved() == (1, 2) and window.find_result.text() == "Search cancelled."

# Dropout: plain words, never the raw error.
def dropout(target, progress, cancel):
    raise AudioDropoutError("PortAudio error -9986 internal detail")
run_find(dropout)
text = window.find_result.text()
assert text == "The sound card stopped during the search. Check that nothing else uses it, then try again.", text
assert channels() == (1, 2) and window.find_try_again.isVisible()

# Try again runs the search again.
window._scan_outputs = lambda target, progress, cancel: FindResult("found", (Route(2, 1, -18.0, ()),), ())
window.find_try_again.click(); wait_idle()
assert channels() == (2, 1) and window.find_try_again.isHidden()
set_channels(1, 2)

# Several: one link per route; a link uses that route.
several = FindResult("several", (Route(2, 1, -18.0, ()), Route(3, 4, -30.0, ())), ())
run_find(lambda target, progress, cancel: several)
assert window.find_result.text().startswith("More than one connection answered.")
links = [b for b in window.find_route_links.findChildren(QPushButton) if b.isVisible()]
assert [b.text() for b in links] == ["Use Output 2 → Input 1", "Use Output 3 → Input 4"], [b.text() for b in links]
assert window.find_try_again.isVisible() and window.find_manual.isVisible()  # a way out if neither is right
links[1].click(); app.processEvents()
assert channels() == (3, 4) and saved() == (3, 4)
assert window.find_result.text().startswith("Found: Output 3 → Input 4.") and window.find_route_links.isHidden()

# Clipping: the route is still used, with the clip advice.
run_find(lambda target, progress, cancel: FindResult("found", (Route(2, 1, -0.5, ()),), ()))
assert channels() == (2, 1) and CLIP_TEXT in window.find_result.text()

# A big device stops at the first answer and says so in Expert settings.
assert window.find_stop_note.isHidden()
run_find(lambda target, progress, cancel: FindResult("found", (Route(2, 1, -18.0, ()),), (), True))
assert window.find_stop_note.text() == "Stopped at the first answer: this sound card has 4 outputs."
assert "Check that Output 2 goes to the reamp box." in window.find_result.text(), window.find_result.text()
assert not window.find_stop_note.isHidden()

# Another sound card: the old result and its route links no longer apply.
run_find(lambda target, progress, cancel: several)
assert not window.find_route_links.isHidden()
window.device_combo.addItem("Other interface", DeviceInfo(6, "Other interface", "Core Audio", 2, 2, 48000.0))
window.device_combo.setCurrentIndex(window.device_combo.count() - 1); app.processEvents()
assert window.find_route_links.isHidden() and window.find_result.text() == "", window.find_result.text()
assert window.find_stop_note.isHidden()

# A new or reopened project starts without the old search result.
window._reset_connect(); app.processEvents()
assert window.find_result.text() == "" and window.find_stop_note.isHidden() and window.find_loopback_note.isHidden()
assert window.find_try_again.isHidden() and window.find_route_links.isHidden()
print("OK")
""")


def test_find_can_be_cancelled_while_it_runs():
    run_gui(SETUP + r"""
window.wire_check.setChecked(True); set_channels(1, 2); app.processEvents()
gate = threading.Event()
def blocking(target, progress, cancel):
    progress(0.25)
    while not cancel():
        if gate.wait(0.02):
            break
    raise CaptureCancelled()
window._scan_outputs = blocking
try:
    window.find_button.click(); QTest.qWait(150); app.processEvents()
    assert window._worker is not None
    assert not window.device_combo.isEnabled() and not window.check_level_button.isEnabled()
    assert window.find_button.text() == "Cancel search" and window.find_button.isEnabled()
    assert not window.route_test_progress.isHidden()
    window.find_button.click(); wait_idle()
    assert window.find_result.text() == "Search cancelled."
    assert channels() == (1, 2) and saved() == (1, 2)
    assert window.find_button.text() == "Find my connection" and window.device_combo.isEnabled()
finally:
    gate.set()
print("OK")
""")
