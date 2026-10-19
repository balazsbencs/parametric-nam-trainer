"""Top bar with the step bar, and the footer with one action slot per step."""
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStackedWidget, QToolButton, QWidget

from .common import Themed, label

StepState = Literal["todo", "current", "done"]
MESSAGE_SECONDS = 12.0


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    numbered: bool


class StepButton(Themed, QPushButton):
    """One step: a small circle with the number (or a check when done) and the title."""

    def __init__(self, number: int, title: str):
        super().__init__()
        self.number, self.title, self.state = number, title, "todo"
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setFixedHeight(32)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(title) + 36)
        self.setAccessibleName(f"Step {number}: {title}")
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def set_state(self, state: StepState) -> None:
        self.state = state
        self.setAccessibleDescription(state)
        self.update()

    def paintEvent(self, event):
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        current, done = self.state == "current", self.state == "done"
        enabled = self.isEnabled()
        circle = QRectF(6, 7, 18, 18)
        painter.setPen(QPen(QColor(p.accent_fill if current else p.muted if done else p.line_strong), 1))
        painter.setBrush(QColor(p.accent_fill) if current else Qt.NoBrush)
        painter.drawEllipse(circle)
        font = painter.font()
        font.setPixelSize(10)
        font.setWeight(QFont.DemiBold if current else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor(p.on_accent if current else p.text if done else p.muted))
        painter.drawText(circle, Qt.AlignCenter, "✓" if done else str(self.number))
        font.setPixelSize(13)
        painter.setFont(font)
        color = p.accent_text if current else p.text if (done and enabled) else p.muted
        painter.setPen(QColor(color))
        painter.drawText(QRectF(32, 0, self.width() - 32, self.height()), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        if self.hasFocus():
            painter.setPen(QPen(QColor(p.accent_text), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 6, 6)


class StepBar(QWidget):
    """The numbered steps in the top bar. Emits the step key when one is clicked."""

    selected = Signal(str)

    def __init__(self, steps: tuple[Step, ...]):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._buttons: dict[str, StepButton] = {}
        numbered = [s for s in steps if s.numbered]
        for i, step in enumerate(numbered, start=1):
            if i > 1:
                line = QLabel()
                line.setFixedSize(10, 1)
                line.setProperty("stepLine", True)
                row.addWidget(line, 0, Qt.AlignVCenter)
            button = StepButton(i, step.title)
            button.clicked.connect(lambda checked=False, key=step.key: self.selected.emit(key))
            self._buttons[step.key] = button
            row.addWidget(button)

    def button(self, key: str) -> StepButton:
        return self._buttons[key]

    def buttons(self) -> tuple[StepButton, ...]:
        return tuple(self._buttons.values())

    def set_states(self, states: Mapping[str, StepState]) -> None:
        for key, button in self._buttons.items():
            button.set_state(states.get(key, "todo"))

    def set_enabled_steps(self, keys: set[str]) -> None:
        for key, button in self._buttons.items():
            button.setEnabled(key in keys)


class ElidedLabel(QLabel):
    """One line of text that shortens with "…" to fit, with the full text in the tooltip."""

    def __init__(self, text: str = ""):
        super().__init__()
        self._full = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(self.fontMetrics().horizontalAdvance(self._full) + 4)
        return hint

    def _elide(self) -> None:
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(0, self.width())))


class TopBar(QWidget):
    """Brand, step bar, project name and the appearance menu button."""

    def __init__(self, steps: tuple[Step, ...]):
        super().__init__()
        self.setObjectName("topBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 12, 10)
        row.setSpacing(10)
        dot = label("●", "accent")
        dot.setAccessibleName("")
        dot.setWordWrap(False)
        dot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.brand_button = QPushButton("Parametric")
        self.brand_button.setObjectName("brand")
        self.brand_button.setToolTip("Start: create or open a project")
        self.brand_button.setCursor(Qt.PointingHandCursor)
        self.project_title = ElidedLabel("No project open")
        self.project_title.setProperty("role", "muted")
        row.addWidget(dot)
        row.addWidget(self.brand_button)
        row.addStretch(1)
        self.step_bar = StepBar(steps)
        row.addWidget(self.step_bar)
        row.addStretch(1)
        row.addWidget(self.project_title, 1)
        self.appearance_button = QToolButton()
        self.appearance_button.setText("◐")
        self.appearance_button.setToolTip("Appearance")
        self.appearance_button.setAccessibleName("Appearance")
        self.appearance_button.setPopupMode(QToolButton.InstantPopup)
        row.addWidget(self.appearance_button)

    def set_project_title(self, text: str) -> None:
        self.project_title.setText(text)


class Footer(QWidget):
    """Status text on the left and the current step's main action on the right."""

    def __init__(self):
        super().__init__()
        self.setObjectName("footer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 10, 24, 10)
        self.status = label("", "muted")
        self._message_until = 0.0
        row.addWidget(self.status, 1)
        self._actions = QStackedWidget()
        self._actions.setObjectName("footerActions")
        self._slots: dict[str, int] = {}
        row.addWidget(self._actions, 0, Qt.AlignRight)

    def add_action(self, key: str, widget: QWidget | None) -> None:
        holder = QWidget()
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        if widget is not None:
            layout.addWidget(widget)
        self._slots[key] = self._actions.addWidget(holder)

    def show_step(self, key: str) -> None:
        self._actions.setCurrentIndex(self._slots.get(key, 0))

    def set_status(self, text: str) -> None:
        """The current state. A recent message (show_message) wins until it expires."""
        if time.monotonic() < self._message_until:
            return
        self.status.setText(text)

    def clear_message(self) -> None:
        self._message_until = 0.0

    def show_message(self, text: str, seconds: float = MESSAGE_SECONDS) -> None:
        """A message the periodic state refresh does not overwrite, for example an error."""
        self._message_until = time.monotonic() + seconds
        self.status.setText(text)
