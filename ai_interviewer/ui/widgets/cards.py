from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ai_interviewer.ui.state import Prop, bind_label
from ai_interviewer.ui.theme.manager import active_tokens


def frame(variant: str = "card", parent: QWidget | None = None) -> QFrame:
    """A themed surface; `variant` maps to the QSS QFrame[variant=...] rules."""
    result = QFrame(parent)
    result.setProperty("variant", variant)
    return result


def vbox(widget: QWidget, margin: int | tuple[int, int, int, int] = 0, spacing: int = 0) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    _apply_margin(layout, margin)
    layout.setSpacing(spacing)
    return layout


def hbox(widget: QWidget, margin: int | tuple[int, int, int, int] = 0, spacing: int = 0) -> QHBoxLayout:
    layout = QHBoxLayout(widget)
    _apply_margin(layout, margin)
    layout.setSpacing(spacing)
    return layout


def grid(widget: QWidget, margin: int | tuple[int, int, int, int] = 0, spacing: int = 0) -> QGridLayout:
    layout = QGridLayout(widget)
    _apply_margin(layout, margin)
    layout.setSpacing(spacing)
    return layout


def _apply_margin(layout, margin: int | tuple[int, int, int, int]) -> None:
    if isinstance(margin, tuple):
        layout.setContentsMargins(*margin)
    else:
        layout.setContentsMargins(margin, margin, margin, margin)


def label(
    text: str = "",
    role: str | None = None,
    *,
    wrap: bool = False,
    parent: QWidget | None = None,
) -> QLabel:
    result = QLabel(text, parent)
    if role:
        result.setProperty("role", role)
    if wrap:
        result.setWordWrap(True)
        result.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return result


def bound_label(prop: Prop, role: str | None = None, *, wrap: bool = False) -> QLabel:
    result = label("", role, wrap=wrap)
    bind_label(result, prop)
    return result


def section_header(title: str, subtitle: str | None = None) -> QWidget:
    holder = QWidget()
    layout = vbox(holder, 0, 2)
    layout.addWidget(label(title, "title"))
    if subtitle:
        layout.addWidget(label(subtitle, "subtitle", wrap=True))
    return holder


def metric_tile(label_text: str, prop: Prop) -> QFrame:
    t = active_tokens()
    tile = frame("subtle")
    layout = vbox(tile, (t.sp[3], t.sp[2], t.sp[3], t.sp[2]), 2)
    layout.addWidget(label(label_text.upper(), "metricLabel"))
    layout.addWidget(bound_label(prop, "metricValue"))
    return tile


def status_row(layout: QGridLayout, row: int, label_text: str, prop: Prop, role: str = "status") -> QLabel:
    layout.addWidget(label(label_text, "muted"), row, 0)
    value = bound_label(prop, role, wrap=True)
    layout.addWidget(value, row, 1)
    return value
