from __future__ import annotations

import logging
import os
import sys
from types import TracebackType

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ai_interviewer.config import default_log_path
from ai_interviewer.error_dialog import format_exception
from ai_interviewer.i18n import tr


logger = logging.getLogger(__name__)


def show_qt_crash_dialog(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> None:
    """Modal crash dialog. Creates a temporary QApplication when invoked
    before/without one (top-level excepthook during startup)."""
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv or ["ai_interviewer"])

    detail = format_exception(exc_type, exc, tb)
    log_path = default_log_path()

    dialog = QDialog()
    dialog.setWindowTitle(tr("crash.title"))
    dialog.resize(640, 420)
    dialog.setMinimumSize(520, 320)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)

    heading = QLabel(tr("crash.heading"))
    heading.setProperty("role", "title")
    layout.addWidget(heading)

    body = QLabel(tr("crash.body", log_path=log_path))
    body.setWordWrap(True)
    layout.addWidget(body)

    text = QPlainTextEdit()
    text.setPlainText(detail)
    text.setReadOnly(True)
    text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    layout.addWidget(text, 1)

    buttons = QHBoxLayout()
    layout.addLayout(buttons)

    copy_button = QPushButton(tr("crash.copy"))
    open_button = QPushButton(tr("crash.open_log"))
    close_button = QPushButton(tr("common.close"))
    buttons.addWidget(copy_button)
    buttons.addWidget(open_button)
    buttons.addStretch(1)
    buttons.addWidget(close_button)

    def copy_detail() -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(detail)

    def open_log_folder() -> None:
        folder = log_path.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))  # noqa: S606 - intentional shell open
        except OSError:
            logger.exception("Could not open the log folder: %s", folder)

    copy_button.clicked.connect(copy_detail)
    open_button.clicked.connect(open_log_folder)
    close_button.clicked.connect(dialog.accept)

    dialog.exec()
    if owns_app:
        del app
