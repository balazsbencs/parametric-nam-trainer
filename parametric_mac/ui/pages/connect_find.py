"""Connect, stage 2: Find my connection. Plays quiet clicks on one output at a time (spec §4.2, §6.1)."""
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from nam.capture import audio

from ...capture_cards import capture_cards
from ...device_rates import live_half_transports
from ...find_route import FindResult, Route
from ...find_scan import ScanTarget, scan_target
from ..copy import (
    FIND_CANCELLED_TEXT, FIND_FAILED_TEXT, find_message, loopback_note, route_choice_text,
    several_routes_text, stopped_early_note,
)
from ..widgets.common import button, label, set_style_property

FIND_TEXT = "Find my connection"
CANCEL_TEXT = "Cancel search"
SEARCHING_TEXT = "Playing quiet clicks on each output, one at a time…"

log = logging.getLogger(__name__)


def link(text: str, callback) -> QPushButton:
    widget = QPushButton(text)
    widget.setProperty("link", True)
    widget.setCursor(Qt.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


class ConnectFindMixin:
    _finding = False
    _find_outputs = 0

    # ---- widgets ----------------------------------------------------------------------

    def _find_rows(self, body: QVBoxLayout) -> None:
        row = QHBoxLayout()
        self.find_button = button(FIND_TEXT, self._on_find_clicked)
        set_style_property(self.find_button, "outline", True)
        row.addWidget(self.find_button)
        self.find_result = label("", "muted")
        row.addWidget(self.find_result, 1)
        body.addLayout(row)
        self.find_route_links = QWidget()
        QHBoxLayout(self.find_route_links).setContentsMargins(0, 0, 0, 0)
        self.find_route_links.hide()
        body.addWidget(self.find_route_links)
        actions = QHBoxLayout()
        self.find_try_again = link("Try again", self._start_find)
        self.find_manual = link("Choose channels myself", self._open_manual_channels)
        for action in (self.find_try_again, self.find_manual):
            action.hide()
            actions.addWidget(action)
        actions.addStretch()
        body.addLayout(actions)

    def _find_expert_notes(self, form: QFormLayout) -> None:
        self.find_loopback_note = label("", "muted")
        self.find_stop_note = label("", "muted")
        for note in (self.find_loopback_note, self.find_stop_note):
            note.hide()
            form.addRow(note)

    # ---- state ------------------------------------------------------------------------

    def _find_allowed(self) -> bool:
        return (not self._busy() and self.wire_check.isChecked() and self._has_device()
                and self._rate_problem() is None)

    def _sync_find(self) -> None:
        if self._finding:
            self.find_button.setText(CANCEL_TEXT)
            self.find_button.setEnabled(self._cancel_token is not None)
        else:
            self.find_button.setText(FIND_TEXT)
            self.find_button.setEnabled(self._find_allowed())
        self.find_try_again.setEnabled(not self._finding and self._find_allowed())
        for choice in self.find_route_links.findChildren(QPushButton):
            choice.setEnabled(not self._busy())

    def _reset_find(self) -> None:
        """A new or reopened project starts without an old search result."""
        self._show_find("", "muted")
        for note in (self.find_loopback_note, self.find_stop_note):
            note.setText("")
            note.hide()

    def _show_find(self, text: str, role: str, routes: tuple[Route, ...] = (), retry: bool = False) -> None:
        self.find_result.setText(text)
        set_style_property(self.find_result, "role", role)
        layout = self.find_route_links.layout()
        for old in self.find_route_links.findChildren(QPushButton):
            layout.removeWidget(old)
            old.deleteLater()
        for route in routes:
            layout.addWidget(link(route_choice_text(route), lambda *_, chosen=route: self._use_route(chosen)))
        self.find_route_links.setVisible(bool(routes))
        self.find_try_again.setVisible(retry)
        self.find_manual.setVisible(retry)

    # ---- the search -------------------------------------------------------------------

    def _on_find_clicked(self) -> None:
        if not self._finding:
            self._start_find()
        elif self._cancel_token is not None:
            self._cancel_token.cancel()

    def _find_target(self) -> ScanTarget | None:
        """Everything the scan needs, read here on the GUI thread as plain values."""
        device = self.device_combo.currentData()
        if device is None:
            return None
        try:
            cards = capture_cards(audio.list_devices(), live_half_transports()).cards
            card = next((c for c in cards if (c.name, c.host_api) == (device.name, device.host_api)), None)
            if card is None:
                return None
            source = audio.find_device(card.name, kind="input", host_api=card.host_api)
            sink = audio.find_device(card.name, kind="output", host_api=card.host_api)
            if (source.index, sink.index) != (card.input_index, card.output_index):
                return None
        except Exception:
            log.debug("Could not resolve Find's sound card", exc_info=True)
            return None
        rate = self._device_sample_rate() or int(round(card.default_samplerate))
        excluded = (frozenset({self.loopback_input_channel_spin.value()}) if self.loopback_check.isChecked()
                    else frozenset())
        return ScanTarget(source.index, sink.index, card.max_output_channels, card.max_input_channels, rate,
                          int(self.buffer_size_combo.currentData()), self.latency_combo.currentData(), excluded)

    def _scan_outputs(self, target: ScanTarget, progress, cancel) -> FindResult:
        """The worker-thread call; tests replace it."""
        return scan_target(target, progress, cancel)

    def _start_find(self) -> None:
        if not self._find_allowed():
            return
        target = self._find_target()
        if target is None:
            self._show_find(FIND_FAILED_TEXT, "warn", retry=True)
            return
        self._finding, self._find_outputs = True, target.output_channels
        self._show_find(SEARCHING_TEXT, "muted")
        self.route_test_progress.setValue(0)
        self.route_test_progress.show()
        self._run_worker(
            lambda progress, cancel: self._scan_outputs(target, progress, cancel),
            on_progress=lambda fraction: self.route_test_progress.setValue(int(fraction * 100)),
            on_success=self._on_find_success, on_failure=self._on_find_failure,
            on_cancelled=self._on_find_cancelled, on_finished=self._find_finished,
            disable=[self.check_level_button],
        )
        if self._worker is None:  # the worker did not start
            self._find_finished()
            self._sync_states()

    def _find_finished(self) -> None:
        self._finding = False
        self.route_test_progress.hide()

    def _on_find_success(self, result: FindResult) -> None:
        self.find_loopback_note.setText(loopback_note(result.loopbacks))
        self.find_loopback_note.setVisible(bool(result.loopbacks))
        self.find_stop_note.setText(stopped_early_note(self._find_outputs) if result.stopped_early else "")
        self.find_stop_note.setVisible(result.stopped_early)
        if result.route is not None:
            self._use_route(result.route, result.stopped_early)
        elif result.state == "several":  # Try again and manual channels stay offered in case neither is right
            self._show_find(several_routes_text(), "muted", routes=result.routes, retry=True)
        else:
            # After a passed level check, or once recording has started, the gain must not change.
            locked = self._plan_locked() or self._route_fingerprint is not None
            self._show_find(find_message(result, levels_locked=locked), "warn", retry=True)
        self._sync_states()

    def _on_find_failure(self, message: str) -> None:
        log.warning("Find my connection failed: %s", message)
        self._show_find(FIND_FAILED_TEXT, "warn", retry=True)

    def _on_find_cancelled(self) -> None:
        self._show_find(FIND_CANCELLED_TEXT, "muted")

    def _use_route(self, route: Route, stopped_early: bool = False) -> None:
        """Set and save the channels, then ask for a new level check: the old one was for another route."""
        self.output_channel_spin.setValue(route.output_channel)
        self.input_channel_spin.setValue(route.input_channel)
        self._save_audio_settings()
        self._route_fingerprint = None
        self._show_level(None)
        message = find_message(FindResult("found", (route,), (), stopped_early), self._find_outputs)
        self._show_find(message, "danger" if route.clipping else "warn" if stopped_early else "ok")
        self._sync_states()

    def _open_manual_channels(self) -> None:
        self.audio_advanced_toggle.setChecked(True)
        self.output_channel_spin.setFocus()
