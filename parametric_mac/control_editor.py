"""Direct manipulation of physical controls; numeric codes stay out of the UI."""
from dataclasses import replace
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QScrollArea, QDialog, QFormLayout, QDoubleSpinBox, QCheckBox,
    QPlainTextEdit, QDialogButtonBox, QMessageBox, QLayout)
from nam.capture.params import KnobSpec, validate_knobs
from .controls import SwitchSpec


def starter(amp=False):
    names = ('Gain', 'Bass', 'Mid', 'Treble', 'Presence', 'Master') if amp else ('Drive', 'Tone')
    controls = [KnobSpec(n, 0, 10, .5, avoid_zero=i == 0 or n == 'Master', is_gain=i == 0)
                for i, n in enumerate(names)]
    if amp:
        controls.append(SwitchSpec('Bright', 0, 1, 1, 0))
    return tuple(controls)


class ControlEditor(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.controls = starter()
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(8)
        self.rows = QWidget()
        self.rows.setStyleSheet("background: #ffffff;")
        self.rows_layout = QVBoxLayout(self.rows)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.rows_layout.setSizeConstraint(QLayout.SetMinimumSize)
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(self.rows)
        scroll.setMinimumHeight(92)
        scroll.setMaximumHeight(292)
        self.box.addWidget(scroll)
        buttons = QHBoxLayout()
        self.add_knob = QPushButton('Add knob')
        self.add_switch = QPushButton('Add switch')
        self.add_knob.clicked.connect(lambda: self.add_control(False))
        self.add_switch.clicked.connect(lambda: self.add_control(True))
        buttons.addWidget(self.add_knob)
        buttons.addWidget(self.add_switch)
        buttons.addStretch()
        self.box.addLayout(buttons)
        self.set_controls(self.controls)

    def set_controls(self, controls):
        self.controls = tuple(controls)
        self.scroll.setFixedHeight(min(292, max(92, len(controls)*42 + max(0, len(controls)-1)*6)))
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        for i, c in enumerate(self.controls):
            row = QWidget()
            row.setFixedHeight(42)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            name = QLineEdit(c.name)
            name.setMinimumWidth(80)
            name.setAccessibleName(f'Control {i+1} name')
            name.editingFinished.connect(lambda index=i, field=name: self.rename(index, field))
            positions = ' / '.join(c.enum_names) if isinstance(c, SwitchSpec) else f'{c.min:g}–{c.max:g}'
            settings = QPushButton((positions if len(positions) <= 20 else f'{len(c.enum_names)} positions').replace('&', '&&'))
            settings.setToolTip('Edit switch positions' if isinstance(c, SwitchSpec) else 'Edit dial range and gain role')
            settings.setAccessibleName(f'{c.name} settings')
            settings.clicked.connect(lambda checked=False, index=i: self.edit(index))
            remove = QPushButton('Remove')
            remove.setAccessibleName(f'Remove {c.name}')
            remove.clicked.connect(lambda checked=False, index=i: self.remove(index))
            layout.addWidget(name, 1)
            layout.addWidget(settings)
            layout.addWidget(remove)
            self.rows_layout.addWidget(row)

        self.add_knob.setEnabled(len(controls) < 24)
        self.add_switch.setEnabled(len(controls) < 24)

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
        if len(self.controls) >= 24:
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
        error.setStyleSheet('color: #925517')
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
