"""Direct manipulation of physical controls as tiles; numeric codes stay out of the UI."""
import math
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)
from nam.capture.params import KnobSpec, validate_knobs

from .controls import SwitchSpec
from .ui.widgets.knobs import ControlGlyph

MAX_CONTROLS = 24
TILE_WIDTH, TILE_HEIGHT, TILE_GAP = 118, 140, 10
VISIBLE_ROWS = 3


def starter(amp=False):
    names = ('Gain', 'Bass', 'Mid', 'Treble', 'Presence', 'Master') if amp else ('Drive', 'Tone')
    controls = [KnobSpec(n, 0, 10, .5, avoid_zero=i == 0 or n == 'Master', is_gain=i == 0)
                for i, n in enumerate(names)]
    if amp:
        controls.append(SwitchSpec('Bright', 0, 1, 1, 0))
    return tuple(controls)


def is_untouched_starter(controls: tuple) -> bool:
    """True when `controls` is exactly the pedal or the amp starter."""
    return tuple(controls) in (starter(False), starter(True))


def swap_starter(controls: tuple, amp: bool) -> tuple:
    """The other gear type's starter, but only if the user has not changed the list."""
    return starter(amp) if is_untouched_starter(controls) else controls


def _range_text(control) -> str:
    if isinstance(control, SwitchSpec):
        text = ' / '.join(control.enum_names)
        return text if len(text) <= 14 else f'{len(control.enum_names)} positions'
    return f'{control.min:g} – {control.max:g}'


