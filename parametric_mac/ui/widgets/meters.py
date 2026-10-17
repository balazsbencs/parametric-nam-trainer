"""Level meter, cable chain and training chart drawings."""
import math
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


class TrainingChart(Themed, QWidget):
    """Validation difference per round, log scale, for the size that is training now."""

    def __init__(self):
        super().__init__()
        self._series: dict[str, list[tuple[int, float]]] = {}
        self.current_tier = ""
        self._total = 0
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName("Difference from the real gear on test settings, lower is better")

    def clear(self) -> None:
        self._series, self.current_tier = {}, ""
        self.update()

    def set_total(self, epochs: int) -> None:
        self._total = epochs
        self.update()

    def add_point(self, point) -> None:
        if point.value <= 0:
            return
        self._series.setdefault(point.tier, []).append((point.epoch, point.value))
        self.current_tier = point.tier
        self.setAccessibleDescription(f"Latest value {point.value:.4g} at round {point.epoch}")
        self.update()

    def points(self, tier: str) -> list[tuple[int, float]]:
        return list(self._series.get(tier, []))

    def paintEvent(self, event):
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor(p.line), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame, 10, 10)
        for i in range(1, 4):
            y = frame.top() + frame.height() * i / 4
            painter.drawLine(QPointF(frame.left() + 8, y), QPointF(frame.right() - 8, y))
        series = self._series.get(self.current_tier, [])
        if len(series) < 1:
            return
        points = self._chart_points(series, frame.adjusted(12, 12, -12, -12))
        painter.setPen(QPen(QColor(p.accent_text), 2))
        for a, b in zip(points, points[1:]):
            painter.drawLine(a, b)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(p.accent_text))
        painter.drawEllipse(points[-1], 4, 4)

    def _chart_points(self, series, area: QRectF) -> list[QPointF]:
        epochs = [e for e, _ in series]
        logs = [math.log10(v) for _, v in series]
        first, last = epochs[0], max(epochs[-1], epochs[0] + 1)
        low, high = min(logs), max(logs)
        span = (high - low) or 1.0
        return [QPointF(area.left() + area.width() * (e - first) / (last - first),
                        area.top() + area.height() * (high - lg) / span) for e, lg in zip(epochs, logs)]
