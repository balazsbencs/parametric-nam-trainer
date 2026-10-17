"""Small shared widgets and layout helpers."""
from PySide6.QtCore import Qt, QRectF, QSize, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QBoxLayout, QLayout, QToolButton, QButtonGroup,
)
from ...theme import icon
from ..tokens import DARK, Palette


PAGE_MARGIN = 38  # left and right padding of every scrolling page


class Themed:
    """Custom-painted widgets take their colors from the current Palette."""
    _palette: Palette = DARK

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()


class Segmented(QWidget):
    """Two or more exclusive choices that look like one control. API like a QComboBox."""

    currentIndexChanged = Signal(int)

    def __init__(self, options: tuple[str, ...]):
        super().__init__()
        self.setObjectName("segmented")
        self.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = []
        for index, text in enumerate(options):
            choice = QPushButton(text)
            choice.setCheckable(True)
            choice.setProperty("segment", True)
            self._group.addButton(choice, index)
            row.addWidget(choice)
            self._buttons.append(choice)
        self._buttons[0].setChecked(True)
        self._group.idToggled.connect(lambda index, checked: checked and self.currentIndexChanged.emit(index))

    def currentIndex(self) -> int:
        return self._group.checkedId()

    def setCurrentIndex(self, index: int) -> None:
        self._buttons[index].setChecked(True)

    def currentText(self) -> str:
        return self._buttons[self.currentIndex()].text()

    def count(self) -> int:
        return len(self._buttons)

    def button(self, index: int) -> QPushButton:
        return self._buttons[index]


class ChoiceCard(QFrame):
    """A large selectable card: title, optional tag, a big number with a unit, and one sentence."""

    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.selected = False
        self.setProperty("card", True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        head_widget = QWidget()
        head_widget.setFixedHeight(26)
        head = QHBoxLayout(head_widget)
        head.setContentsMargins(0, 0, 0, 0)
        self._title = label("", "section")
        self._title.setWordWrap(False)
        self._title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._tag = label("")
        self._tag.setProperty("tag", "accent")
        self._tag.setWordWrap(False)
        self._tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        head.addWidget(self._title)
        head.addWidget(self._tag)
        head.addStretch()
        layout.addWidget(head_widget)
        self._number = label("", "quality")
        self._number.setWordWrap(False)
        layout.addWidget(self._number)
        self._body = label("", "muted")
        layout.addWidget(self._body)

    def set_content(self, title: str, number: str, unit: str, body: str, tag: str | None) -> None:
        self._title.setText(title)
        self._number.setText(number)
        self._unit = unit
        self._number.setToolTip(unit)
        self._body.setText(f"{unit}\n{body}" if unit else body)
        self._tag.setText(tag or "")
        self._tag.setVisible(bool(tag))
        self.setAccessibleName(f"{title}: {number} {unit}. {body}")

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        set_style_property(self, "selected", selected)

    def title_text(self) -> str:
        return self._title.text()

    def number_text(self) -> str:
        return self._number.text()

    def tag_text(self) -> str:
        return self._tag.text() if self._tag.isVisibleTo(self) else ""

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.isEnabled() and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


class AlertBox(QFrame):
    """A tinted box with a title, a plain instruction, and optional actions underneath."""

    def __init__(self):
        super().__init__()
        self.setProperty("alert", "error")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        self._title = label("", "section")
        self._body = label("")
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 6, 0, 0)
        layout.addLayout(self.actions)
        self.hide()

    def show_message(self, title: str, body: str, kind: str = "error") -> None:
        set_style_property(self, "alert", kind)
        self._title.setText(title)
        self._body.setText(body)
        self.show()

    def body_text(self) -> str:
        return self._body.text()


