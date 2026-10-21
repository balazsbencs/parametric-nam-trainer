"""Pair the input and output devices of one sound card. No Qt or audio I/O."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from nam.capture.audio import DeviceInfo


@dataclass(frozen=True)
class CaptureCard:
    name: str
    host_api: str
    input_index: int
    output_index: int
    max_input_channels: int
    max_output_channels: int
    input_default_rate: float
    output_default_rate: float
    split: bool

    @property
    def default_samplerate(self) -> float:
        return self.input_default_rate


@dataclass(frozen=True)
class CardList:
    cards: tuple[CaptureCard, ...]
    ambiguous: tuple[str, ...]


def capture_cards(devices: Sequence[DeviceInfo],
                  transports: Mapping[tuple[str, str], str] | None = None) -> CardList:
    groups: dict[tuple[str, str], list[DeviceInfo]] = {}
    for device in devices:
        groups.setdefault((device.name, device.host_api), []).append(device)
    cards, ambiguous = [], set()
    for (name, host_api), group in groups.items():
        inputs = [d for d in group if d.max_input_channels > 0]
        outputs = [d for d in group if d.max_output_channels > 0]
        if len(inputs) > 1 or len(outputs) > 1:
            ambiguous.add(name)
            continue
        if len(inputs) != 1 or len(outputs) != 1:
            continue
        source, sink = inputs[0], outputs[0]
        split = source.index != sink.index
        if split and any((transports or {}).get((name, direction)) in {"blue", "blea"}
                         for direction in ("input", "output")):
            continue
        cards.append(CaptureCard(name, host_api, source.index, sink.index, source.max_input_channels,
                                 sink.max_output_channels, source.default_samplerate,
                                 sink.default_samplerate, split))
    cards.sort(key=lambda card: min(card.input_index, card.output_index))
    return CardList(tuple(cards), tuple(sorted(ambiguous)))


def card_label(card: CaptureCard) -> str:
    return f"{card.name} ({card.host_api}) · {card.max_input_channels} in · {card.max_output_channels} out"
