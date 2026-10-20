from gui_harness import run_gui

CONNECT_SCRIPT = r"""
import hashlib, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np, soundfile as sf
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.ui import project_io
inputs = Path(tempfile.mkdtemp())
for name in ("inputTrunc.wav", "validation.wav"):
    sf.write(inputs / name, np.zeros(4800, dtype=np.float32), 48000)
project_io.FILES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
from parametric_mac.gui import MacWindow
window = MacWindow(); window._inputs_dir = inputs
window._has_device = lambda: True
window._device_sample_rate = lambda: 48000
window.input_channel_spin.setRange(1, 8)  # The mocked sound card has multiple inputs, even on a host with none.
window.resize(1140, 900); window.show(); app.processEvents()
window._start_new_capture(); window.gear_next_button.click(); app.processEvents()
assert window.current_step() == "connect"
# Find is the main path; the channel numbers sit under Expert settings.
assert window.card_stage.title.text() == "Find the connection" and window.find_button.isVisible()
assert window.audio_advanced.isAncestorOf(window.input_channel_spin) and not window.input_channel_spin.isVisible()
route = lambda peak: SimpleNamespace(ok=True, loopback_failed=False, loopback_used=False, loopback_disagreement=False,
                                     crosscheck=None, peak=peak, latency=SimpleNamespace(delay=17, peak_delay=17.0))

# Next waits for the checkbox and a good level.
assert not window.connect_button.isEnabled()
window._on_route_test_success(route(-9.0)); app.processEvents()
assert not window.connect_button.isEnabled(), "the checkbox is still off"
window.wire_check.setChecked(True); window._on_route_test_success(route(-9.0)); app.processEvents()
assert window.connect_button.isEnabled() and window._route_ready()
assert window.level_result.text().startswith("Peak −9.0 dB"), window.level_result.text()
assert window.level_meter.peak == -9.0

# A clipped level is not ready.
window._on_route_test_success(route(-0.5)); app.processEvents()
assert not window.connect_button.isEnabled() and "clipping" in window.level_result.text()

# A channel change invalidates the check.
window._on_route_test_success(route(-9.0)); assert window.connect_button.isEnabled()
window.input_channel_spin.setValue(window.input_channel_spin.value() + 1); app.processEvents()
assert not window.connect_button.isEnabled()

# A wrong sample rate blocks and offers Audio MIDI Setup.
window.input_channel_spin.setValue(window.input_channel_spin.value() - 1)
window._on_route_test_success(route(-9.0))
window._device_sample_rate = lambda: 44100; window._sync_states(); app.processEvents()
assert not window.connect_button.isEnabled()
assert "44.1 kHz" in window.sample_rate_message_label.text() and window.audio_midi_button.isVisible()
window._device_sample_rate = lambda: 48000; window._sync_states()

# Reopen: checkbox off, level cleared, not ready.
folder = window.project_dir
window._open_project(folder); app.processEvents()
assert window.current_step() == "connect"
assert not window.wire_check.isChecked() and not window.connect_button.isEnabled()
assert window.level_meter.peak is None and window.level_result.text() == ""

# Amp: load box in the chain and the warning before it.
window.go_to_step("gear"); window.gear_kind.setCurrentIndex(1); window.go_to_step("connect"); app.processEvents()
assert "Load box" in window.cable_chain.node_titles() and window.amp_warning.isVisible()
assert any("load box" in text.lower() for text in window.needs_list())

# Help disclosure.
window.connect_help_toggle.click(); app.processEvents()
help_text = window.connect_help.text()
assert window.connect_help.isVisible()
for words in ("No sound card", "sample rate", "No signal", "clipping"):
    assert words.lower() in help_text.lower(), words
print("OK")
"""


def test_connect_stages():
    run_gui(CONNECT_SCRIPT)


def test_connect_messages_are_readable():
    run_gui(r"""
from PySide6.QtWidgets import QApplication
app = QApplication([])
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show()
window._has_device = lambda: True; window._device_sample_rate = lambda: 44100
window._file_sample_rate = lambda: 48000
window.go_to_step("connect"); window._sync_states(); app.processEvents()
message = window.sample_rate_message_label
assert message.isVisible() and message.width() > 300, message.width()
assert message.height() >= message.heightForWidth(message.width()), (message.height(), message.heightForWidth(message.width()))
for stage in (window.wire_stage, window.card_stage, window.level_stage):
    assert stage.badge.width() == 22 and stage.badge.geometry().right() < stage.title.geometry().left()
print("OK")
""")


def test_connect_is_locked_during_jobs_and_keeps_failure_reasons():
    run_gui(r"""
import sys
from types import SimpleNamespace
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
app = QApplication([])
import nam.capture.gui.main as upstream
upstream._QMessageBox.critical = staticmethod(lambda *args, **kwargs: None)  # upstream's modal box
from parametric_mac.gui import MacWindow
window = MacWindow(); window.resize(1140, 900); window.show()
window._has_device = lambda: True; window._device_sample_rate = lambda: 48000
window.go_to_step("connect"); window.wire_check.setChecked(True); app.processEvents()

failed = SimpleNamespace(ok=True, loopback_failed=True, loopback_used=True, loopback_disagreement=False,
                         crosscheck=None, peak=-9.0, latency=SimpleNamespace(delay=17, peak_delay=17.0))
window._on_route_test_success(failed); app.processEvents()
text = window.level_result.text()
assert text and "did not pass" not in text and "⚠" not in text, text
assert not window.connect_button.isEnabled()
assert window.route_test_progress.isHidden()
assert window.no_devices_label.styleSheet() == ""

job = QProcess(); job.start(sys.executable, ["-c", "import time; time.sleep(5)"]); assert job.waitForStarted(5000)
window.process = job; window._sync_states(); app.processEvents()
for widget in (window.device_combo, window.wire_check, window.output_channel_spin, window.check_level_button,
               window.find_button):
    assert not widget.isEnabled(), widget
job.kill(); job.waitForFinished(3000); window.process = None
print("OK")
""")
