"""Small shared widgets and layout helpers."""
from PySide6.QtCore import Qt, QRectF, QSize, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
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


class TrainingProfiles(QWidget):
    def __init__(self, combo):
        super().__init__()
        self.setObjectName('profiles')
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.buttons = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(('Full training', 'Quick test', 'Custom')):
            choice = QPushButton(text)
            choice.setProperty('profile', True)
            choice.setCheckable(True)
            choice.setAccessibleName(combo.itemText(i))
            choice.clicked.connect(lambda checked=False, index=i: combo.setCurrentIndex(index))
            self.group.addButton(choice, i)
            layout.addWidget(choice, 1)
            self.buttons.append(choice)
        def selected(index):
            for i, choice in enumerate(self.buttons):
                choice.setChecked(i == index)
                choice.setAccessibleName(combo.itemText(i))
        combo.currentIndexChanged.connect(selected)
        combo.currentTextChanged.connect(lambda _: selected(combo.currentIndex()))
        selected(combo.currentIndex())


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
