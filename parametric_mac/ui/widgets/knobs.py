"""Physical knob target drawing."""
import math
import re
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QSizePolicy,
)
from ...controls import SwitchSpec
from .common import Themed


class KnobTargets(Themed, QWidget):
    """Read-only physical dial positions, never software controls."""
    def __init__(self):
        super().__init__()
        self.targets = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setAccessibleName("Physical knob positions")

    def set_targets(self, entry, knobs):
        self.targets = [(k, entry.params[k.name]) for k in knobs if not isinstance(k, SwitchSpec)] if entry else []
        self.setAccessibleDescription(", ".join(f"{k.name} {v:g}, range {k.min:g} to {k.max:g}" for k, v in self.targets))
        self._size_targets()
        self.update()

    def _size_targets(self):
        columns = max(1, min(3, self.width() // 170))
        self.setMinimumHeight(math.ceil(len(self.targets) / columns) * 190)
        self.setVisible(bool(self.targets))
        self.updateGeometry()

    def resizeEvent(self, event):
        self._size_targets()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        p = self._palette
        columns = max(1, min(3, self.width() // 170))
        width = self.width() / columns
        for index, (knob, value) in enumerate(self.targets):
            row, col = divmod(index, columns)
            top = row * 190
            center = QPointF(width * (col + .5), top + 72)
            font = painter.font()
            font.setPixelSize(12)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(p.text))
            painter.drawText(QRectF(col*width, top, width, 20), Qt.AlignCenter, knob.name)
            painter.setPen(QPen(QColor(p.line_strong), 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(QRectF(center.x()-48, center.y()-48, 96, 96), 225*16, -270*16)
            painter.setBrush(QColor(p.raised))
            painter.setPen(QPen(QColor(p.line_strong), 1.2))
            painter.drawEllipse(center, 37, 37)
            angle = math.radians(225 - 270 * (value - knob.min) / (knob.max - knob.min))
            direction = QPointF(math.cos(angle), -math.sin(angle))
            painter.setPen(QPen(QColor(p.accent_text), 2.5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(center + direction*20, center + direction*37)
            font.setPixelSize(11)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(center.x()-54, top+112, 45, 18), Qt.AlignLeft, f'{knob.min:g}')
            painter.drawText(QRectF(center.x()+9, top+112, 45, 18), Qt.AlignRight, f'{knob.max:g}')
            font.setPixelSize(30)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(p.text))
            painter.drawText(QRectF(col*width, top+132, width, 35), Qt.AlignCenter, f'{value:g}')
            font.setPixelSize(11)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(col*width, top+170, width, 18), Qt.AlignCenter, 'Physical knob position')


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
