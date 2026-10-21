"""Connect's sound-card list, missing selections and per-direction rate state."""
from PySide6.QtWidgets import QComboBox
from nam.capture.project import save_project

from ... import device_rates
from ...capture_cards import CaptureCard, CardList, capture_cards, card_label

NO_DEVICE_TEXT = "No sound card found. Plug it in, then press refresh."


class ConnectCardsMixin:
    _missing_card: str | None = None
    _card_list = CardList((), ())

    def _populate_device_combo(self, combo: QComboBox, devices) -> None:
        self._update_live_device_rates()
        self._card_list = capture_cards(self._devices, self._live_half_transports)
        blocked = combo.blockSignals(True)
        combo.clear()
        combo.setPlaceholderText("Choose a sound card")
        for card in self._card_list.cards:
            combo.addItem(card_label(card), card)
        combo.setCurrentIndex(-1)
        combo.blockSignals(blocked)

    def _select_combo_by_name(self, combo: QComboBox, name: str | None) -> None:
        index = next((i for i in range(combo.count()) if combo.itemData(i).name == name), -1)
        self._missing_card = name if index == -1 else None
        old_card = combo.currentData()
        blocked = combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(blocked)
        if old_card != combo.currentData():
            self._invalidate_card_route()
        self._sync_card_notice()

    def _invalidate_card_route(self) -> None:
        self._route_fingerprint = None
        if hasattr(self, "find_result"):
            self._reset_find()
        if hasattr(self, "level_meter"):
            self._show_level(None)

    def _load_audio_settings_into_ui(self) -> None:
        self._loading_card_settings = True
        try:
            super()._load_audio_settings_into_ui()
        finally:
            self._loading_card_settings = False

    def _update_channel_ranges(self) -> None:
        if self.device_combo.currentData() is not None:
            return super()._update_channel_ranges()
        # Without a card there is no channel limit to apply. Preserve saved values.
        audio = self._current_audio_settings()
        for field in ("output_channel", "input_channel", "loopback_output_channel", "loopback_input_channel"):
            spin = getattr(self, f"{field}_spin")
            spin.setMaximum(max(spin.maximum(), getattr(audio, field) or 2))

    def _save_audio_settings(self) -> None:
        if getattr(self, "_loading_card_settings", False):
            return
        if self.device_combo.currentData() is not None:
            self._missing_card = None
            super()._save_audio_settings()
        else:
            self._save_unselected_settings()
        self._sync_card_notice()

    def _save_unselected_settings(self) -> None:
        """Keep device identity while persisting explicit Expert edits."""
        audio = self._current_audio_settings()
        for field in ("output_channel", "input_channel"):
            setattr(audio, field, getattr(self, f"{field}_spin").value())
        for field in ("loopback_output_channel", "loopback_input_channel"):
            setattr(audio, field, getattr(self, f"{field}_spin").value() if self.loopback_check.isChecked() else None)
        audio.blocksize = int(self.buffer_size_combo.currentData())
        audio.latency = self.latency_combo.currentData()
        if self.project is not None and self.project_dir is not None:
            save_project(self.project, self.project_dir)

    def _refresh_devices(self) -> None:
        super()._refresh_devices()
        self._invalidate_card_route()
        missing = not self._card_list.cards and not self._card_list.ambiguous
        self.no_devices_label.setText(NO_DEVICE_TEXT if missing else "")
        self.no_devices_label.setVisible(missing)
        self._sync_card_notice()
        if self._ready:
            self._sync_states()

    def _sync_card_notice(self) -> None:
        if not hasattr(self, "card_notice"):
            return
        messages = [f"Two sound cards are called “{name}”, so the app cannot tell them apart. "
                    "Unplug one, then press refresh." for name in self._card_list.ambiguous]
        if self._missing_card and self._missing_card not in self._card_list.ambiguous:
            messages.append(f"This project used “{self._missing_card}”, which is not connected. "
                            "Plug it in, then press refresh, or choose another sound card.")
        self.card_notice.setText("\n".join(messages))
        self.card_notice.setVisible(bool(messages))

    def _device_rate(self, device: CaptureCard | None, live: dict[str, float]) -> int | None:
        if device is None:
            return None
        rates = device_rates.card_rates(device, getattr(self, "_live_half_rates", {}))
        file_rate = self._file_sample_rate()
        return next((rate for rate in rates if rate is not None and file_rate is not None and rate != file_rate), rates[0])

    def _update_live_device_rates(self) -> None:
        rates, transports = device_rates.live_device_state()
        self._live_half_rates = {**getattr(self, "_live_half_rates", {}), **rates}
        self._live_half_transports = {**getattr(self, "_live_half_transports", {}), **transports}
