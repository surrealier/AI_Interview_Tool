from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

from ai_interviewer.ui.state import BoolProp, Prop


# Two-way bindings are loop-safe because Prop.set() ignores equal values.


def bind_combo(combo: QComboBox, prop: Prop) -> None:
    combo.setCurrentText(str(prop.get()))
    combo.currentTextChanged.connect(prop.set)

    def _sync(value) -> None:
        text = str(value)
        if combo.currentText() != text:
            combo.setCurrentText(text)

    prop.changed.connect(_sync)
    combo.destroyed.connect(lambda: _safe_disconnect(prop, _sync))


def bind_line_edit(edit: QLineEdit, prop: Prop) -> None:
    edit.setText(str(prop.get()))
    edit.textChanged.connect(prop.set)

    def _sync(value) -> None:
        text = str(value)
        if edit.text() != text:
            edit.setText(text)

    prop.changed.connect(_sync)
    edit.destroyed.connect(lambda: _safe_disconnect(prop, _sync))


def bind_checkbox(checkbox: QCheckBox, prop: BoolProp) -> None:
    checkbox.setChecked(bool(prop.get()))
    checkbox.toggled.connect(prop.set)

    def _sync(value) -> None:
        checked = bool(value)
        if checkbox.isChecked() != checked:
            checkbox.setChecked(checked)

    prop.changed.connect(_sync)
    checkbox.destroyed.connect(lambda: _safe_disconnect(prop, _sync))


def _safe_disconnect(prop: Prop, slot) -> None:
    try:
        prop.changed.disconnect(slot)
    except (RuntimeError, TypeError):
        pass