class ControlTile(QFrame):
    """One knob or switch: glyph, editable name, range button and a remove button."""

    def __init__(self, editor, index: int, control):
        super().__init__()
        self.setProperty('card', True)
        self.setFixedSize(TILE_WIDTH, TILE_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.addStretch()
        remove = QPushButton('×')
        remove.setProperty('quiet', True)
        remove.setFixedSize(22, 22)
        remove.setAccessibleName(f'Remove {control.name}')
        remove.clicked.connect(lambda checked=False: editor.remove(index))
        top.addWidget(remove)
        layout.addLayout(top)
        self.glyph = ControlGlyph(isinstance(control, SwitchSpec))
        layout.addWidget(self.glyph, 0, Qt.AlignHCenter)
        name = QLineEdit(control.name)
        name.setAlignment(Qt.AlignCenter)
        name.setMinimumHeight(34)
        name.setAccessibleName(f'Control {index + 1} name')
        name.editingFinished.connect(lambda field=name: editor.rename(index, field))
        layout.addWidget(name)
        settings = QPushButton(_range_text(control).replace('&', '&&'))
        settings.setProperty('link', True)
        settings.setToolTip('Edit switch positions' if isinstance(control, SwitchSpec) else 'Edit dial range and gain role')
        settings.setAccessibleName(f'{control.name} settings')
        settings.clicked.connect(lambda checked=False: editor.edit(index))
        layout.addWidget(settings, 0, Qt.AlignHCenter)


class ControlEditor(QWidget):
    changed = Signal()

    def __init__(self, appearance=None):
        super().__init__()
        self.appearance = appearance
        self.controls = starter()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self.rows = QWidget()
        self.rows.setObjectName('tiles')
        self.grid = QGridLayout(self.rows)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(TILE_GAP)
        self.grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.rows)
        box.addWidget(self.scroll)
        self.add_knob = self._add_tile('+ Knob', False)
        self.add_switch = self._add_tile('+ Switch', True)
        self._tiles: list[QWidget] = []
        if appearance is not None:
            appearance.changed.connect(self._set_palette)
        self.set_controls(self.controls)

    def _set_palette(self, palette) -> None:
        for tile in self._tiles:
            tile.glyph.set_palette(palette)

    def _add_tile(self, text: str, switch: bool) -> QPushButton:
        tile = QPushButton(text)
        tile.setProperty('addTile', True)
        tile.setFixedSize(TILE_WIDTH, TILE_HEIGHT)
        tile.clicked.connect(lambda checked=False: self.add_control(switch))
        return tile

    def set_controls(self, controls):
        self.controls = tuple(controls)
        for tile in getattr(self, '_tiles', []):
            self.grid.removeWidget(tile)
            tile.hide()
            tile.deleteLater()
        self._tiles = [ControlTile(self, i, c) for i, c in enumerate(self.controls)]
        if self.appearance is not None:
            self._set_palette(self.appearance.palette())
        self.add_knob.setEnabled(len(self.controls) < MAX_CONTROLS)
        self.add_switch.setEnabled(len(self.controls) < MAX_CONTROLS)
        self._reflow()

    def _columns(self) -> int:
        width = self.scroll.viewport().width() or self.width()
        return max(1, (width + TILE_GAP) // (TILE_WIDTH + TILE_GAP))

    def _reflow(self) -> None:
        items = [*self._tiles, self.add_knob, self.add_switch]
        for widget in items:
            self.grid.removeWidget(widget)
        columns = self._columns()
        for position, widget in enumerate(items):
            row, column = divmod(position, columns)
            self.grid.addWidget(widget, row, column)
            widget.show()
        rows = math.ceil(len(items) / columns)
        visible = min(rows, VISIBLE_ROWS)
        self.scroll.setFixedHeight(visible * TILE_HEIGHT + (visible - 1) * TILE_GAP + 2)
        self.setFixedHeight(self.scroll.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._columns() != getattr(self, '_last_columns', None):
            self._last_columns = self._columns()
            self._reflow()

    def commit(self, controls):
        validate_knobs(controls)
        self.set_controls(controls)
        self.changed.emit()

    def rename(self, index, field):
        if index >= len(self.controls) or field.text().strip() == self.controls[index].name:
            return
        try:
            controls = list(self.controls)
            controls[index] = replace(controls[index], name=field.text().strip())
            self.commit(controls)
        except ValueError as exc:
            field.setText(self.controls[index].name)
            QMessageBox.warning(self, 'Choose a unique control name', str(exc))

    def add_control(self, switch=False):
        if len(self.controls) >= MAX_CONTROLS:
            return
        base = 'Switch' if switch else 'Knob'
        names = {c.name.casefold() for c in self.controls}
        index = 1
        while f'{base} {index}'.casefold() in names:
            index += 1
        c = SwitchSpec(f'{base} {index}', 0, 1, 1, 0) if switch else KnobSpec(f'{base} {index}', 0, 10, .5)
        self.commit((*self.controls, c))

    def remove(self, index):
        controls = self.controls[:index] + self.controls[index+1:]
        if not any(not isinstance(c, SwitchSpec) for c in controls):
            QMessageBox.information(self, 'Keep one knob', 'A parametric capture needs at least one knob. Add its replacement before removing this one.')
            return
        self.commit(controls)

    def edit(self, index):
        c = self.controls[index]
        dialog = QDialog(self)
        dialog.setWindowTitle(f'{c.name} settings')
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        if isinstance(c, SwitchSpec):
            layout.addWidget(QLabel('Name each physical switch position, one per line.\nEvery combination will be captured.'))
            positions = QPlainTextEdit('\n'.join(c.enum_names))
            positions.setAccessibleName('Switch position names')
            layout.addWidget(positions)
        else:
            low, high = QDoubleSpinBox(), QDoubleSpinBox()
            for spin, value in [(low, c.min), (high, c.max)]:
                spin.setRange(-10000, 10000)
                spin.setDecimals(3)
                spin.setValue(value)
            form.addRow('Dial minimum', low)
            form.addRow('Dial maximum', high)
            gain = QCheckBox('This is the gain / drive knob')
            gain.setChecked(c.is_gain)
            silent = QCheckBox('Avoid zero: this knob mutes the sound at zero')
            silent.setChecked(c.avoid_zero)
            form.addRow(gain)
            form.addRow(silent)
            layout.addLayout(form)
        error = QLabel()
        error.setWordWrap(True)
        error.setProperty('role', 'warn')
        layout.addWidget(error)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        actions.rejected.connect(dialog.reject)
        def save():
            try:
                controls = list(self.controls)
                if isinstance(c, SwitchSpec):
                    names = tuple(n.strip() for n in positions.toPlainText().splitlines() if n.strip())
                    updated = SwitchSpec(c.name, 0, len(names)-1, 1, 0, enum_names=names)
                    updated.to_param_spec()
                else:
                    updated = KnobSpec(c.name, low.value(), high.value(), (high.value()-low.value())*.05,
                        is_gain=gain.isChecked(), avoid_zero=silent.isChecked())
                    if updated.is_gain:
                        controls = [replace(other, is_gain=False) for other in controls]
                controls[index] = updated
                self.commit(controls)
                dialog.accept()
            except ValueError as exc:
                error.setText(str(exc))
        actions.accepted.connect(save)
        layout.addWidget(actions)
        dialog.resize(430, 300)
        dialog.exec()
