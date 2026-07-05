from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from types import TracebackType

from ai_interviewer.config import default_log_path


logger = logging.getLogger(__name__)

_dialog_lock = threading.Lock()
_dialog_open = False


def format_exception(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> str:
    return "".join(traceback.format_exception(exc_type, exc, tb))


def show_crash_dialog(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
    """Show a friendly crash dialog with the log location and a copyable traceback.

    Safe to call from any state; falls back silently if Tk itself is unusable.
    Re-entrant calls (an exception raised while the dialog is open) are dropped.
    """
    global _dialog_open
    with _dialog_lock:
        if _dialog_open:
            return
        _dialog_open = True
    try:
        _show_crash_dialog(exc_type, exc, tb)
    except Exception:
        logger.exception("Could not display the crash dialog.")
    finally:
        with _dialog_lock:
            _dialog_open = False


def _show_crash_dialog(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
    import tkinter as tk
    from tkinter import ttk

    detail = format_exception(exc_type, exc, tb)
    log_path = default_log_path()

    root = tk._default_root  # noqa: SLF001 - only sane way to find a live Tk instance
    owns_root = root is None
    if owns_root:
        root = tk.Tk()
        root.withdraw()

    window = tk.Toplevel(root)
    window.title("AI Interviewer - 오류")
    window.geometry("640x420")
    window.minsize(520, 320)
    try:
        window.attributes("-topmost", True)
    except tk.TclError:
        pass

    frame = ttk.Frame(window, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="예상하지 못한 오류가 발생했습니다.",
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        frame,
        text=(
            "작업 내용은 자동 저장된 범위까지 보존됩니다. 문제가 반복되면 아래 로그 파일과 함께\n"
            f"문의해 주세요.\n로그 파일: {log_path}"
        ),
        justify="left",
    ).pack(anchor="w", pady=(8, 8))

    text = tk.Text(frame, height=10, wrap="none")
    text.insert("1.0", detail)
    text.configure(state="disabled")
    text.pack(fill="both", expand=True)

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=(10, 0))

    def copy_detail() -> None:
        window.clipboard_clear()
        window.clipboard_append(detail)

    def open_log_folder() -> None:
        folder = log_path.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))  # noqa: S606 - intentional shell open
        except OSError:
            logger.exception("Could not open the log folder: %s", folder)

    ttk.Button(buttons, text="오류 내용 복사", command=copy_detail).pack(side="left")
    ttk.Button(buttons, text="로그 폴더 열기", command=open_log_folder).pack(side="left", padx=(8, 0))
    ttk.Button(buttons, text="닫기", command=window.destroy).pack(side="right")

    window.transient(root)
    try:
        window.grab_set()
    except tk.TclError:
        pass
    if owns_root:
        # No mainloop is running (top-level excepthook); pump events until the
        # dialog closes, then drop the temporary root.
        root.wait_window(window)
        root.destroy()


def install_thread_excepthooks() -> None:
    """Log (and best-effort surface) exceptions from non-Tk threads and interpreter top level."""

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