def set_style_property(widget, name: str, value) -> None:
    """Change a property that the style sheet reads, and restyle the widget at once."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def themed(widget, appearance):
    """Give `widget` the current palette and keep it in sync with appearance changes."""
    widget.set_palette(appearance.palette())
    appearance.changed.connect(widget.set_palette)
    return widget


def label(text, role=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    policy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    policy.setHeightForWidth(True)
    widget.setSizePolicy(policy)
    widget.setTextFormat(Qt.PlainText)
    if role:
        widget.setProperty("role", role)
    if role == 'title':
        font = widget.font()
        font.setLetterSpacing(QFont.AbsoluteSpacing, -.6)
        widget.setFont(font)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    widget.clicked.connect(callback)
    return widget


def disclosure(layout, title, widget):
    toggle = QToolButton()
    toggle.setText(title)
    toggle.setProperty('disclosure', True)
    toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    toggle.setIcon(icon('chevron-right'))
    toggle.setIconSize(QSize(12, 12))
    toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    toggle.setCheckable(True)
    toggle.setAccessibleName(title)
    widget.setVisible(False)
    def reveal(opened):
        toggle.setIcon(icon('chevron-down' if opened else 'chevron-right'))
        widget.setVisible(opened)
    toggle.toggled.connect(reveal)
    layout.addWidget(toggle)
    layout.addWidget(widget)
    return toggle


def field(caption, widget):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    title = label(caption)
    title.setStyleSheet('font-size: 12px;')
    title.setBuddy(widget)
    widget.setAccessibleName(caption)
    layout.addWidget(title)
    layout.addWidget(widget)
    return container


class StageButton(Themed, QPushButton):
    def __init__(self, index, stage, detail, callback):
        super().__init__()
        self.index, self.stage, self.detail = index, stage, detail
        self.setProperty('nav', True)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.TabFocus)
        self.setMinimumHeight(62)
        self.clicked.connect(callback)
        self.setAccessibleName(f'{stage} stage: {detail}')

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        active = self.isChecked()
        p = self._palette
        painter.setPen(QPen(QColor(p.accent_fill if active else p.line_strong), 1))
        painter.setBrush(QColor(p.accent_fill) if active else Qt.NoBrush)
        painter.drawEllipse(QRectF(12, 15, 16, 16))
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor(p.on_accent if active else p.muted))
        painter.drawText(QRectF(12, 15, 16, 16), Qt.AlignCenter, str(self.index + 1))
        font.setPixelSize(14)
        font.setWeight(QFont.DemiBold if active else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor(p.accent_text if active else p.text))
        painter.drawText(QRectF(40, 10, self.width()-46, 22), Qt.AlignLeft | Qt.AlignVCenter, self.stage)
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(p.muted))
        painter.drawText(QRectF(40, 32, self.width()-46, 20), Qt.AlignLeft | Qt.AlignVCenter, self.detail)


class Columns(QWidget):
    """The mockup's working area and reference column, stacked on narrow windows."""
    def __init__(self, parent_layout):
        super().__init__()
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.box.setSizeConstraint(QLayout.SetNoConstraint)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(28)
        self.box.setAlignment(Qt.AlignTop)
        self.columns = []
        for _ in range(2):
            panel = QWidget()
            policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            policy.setHeightForWidth(True)
            panel.setSizePolicy(policy)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            layout.setSizeConstraint(QLayout.SetNoConstraint)
            layout.setAlignment(Qt.AlignTop)
            self.box.addWidget(panel, 1, Qt.AlignTop)
            self.columns.append(layout)
        parent_layout.addWidget(self)

    def reflow(self, available):
        direction = QBoxLayout.TopToBottom if available < 780 else QBoxLayout.LeftToRight
        if self.box.direction() != direction:
            self.box.setDirection(direction)
            for index in range(self.box.count()):
                self.box.setStretch(index, 0 if direction == QBoxLayout.TopToBottom else 1)
            self.updateGeometry()


class PageScroll(QScrollArea):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        for columns in self.findChildren(Columns):
            columns.reflow(self.viewport().width() - 2 * PAGE_MARGIN)
