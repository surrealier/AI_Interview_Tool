from __future__ import annotations

import threading
import tkinter as tk
from typing import Any, Callable


def run_bg(
    widget: tk.Misc,
    work: Callable[[], Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    name: str | None = None,
) -> None:
    """Run `work` on a daemon thread and marshal the outcome to the Tk loop.

    `on_done` receives the return value of `work`; `on_error` receives the
    raised exception. Without `on_error`, exceptions propagate to
    `threading.excepthook` (logged by the global handler).
    """

    def runner() -> None:
        try:
            result = work()
        except Exception as exc:
            if on_error is None:
                raise
            _post(widget, lambda: on_error(exc))
            return
        if on_done is not None:
            _post(widget, lambda: on_done(result))

    threading.Thread(target=runner, daemon=True, name=name).start()


def _post(widget: tk.Misc, action: Callable[[], None]) -> None:
    try:
        widget.after(0, action)
    except tk.TclError:
        # The widget was destroyed while the worker ran; drop the callback.
        pass
