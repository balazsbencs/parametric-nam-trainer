"""Level meter and the cable chain drawing."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .common import Themed

METER_FLOOR_DB = -60.0
METER_ZONES = (-18.0, -6.0)


class LevelMeter(Themed, QWidget):
    """A horizontal peak meter from −60 to 0 dB with ok, careful and too-loud zones."""

    def __init__(self):
        super().__init__()
        self.peak: float | None = None
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName("Level meter")

    def set_peak(self, dbfs: float | None) -> None:
        self.peak = dbfs
        self.setAccessibleDescription("No level checked yet" if dbfs is None else f"Peak {dbfs:.1f} dB")
        self.update()

    def _x(self, db: float) -> float:
        span = self.width() - 2
        return 1 + span * (max(METER_FLOOR_DB, min(0.0, db)) - METER_FLOOR_DB) / -METER_FLOOR_DB

    def paintEvent(self, event):
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bar = QRectF(1, 2, self.width() - 2, 10)
        zones = ((METER_FLOOR_DB, METER_ZONES[0], p.ok_surface), (METER_ZONES[0], METER_ZONES[1], p.warn_surface),
                 (METER_ZONES[1], 0.0, p.danger_surface))
        painter.setPen(Qt.NoPen)
        for low, high, color in zones:
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(self._x(low), bar.top(), self._x(high) - self._x(low), bar.height()))
        if self.peak is not None:
            color = p.ok if self.peak < METER_ZONES[0] else p.warn if self.peak < METER_ZONES[1] else p.danger
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(bar.left(), bar.top(), self._x(self.peak) - bar.left(), bar.height()))
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QColor(p.muted))
        for db in (METER_FLOOR_DB, *METER_ZONES, 0.0):
            text = f"{db:g}" if db else "0 dB"
            x = self._x(db)
            align = Qt.AlignLeft if db == METER_FLOOR_DB else Qt.AlignRight if db == 0 else Qt.AlignHCenter
            rect = QRectF(x - (0 if align == Qt.AlignLeft else 60 if align == Qt.AlignRight else 30), 14, 60, 14)
            painter.drawText(rect, align | Qt.AlignVCenter, text.replace("-", "−"))


PEDAL_CHAIN = (("Sound card", "Output"), ("Reamp box", "Instrument level"), ("Pedal", "In → Out"), ("Sound card", "Input"))
AMP_CHAIN = (("Sound card", "Output"), ("Reamp box", "Instrument level"), ("Amp", "Input → speaker out"),
             ("Load box", "Line out"), ("Sound card", "Input"))


class CableChain(Themed, QWidget):
    """Boxes joined by dashed cables: how the signal travels from the sound card and back."""

    def __init__(self):
        super().__init__()
        self.nodes = PEDAL_CHAIN
        self.setFixedHeight(56)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_amp(self, amp: bool) -> None:
        self.nodes = AMP_CHAIN if amp else PEDAL_CHAIN
        self.setAccessibleDescription(" → ".join(title for title, _ in self.nodes))
        self.update()

    def node_titles(self) -> tuple[str, ...]:
        return tuple(title for title, _ in self.nodes)

    def paintEvent(self, event):
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        count, gap = len(self.nodes), 14
        width = (self.width() - gap * (count - 1)) / count
        font = painter.font()
        for i, (title, detail) in enumerate(self.nodes):
            box = QRectF(i * (width + gap), 1, width, self.height() - 2)
            painter.setPen(QPen(QColor(p.line_strong), 1))
            painter.setBrush(QColor(p.panel))
            painter.drawRoundedRect(box, 8, 8)
            if i:
                painter.setPen(QPen(QColor(p.accent_text), 2, Qt.DashLine))
                painter.drawLine(QPointF(box.left() - gap, box.center().y()), QPointF(box.left(), box.center().y()))
            font.setPixelSize(12)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(p.text))
            inner = box.adjusted(8, 6, -6, -6)
            painter.drawText(inner, Qt.AlignLeft | Qt.AlignTop, painter.fontMetrics().elidedText(title, Qt.ElideRight, int(inner.width())))
            font.setPixelSize(11)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor(p.muted))
            painter.drawText(inner, Qt.AlignLeft | Qt.AlignBottom, painter.fontMetrics().elidedText(detail, Qt.ElideRight, int(inner.width())))
