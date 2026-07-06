from __future__ import annotations

import logging
import sys
import threading
import traceback
from types import TracebackType


logger = logging.getLogger(__name__)

_dialog_lock = threading.Lock()
_dialog_open = False


def format_exception(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> str:
    return "".join(traceback.format_exception(exc_type, exc, tb))


def show_crash_dialog(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
    """Show a friendly crash dialog with the log location and a copyable traceback.

    Safe to call from any state; falls back silently if the GUI toolkit is
    unusable. Re-entrant calls (an exception raised while the dialog is open)
    are dropped. The Qt dialog is imported lazily so that headless entry
    points (--smoke) never load PySide6.
    """
    global _dialog_open
    with _dialog_lock:
        if _dialog_open:
            return
        _dialog_open = True
    try:
        from ai_interviewer.ui.dialogs.crash_dialog import show_qt_crash_dialog

        show_qt_crash_dialog(exc_type, exc, tb)
    except Exception:
        logger.exception("Could not display the crash dialog.")
    finally:
        with _dialog_lock:
            _dialog_open = False


def install_thread_excepthooks() -> None:
    """Log (and best-effort surface) exceptions from worker threads and the
    interpreter top level. PySide6 routes unhandled slot exceptions through
    sys.excepthook as well (verified on the pinned version), so Qt callback
    errors also land here."""

    def sys_hook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        show_crash_dialog(exc_type, exc, tb)

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit:
            return
        logger.critical(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = sys_hook
    threading.excepthook = thread_hook
