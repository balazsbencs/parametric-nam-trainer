from gui_harness import run_gui
from test_ui_cards import SETUP


def test_empty_poll_preserves_each_known_rate_and_the_block():
    run_gui(SETUP + r'''
choose("USB Audio CODEC"); window.wire_check.setChecked(True)
device_rates.live_half_rates = lambda: {("USB Audio CODEC", "input"): 44100, ("USB Audio CODEC", "output"): 48000}
window._sync_states()
text = window.sample_rate_label.text()
assert not window.find_button.isEnabled()
device_rates.live_half_rates = lambda: {}
window._refresh_sample_rate_warning(); app.processEvents()
assert window.sample_rate_label.text() == text
assert not window.find_button.isEnabled() and not window.check_level_button.isEnabled()
device_rates.live_half_rates = lambda: {("USB Audio CODEC", "input"): 48000}
window._refresh_sample_rate_warning()
assert window.sample_rate_label.text() == "48 kHz" and window.find_button.isEnabled()
print("OK")
''')


def test_refresh_clears_found_route_choices_and_level_proof():
    run_gui(SETUP + r'''
from parametric_mac.find_route import Route
from PySide6.QtWidgets import QPushButton
choose("USB Audio CODEC"); window.wire_check.setChecked(True)
route = Route(1, 1, -18, ())
window._show_find("Several routes", "muted", (route,), retry=True)
old_link = window.find_route_links.findChildren(QPushButton)[0]
window._show_level(-9); window._route_fingerprint = window.project.audio.stream_fingerprint()
devices = [blackhole]; refresh()
assert window.find_result.text() == "" and window.find_route_links.isHidden()
assert window.level_meter.peak is None and window._route_fingerprint is None
before = window.project.audio.model_dump()
window._use_route(route)
assert window.find_result.text() == "" and window.project.audio.model_dump() == before
print("OK")
''')


def test_new_capture_clears_missing_card_but_does_not_rewrite_old_project():
    run_gui(SETUP + r'''
choose("USB Audio CODEC"); folder = window.project_dir
devices = [blackhole]; refresh()
assert "not connected" in window.card_notice.text()
before = (folder / "capture_project.json").read_bytes()
window._start_new_capture(); app.processEvents()
assert window._missing_card is None and "USB Audio CODEC" not in window.card_notice.text()
window.gear_next_button.click(); app.processEvents()
assert "USB Audio CODEC" not in window.card_notice.text()
assert (folder / "capture_project.json").read_bytes() == before
print("OK")
''')


def test_only_ambiguous_cards_give_one_consistent_instruction():
    run_gui(SETUP + r'''
choose("USB Audio CODEC")
devices = [*pair, dev(6, 0, 2), dev(7, 2, 0)]; refresh()
assert window.no_devices_label.isHidden()
assert "Unplug one" in window.card_notice.text()
assert "not connected" not in window.card_notice.text()
assert not window.find_button.isEnabled()
print("OK")
''')


def test_expert_edits_persist_without_changing_missing_card_or_main_channels():
    run_gui(SETUP + r'''
choose("USB Audio CODEC")
window.output_channel_spin.setValue(2); window.input_channel_spin.setValue(2)
folder = window.project_dir
devices = [blackhole]; refresh()
assert window.device_combo.currentIndex() == -1
window.buffer_size_combo.setCurrentIndex(window.buffer_size_combo.findData(512))
window.latency_combo.setCurrentIndex(1)
window.loopback_check.setChecked(True)
window.loopback_input_channel_spin.setValue(2)
window._save_audio_settings()
from parametric_mac.controls import load_project
audio_settings = load_project(folder).audio
assert audio_settings.output_device == audio_settings.input_device == "USB Audio CODEC"
assert audio_settings.output_channel == audio_settings.input_channel == 2
assert audio_settings.blocksize == 512 and audio_settings.latency == window.latency_combo.currentData()
assert audio_settings.loopback_enabled and audio_settings.loopback_input_channel == 2
print("OK")
''')


def test_standalone_split_rates_block_find_and_level_check():
    run_gui(SETUP + r'''
window._start_new_capture(); choose("USB Audio CODEC")
assert window.project is None
device_rates.live_half_rates = lambda: {("USB Audio CODEC", "input"): 44100, ("USB Audio CODEC", "output"): 48000}
window.wire_check.setChecked(True); window._sync_states()
assert window._rate_problem() and not window.find_button.isEnabled() and not window.check_level_button.isEnabled()
print("OK")
''')


def test_find_reinitializes_portaudio_once_and_never_while_worker_is_active():
    run_gui(SETUP + r'''
choose("USB Audio CODEC"); window.wire_check.setChecked(True)
calls = []
def enumerate_devices(refresh=False):
    calls.append(refresh)
    return [dev(4, 0, 2), dev(5, 2, 0)] if refresh else pair
audio.list_devices = enumerate_devices
target = window._find_target()
assert calls == [True] and (target.input_index, target.output_index) == (5, 4)
calls.clear()
window._worker = object()
assert window._find_target() is None and calls == []
window._worker = None
print("OK")
''')


def test_rate_poll_reads_one_snapshot_and_caches_wav_headers():
    run_gui(SETUP + r'''
choose("USB Audio CODEC")
import parametric_mac.ui.pages.connect as connect
calls, headers = [], []
def snapshot():
    calls.append(1)
    return {}, {}
device_rates.live_device_state = snapshot
original = connect.read_wav_rate
def read(path):
    headers.append(path)
    return original(path)
connect.read_wav_rate = read
# Warm the header cache, then steady polls must not reopen the WAV files.
window._refresh_sample_rate_warning()
calls.clear(); headers.clear()
window._refresh_sample_rate_warning()
assert len(calls) == 1, len(calls)
assert not headers, headers
print("OK")
''')


def test_empty_snapshot_does_not_readmit_a_known_bluetooth_pair():
    run_gui(SETUP + r'''
devices = [blackhole, dev(6, 2, 0, "AirPods"), dev(7, 0, 2, "AirPods")]
device_rates.live_half_transports = lambda: {("AirPods", "input"): "blue", ("AirPods", "output"): "blue"}
refresh()
assert window.device_combo.count() == 1
device_rates.live_half_transports = lambda: {}
refresh()
assert window.device_combo.count() == 1 and window.device_combo.itemData(0).name == "BlackHole 2ch"
print("OK")
''')


def test_wav_cache_notices_replaced_input_and_blocks_its_new_rate():
    run_gui(SETUP + r'''
choose("USB Audio CODEC"); window.wire_check.setChecked(True)
assert window._file_sample_rate() == 48000
sf.write(window.project_dir / window.project.train_input, np.zeros(4200, dtype=np.float32), 44100)
window._refresh_sample_rate_warning()
assert window._file_sample_rate() == 44100
assert window._current_sample_rate_warnings()
assert not window.find_button.isEnabled() and not window.check_level_button.isEnabled()
print("OK")
''')
