"""Connect's sound-card list, missing selections and per-direction rate state."""
from PySide6.QtWidgets import QComboBox

from ... import device_rates
from ...capture_cards import CaptureCard, CardList, capture_cards, card_label

NO_DEVICE_TEXT = "No sound card found. Plug it in, then press refresh."


class ConnectCardsMixin:
    _missing_card: str | None = None
    _card_list = CardList((), ())

    def _populate_device_combo(self, combo: QComboBox, devices) -> None:
        if combo is not self.device_combo:
            return super()._populate_device_combo(combo, devices)
        self._card_list = capture_cards(self._devices, device_rates.live_half_transports())
        combo.blockSignals(True)
        combo.clear()
        combo.setPlaceholderText("Choose a sound card")
        for card in self._card_list.cards:
            combo.addItem(card_label(card), card)
        combo.setCurrentIndex(-1)
        combo.blockSignals(False)

    def _select_combo_by_name(self, combo: QComboBox, name: str | None) -> None:
        if combo is not self.device_combo:
            return super()._select_combo_by_name(combo, name)
        index = next((i for i in range(combo.count()) if combo.itemData(i).name == name), -1)
        self._missing_card = name if index == -1 else None
        # Loading a project must not save the old channel widgets over its settings.
        blocked = combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(blocked)
        self._sync_card_notice()

    def _load_audio_settings_into_ui(self) -> None:
        self._loading_card_settings = True
        try:
            super()._load_audio_settings_into_ui()
        finally:
            self._loading_card_settings = False

    def _save_audio_settings(self) -> None:
        if getattr(self, "_loading_card_settings", False) or self.device_combo.currentData() is None:
            return
        self._missing_card = None
        super()._save_audio_settings()
        self._sync_card_notice()

    def _refresh_devices(self) -> None:
        super()._refresh_devices()
        has_cards = bool(self._card_list.cards)
        self.no_devices_label.setText("" if has_cards else NO_DEVICE_TEXT)
        self.no_devices_label.setVisible(not has_cards)
        self._sync_card_notice()
        if hasattr(self, "wire_stage"):
            self._sync_states()

    def _sync_card_notice(self) -> None:
        if not hasattr(self, "card_notice"):
            return
        messages = [f"Two sound cards are called “{name}”, so the app cannot tell them apart. "
                    "Unplug one, then press refresh." for name in self._card_list.ambiguous]
        if self._missing_card:
            messages.append(f"This project used “{self._missing_card}”, which is not connected. "
                            "Plug it in, then press refresh, or choose another sound card.")
        self.card_notice.setText("\n".join(messages))
        self.card_notice.setVisible(bool(messages))

    def _device_rate(self, device, live: dict[str, float]) -> int | None:
        if not isinstance(device, CaptureCard):
            return super()._device_rate(device, live)
        rates = device_rates.card_rates(device, getattr(self, "_live_half_rates", {}))
        file_rate = self._file_sample_rate()
        return next((rate for rate in rates if rate is not None and file_rate is not None and rate != file_rate), rates[0])

    def _update_live_device_rates(self) -> None:
        super()._update_live_device_rates()
        self._live_half_rates = device_rates.live_half_rates()
