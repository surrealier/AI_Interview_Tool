from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt, QtMsgType, QTimer, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from ai_interviewer import __version__
from ai_interviewer.config import resource_base_dir
from ai_interviewer.ui.context import AppContext
from ai_interviewer.ui.main_window import MainWindow
from ai_interviewer.ui.theme.manager import ThemeManager


logger = logging.getLogger(__name__)

_QT_LOG_LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


def _qt_message_to_logging(msg_type: QtMsgType, _context, message: str) -> None:
    logging.getLogger("qt").log(_QT_LOG_LEVELS.get(msg_type, logging.WARNING), "%s", message)


def create_app(argv: list[str] | None = None) -> QApplication:
    # Per-monitor fractional scaling without 125%/150% rounding blur.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("AI Interviewer")
    app.setOrganizationName("Surrealier")
    app.setApplicationVersion(__version__)
    icon_path = resource_base_dir() / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    qInstallMessageHandler(_qt_message_to_logging)
    return app


def run_app() -> int:
    app = create_app()
    ctx = AppContext()
    ThemeManager(ctx.config_model).apply(app)
    window = MainWindow(ctx)
    window.show()
    QTimer.singleShot(100, ctx.run_startup_diagnostics)
    return app.exec()
