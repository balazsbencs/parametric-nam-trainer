"""Physical knob target drawing."""
import math
import re
from collections.abc import Mapping
from typing import Literal
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QSizePolicy,
)
from ...controls import SwitchSpec
from .common import Themed


Tier = Literal["large", "medium", "compact"]
# (cell width, cell height, dial size, value font px) per tier
TIER_SIZES = {"large": (210, 214, 104, 32), "medium": (160, 168, 72, 24), "compact": (118, 116, 40, 16)}
MAX_PER_ROW = 4


def changed_controls(previous: Mapping[str, float] | None, current: Mapping[str, float]) -> frozenset[str]:
    """Names whose target moved since the last take. Everything is "changed" for the first take."""
    if previous is None:
        return frozenset(current)
    return frozenset(name for name, value in current.items() if previous.get(name) != value)


def control_value_text(control, value) -> str:
    """A target as the user reads it: the number for a knob, the position name for a switch."""
    if isinstance(control, SwitchSpec):
        names = control.enum_names
        return names[int(value)] if 0 <= int(value) < len(names) else f"{value:g}"
    return f"{value:g}"


def size_tier(count: int) -> Tier:
    return "large" if count <= 2 else "medium" if count <= 6 else "compact"


class TargetControls(Themed, QWidget):
    """The positions to set for the next take: dials for knobs, position names for switches."""

    def __init__(self):
        super().__init__()
        self.targets: list = []
        self.changed: frozenset[str] = frozenset()
        self.tier: Tier = "large"
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_targets(self, entry, controls, changed: frozenset[str] = frozenset()) -> None:
        params = entry.params if entry is not None else {}
        self.targets = [(c, params[c.name]) for c in controls if c.name in params]
        self.changed = frozenset(changed)
        self.tier = size_tier(len(self.targets))
        self.setAccessibleDescription(", ".join(
            f"{c.name} {self._value_text(c, v)}" + (" (changed)" if c.name in self.changed else "") for c, v in self.targets))
        self._size()
        self.update()

    def _columns(self) -> int:
        cell = TIER_SIZES[self.tier][0]
        return max(1, min(MAX_PER_ROW, len(self.targets) or 1, self.width() // cell or 1))

    def required_height(self) -> int:
        return math.ceil(len(self.targets) / self._columns()) * TIER_SIZES[self.tier][1] if self.targets else 0

    def _size(self) -> None:
        self.setFixedHeight(self.required_height())
        self.setVisible(bool(self.targets))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.height() != self.required_height():
            self._size()

    _value_text = staticmethod(control_value_text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        columns = self._columns()
        cell_w, cell_h, _, _ = TIER_SIZES[self.tier]
        width = self.width() / columns
        for index, (control, value) in enumerate(self.targets):
            row, col = divmod(index, columns)
            self._paint_cell(painter, QRectF(col * width, row * cell_h, width, cell_h), control, value)

    def _paint_cell(self, painter, cell: QRectF, control, value) -> None:
        p = self._palette
        _, _, dial, value_px = TIER_SIZES[self.tier]
        changed = control.name in self.changed
        font = painter.font()
        font.setPixelSize(12 if self.tier != "compact" else 11)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(p.accent_text if changed else p.muted))
        name = control.name + ("  · changed" if changed else "")
        painter.drawText(QRectF(cell.left() + 4, cell.top(), cell.width() - 8, 18), Qt.AlignCenter,
                         painter.fontMetrics().elidedText(name, Qt.ElideRight, int(cell.width() - 8)))
        center = QPointF(cell.center().x(), cell.top() + 22 + dial / 2)
        if isinstance(control, SwitchSpec):
            self._paint_switch(painter, center, dial, control, value)
        else:
            self._paint_dial(painter, center, dial, control, value)
        font.setPixelSize(value_px)
        font.setFamily("Geist Mono")
        painter.setFont(font)
        painter.setPen(QColor(p.text))
        top = center.y() + dial / 2 + 4
        painter.drawText(QRectF(cell.left(), top, cell.width(), value_px + 8), Qt.AlignCenter,
                         painter.fontMetrics().elidedText(self._value_text(control, value), Qt.ElideRight, int(cell.width() - 4)))

    def _paint_dial(self, painter, center: QPointF, size: int, control, value) -> None:
        p = self._palette
        radius = size / 2
        span = (control.max - control.min) or 1
        fraction = max(0.0, min(1.0, (value - control.min) / span))
        ring = QRectF(center.x() - radius, center.y() - radius, size, size)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(p.line_strong), 2))
        painter.drawArc(ring, 225 * 16, -270 * 16)
        painter.setPen(QPen(QColor(p.accent_text), 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(ring, 225 * 16, int(-270 * 16 * fraction))
        painter.setPen(QPen(QColor(p.line_strong), 1))
        painter.setBrush(QColor(p.raised))
        painter.drawEllipse(center, radius * 0.72, radius * 0.72)
        angle = math.radians(225 - 270 * fraction)
        direction = QPointF(math.cos(angle), -math.sin(angle))
        painter.setPen(QPen(QColor(p.text), max(2.0, size / 40), Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(center + direction * radius * 0.25, center + direction * radius * 0.65)

    def _paint_switch(self, painter, center: QPointF, size: int, control, value) -> None:
        p = self._palette
        positions = max(2, len(control.enum_names))
        height, width = size * 0.9, size * 0.32
        body = QRectF(center.x() - width / 2, center.y() - height / 2, width, height)
        painter.setPen(QPen(QColor(p.line_strong), 1))
        painter.setBrush(QColor(p.panel))
        painter.drawRoundedRect(body, width / 2, width / 2)
        step = (height - width) / (positions - 1)
        knob_y = body.top() + width / 2 + step * max(0, min(positions - 1, int(value)))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(p.accent_text))
        painter.drawEllipse(QPointF(center.x(), knob_y), width * 0.36, width * 0.36)


class ControlGlyph(Themed, QWidget):
    """A small knob or switch icon for a control tile."""

    def __init__(self, switch: bool):
        super().__init__()
        self.switch = switch
        self.setFixedSize(36, 36)

    def paintEvent(self, event):
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.switch:
            painter.setPen(QPen(QColor(p.line_strong), 1.2))
            painter.setBrush(QColor(p.panel))
            painter.drawRoundedRect(QRectF(12, 4, 12, 28), 6, 6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(p.text))
            painter.drawEllipse(QPointF(18, 11), 4.5, 4.5)
            return
        painter.setPen(QPen(QColor(p.line_strong), 1.2))
        painter.setBrush(QColor(p.panel))
        painter.drawEllipse(QPointF(18, 18), 13, 13)
        painter.setPen(QPen(QColor(p.text), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(18, 18), QPointF(18, 8))


# A short control name and a short value: "Level at 5", "Tone at 2 o'clock". Sentences do not match.
_FIXED_NOTE = re.compile(r"\s*(.{1,20}?)\s+at\s+(.{1,12}?)\s*")


def fixed_controls(fixed_notes: str) -> tuple[tuple[str, str], ...]:
    """("Level", "5") pairs from free text like "Level at 5, Volume at noon"."""
    matches = (_FIXED_NOTE.fullmatch(part) for part in re.split(r"[,;]", fixed_notes))
    return tuple((m.group(1).strip(), m.group(2).strip()) for m in matches if m)


class GearDrawing(Themed, QWidget):
    """A pedal enclosure with an LED, the modeled knobs and switches, dimmed fixed knobs, and the name."""

    PER_ROW, CELL, ROW_HEIGHT, WIDTH = 3, 64, 76, 240

    def __init__(self):
        super().__init__()
        self.name, self.controls, self.fixed = "", (), ()
        self.setMinimumWidth(self.WIDTH + 20)
        self.setAccessibleName("Drawing of your gear")

    def set_gear(self, name: str, controls: tuple, fixed_notes: str) -> None:
        self.name, self.controls, self.fixed = name, tuple(controls), fixed_controls(fixed_notes)
        rows = max(1, math.ceil((len(self.controls) + len(self.fixed)) / self.PER_ROW))
        self.setFixedHeight(min(rows, 6) * self.ROW_HEIGHT + 150)
        self.setAccessibleDescription(", ".join(c.name for c in self.controls))
        self.update()

    def paintEvent(self, event):
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF((self.width() - self.WIDTH) / 2, 4, self.WIDTH, self.height() - 8)
        painter.setPen(QPen(QColor(p.line_strong), 1))
        painter.setBrush(QColor(p.raised))
        painter.drawRoundedRect(box, 18, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(p.danger))
        painter.drawEllipse(QPointF(box.center().x(), box.top() + 20), 4.5, 4.5)
        items = [(c.name, isinstance(c, SwitchSpec), False) for c in self.controls]
        items += [(f"{n} · {v}", False, True) for n, v in self.fixed]
        visible = items[: 6 * self.PER_ROW]
        for i, (text, switch, fixed) in enumerate(visible):
            row, col = divmod(i, self.PER_ROW)
            in_row = min(self.PER_ROW, len(visible) - row * self.PER_ROW)
            x = box.center().x() + (col - (in_row - 1) / 2) * self.CELL
            y = box.top() + 40 + row * self.ROW_HEIGHT
            self._draw_control(painter, QPointF(x, y + 20), text, switch, fixed)
        stomp_y = box.bottom() - 62
        painter.setPen(QPen(QColor(p.line_strong), 1))
        painter.setBrush(QColor(p.panel))
        painter.drawEllipse(QPointF(box.center().x(), stomp_y), 22, 22)
        font = painter.font()
        font.setPixelSize(12)
        font.setWeight(QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 1)
        painter.setFont(font)
        painter.setPen(QColor(p.text))
        painter.drawText(QRectF(box.left() + 8, box.bottom() - 32, box.width() - 16, 20), Qt.AlignCenter,
                         painter.fontMetrics().elidedText(self.name.upper(), Qt.ElideRight, int(box.width() - 16)))

    def _draw_control(self, painter, center, text, switch, fixed):
        p = self._palette
        color = QColor(p.muted if fixed else p.text)
        painter.setPen(QPen(QColor(p.line_strong), 1.2))
        painter.setBrush(QColor(p.panel))
        if switch:
            painter.drawRoundedRect(QRectF(center.x() - 6, center.y() - 14, 12, 28), 6, 6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(center.x(), center.y() - 7), 4, 4)
        else:
            painter.drawEllipse(center, 17, 17)
            painter.setPen(QPen(color, 2.4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(center, QPointF(center.x(), center.y() - 12))
        font = painter.font()
        font.setPixelSize(11)
        font.setWeight(QFont.Normal)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
        painter.setFont(font)
        painter.setPen(QColor(p.muted))
        label_rect = QRectF(center.x() - self.CELL / 2, center.y() + 20, self.CELL, 16)
        painter.drawText(label_rect, Qt.AlignCenter, painter.fontMetrics().elidedText(text, Qt.ElideRight, self.CELL))
