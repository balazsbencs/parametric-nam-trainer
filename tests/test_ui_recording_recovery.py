"""Recording recovery must preserve targets, calibration and persisted clipping QA."""
from gui_harness import run_gui
from test_ui_final_fixes import SETUP


def test_warning_actions_cannot_advance_a_running_take():
    run_gui(SETUP + r'''
from nam.capture.project import QAModel
window._start_new_capture(); window.gear_next_button.click()
window.wire_check.setChecked(True); window._on_route_test_success(ROUTE)
window.go_to_step("record"); window.quality_cards[0].clicked.emit(); window.record_start_button.click()
entry = window._shown_entry
entry.status, entry.delay = "captured", 0
entry.qa = QAModel(peak=-12, clipping=False, messages=["Timing warning"])
target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(inputs / "validation.wav", target)
save_project(window.project, window.project_dir)
window._recording_entry = entry
window._on_capture_success(entry.qa); app.processEvents()
assert window.take_alert_keep.isVisible() and window.take_alert_keep.isEnabled()

window._worker, window._cancel_token = object(), object()
window._sync_states()
assert not window.take_alert_keep.isEnabled() and not window.take_alert_new_capture.isEnabled()
assert not window.capture_table.isEnabled()
window.take_alert_keep.click()
window._keep_take()  # Queued callbacks must also respect the busy guard.
other = next(i for i, e in enumerate(window._displayed_entries) if e.y_path != entry.y_path)
window.capture_table.selectRow(other)
window._record_selected()
assert window._shown_entry is entry and window._retry_entry is entry
assert window.take_alert.isVisible()

window._worker = window._cancel_token = None
window._sync_states()
assert window.take_alert_keep.isEnabled()
window.take_alert_keep.click()
assert window._shown_entry.y_path != entry.y_path and window._retry_entry is None
assert not window.take_alert.isVisible()
print("OK")
''')


def test_clipped_retries_survive_reopen_until_every_replacement_is_saved():
    run_gui(SETUP + r'''
from nam.capture.project import QAModel
from parametric_mac.recent import project_status
from parametric_mac.workflow import takes_to_record
window._start_new_capture(); window.gear_next_button.click()
window.go_to_step("record"); window.quality_cards[0].clicked.emit(); window.record_start_button.click()
total = len(window.project.entries)
good = QAModel(peak=-12, clipping=False, messages=[])
for entry in window.project.entries:
    entry.status, entry.delay, entry.qa = "captured", 0, good.model_copy(deep=True)
    target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inputs / "validation.wav", target)
ordered = window._entries_in_display_order()
paths = [ordered[0].y_path, ordered[-1].y_path]
for entry in (ordered[0], ordered[-1]):
    entry.qa = QAModel(peak=0, clipping=True, messages=["Clipping detected"])
# An advisory warning is still usable and must not become a mandatory retry.
ordered[1].qa = QAModel(peak=-12, clipping=False, messages=["Timing warning"])
folder = window.project_dir
save_project(window.project, folder)
original_wavs = {entry.y_path: (folder / entry.y_path).read_bytes() for entry in ordered}

for index, path in enumerate(paths):
    window._open_project(folder); app.processEvents()
    assert window.current_step() == "connect"
    assert project_status(folder).state == "recording"
    assert project_status(folder).captured == total - (2 - index)
    window.go_to_step("record"); app.processEvents()
    assert window._shown_entry.y_path == path and window._retry_entry.y_path == path
    assert window._shown_entry.qa.clipping
    assert window.take_alert.isVisible() and not window.take_alert_keep.isVisible()
    assert window.take_alert_new_capture.isVisible()
    window._keep_take()  # A direct invocation cannot bypass clipping either.
    assert window._retry_entry.y_path == path
    assert not window.capture_continue.isEnabled() and "record" not in window._done_steps()
    assert window.progress_count.text() == f"{total - (2 - index)} / {total}"
    assert "minutes left" in window.time_left_label.text()
    assert "Replace the clipped takes" in window.train_readiness.text()
    assert len(takes_to_record(window.project)) == 2 - index
    window.go_to_step("train")
    assert not window.train_button.isEnabled()
    window._start_training_flow(); assert window.process is None
    window._start("train"); assert window.process is None

    # A cancelled or failed replacement preserves the saved clipped take and retry.
    window.go_to_step("record")
    entry = window._shown_entry
    window._recording_entry = entry
    window._on_capture_cancelled()
    window._on_capture_failure("Synthetic recording failure")
    assert entry.qa.clipping and window._retry_entry is entry
    assert (folder / path).read_bytes() == original_wavs[path]

    # The session saves a successful replacement before it emits its success signal.
    entry.qa = good.model_copy(deep=True)
    save_project(window.project, folder)
    window._on_capture_success(entry.qa); app.processEvents()

assert window._retry_entry is None and window._shown_entry is None
assert not window.take_alert.isVisible()
assert window.capture_continue.isEnabled() and "record" in window._done_steps()
assert window.progress_count.text() == f"{total} / {total}"
assert window.train_button.isEnabled()
assert project_status(folder).state == "recorded"
assert takes_to_record(window.project) == []
print("OK")
''')


def test_locked_level_check_offers_a_new_capture_without_changing_saved_takes():
    run_gui(SETUP + r'''
from nam.capture.project import QAModel
window._start_new_capture(); window.gear_next_button.click()
window.wire_check.setChecked(True)
clipped_route = SimpleNamespace(**{**vars(ROUTE), "peak": -0.5})
window._on_route_test_success(clipped_route); app.processEvents()
assert "down a little" in window.level_result.text()
assert not window.level_new_capture.isVisible()

window.go_to_step("record"); window.quality_cards[0].clicked.emit(); window.record_start_button.click()
entry = window._shown_entry
entry.status, entry.delay = "captured", 0
entry.qa = QAModel(peak=-12, clipping=False, messages=[])
target = window.project_dir / entry.y_path; target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(inputs / "validation.wav", target)
save_project(window.project, window.project_dir)
folder = window.project_dir
window._open_project(folder)
window.wire_check.setChecked(True)
window._on_route_test_success(clipped_route); app.processEvents()
assert window._plan_locked() and not window.connect_button.isEnabled()
assert "gain fixed" in window.level_result.text()
assert "Start a new capture" in window.level_result.text()
assert "down a little" not in window.level_result.text()
assert "After recording starts, keep these levels fixed" in window.connect_help.text()
assert window.level_new_capture.isVisible() and window.level_new_capture.isEnabled()

# Both appearances and supported sizes keep the recovery action visible without horizontal overflow.
for appearance in ("dark", "light"):
    window.appearance.set_choice(appearance)
    for size in ((1140, 900), (800, 680)):
        window.resize(*size); app.processEvents()
        page = window.pages.currentWidget()
        assert page.horizontalScrollBar().maximum() == 0
        assert window.level_new_capture.isVisible()
        assert window.level_new_capture.width() >= window.level_new_capture.fontMetrics().horizontalAdvance(window.level_new_capture.text())

saved = (folder / "capture_project.json").read_bytes(), target.read_bytes()
window.level_new_capture.click(); app.processEvents()
assert window.project_dir != folder and window.current_step() == "connect"
assert not window._plan_locked() and not window.project.captured_entries()
assert not window.level_new_capture.isVisible() and window.level_result.text() == ""
assert saved == ((folder / "capture_project.json").read_bytes(), target.read_bytes())
print("OK")
''')
