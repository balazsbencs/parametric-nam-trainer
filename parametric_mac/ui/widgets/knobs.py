"""Physical knob target drawing."""
import math
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
