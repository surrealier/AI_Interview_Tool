from __future__ import annotations

import logging
from typing import Any, Callable

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


logger = logging.getLogger(__name__)

# Bridges must outlive their job even if the owner widget dies first; the
# registry keeps them alive until the queued callback has been handled.
_active_bridges: set["_Bridge"] = set()


def _owner_alive(owner: QObject | None) -> bool:
    return owner is None or shiboken6.isValid(owner)


class _Bridge(QObject):
    """Created on the main thread; its bound-method slots guarantee queued
    delivery back to the main thread when the worker emits from the pool."""

    done = Signal(object)
    error = Signal(object)

    def __init__(
        self,
        owner: QObject | None,
        on_done: Callable[[Any], None] | None,
        on_error: Callable[[Exception], None] | None,
        name: str | None,
    ) -> None:
        super().__init__()
        self._owner = owner
        self._on_done = on_done
        self._on_error = on_error
        self._name = name or "worker"
        self.done.connect(self._handle_done)
        self.error.connect(self._handle_error)

    @Slot(object)
    def _handle_done(self, result: Any) -> None:
        try:
            if self._on_done is not None and _owner_alive(self._owner):
                self._on_done(result)
        finally:
            self._finish()

    @Slot(object)
    def _handle_error(self, exc: Exception) -> None:
        try:
            if not _owner_alive(self._owner):
                logger.warning("Background task %s failed after owner was destroyed: %s", self._name, exc)
            elif self._on_error is not None:
                self._on_error(exc)
            else:
                logger.exception("Unhandled error in background task %s", self._name, exc_info=exc)
        finally:
            self._finish()

    def _finish(self) -> None:
        _active_bridges.discard(self)
        self.deleteLater()


class _Job(QRunnable):
    def __init__(self, work: Callable[[], Any], bridge: _Bridge) -> None:
        super().__init__()
        self._work = work
        self._bridge = bridge

    def run(self) -> None:  # executes on a pool thread
        try:
            result = self._work()
        except Exception as exc:  # noqa: BLE001 - marshalled to the UI thread
            self._bridge.error.emit(exc)
        else:
            self._bridge.done.emit(result)


def run_bg(
    owner: QObject | None,
    work: Callable[[], Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    name: str | None = None,
) -> None:
    """Run `work` on the global thread pool and marshal the outcome to the
    main thread. Same call shape as the old tasks.run_bg; if `owner` (a
    QObject/QWidget) is destroyed before completion the callback is dropped.
    """
    bridge = _Bridge(owner, on_done, on_error, name)
    _active_bridges.add(bridge)
    pool = QThreadPool.globalInstance()
    if pool.maxThreadCount() < 4:
        pool.setMaxThreadCount(4)
    pool.start(_Job(work, bridge))
