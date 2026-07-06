from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel


class Prop(QObject):
    """Observable value with the same get()/set() contract as tk.StringVar.

    Handler bodies ported from the Tk app keep calling ``prop.get()`` /
    ``prop.set(value)``; widgets subscribe through ``changed``.
    """

    changed = Signal(object)

    def __init__(self, value: Any = "") -> None:
        super().__init__()
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        if value != self._value:
            self._value = value
            self.changed.emit(value)


class BoolProp(Prop):
    def __init__(self, value: bool = False) -> None:
        super().__init__(bool(value))

    def get(self) -> bool:
        return bool(self._value)

    def set(self, value: Any) -> None:  # noqa: D102 - same contract
        super().set(bool(value))


def bind_label(label: QLabel, prop: Prop, formatter: Callable[[Any], str] | None = None) -> None:
    """Keep a QLabel's text in sync with a Prop (initial value + updates).

    The connection is owned by the label: when the label is destroyed the
    connection dies with it, so rebuilt screens never leak stale receivers.
    """

    def _apply(value: Any) -> None:
        label.setText(formatter(value) if formatter else str(value))

    _apply(prop.get())
    prop.changed.connect(_apply)
    label.destroyed.connect(lambda: _safe_disconnect(prop, _apply))


def _safe_disconnect(prop: Prop, slot: Callable) -> None:
    try:
        prop.changed.disconnect(slot)
    except (RuntimeError, TypeError):
        pass
