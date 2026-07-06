from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QWidget


def make_text_edit(
    parent: QWidget | None = None,
    *,
    read_only: bool = False,
    min_lines: int | None = None,
) -> QPlainTextEdit:
    editor = QPlainTextEdit(parent)
    editor.setReadOnly(read_only)
    editor.setTabChangesFocus(True)
    if min_lines is not None:
        metrics = editor.fontMetrics()
        editor.setMinimumHeight(metrics.lineSpacing() * min_lines + 24)
    return editor


def set_text_content(widget: QPlainTextEdit, content: str) -> None:
    widget.setPlainText(content)


def text_content(widget: QPlainTextEdit) -> str:
    return widget.toPlainText()
