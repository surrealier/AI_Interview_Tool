from __future__ import annotations

import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from ai_interviewer.ui.workers import run_bg


def test_run_bg_delivers_result_on_main_thread(qtbot) -> None:
    outcome = {}
    main_thread = threading.get_ident()

    def work():
        assert threading.get_ident() != main_thread
        return "payload"

    def on_done(result):
        outcome["result"] = result
        outcome["thread"] = threading.get_ident()

    run_bg(None, work, on_done=on_done, name="test-done")
    qtbot.waitUntil(lambda: "result" in outcome, timeout=3000)
    assert outcome["result"] == "payload"
    assert outcome["thread"] == main_thread


def test_run_bg_delivers_error_on_main_thread(qtbot) -> None:
    outcome = {}
    main_thread = threading.get_ident()

    def work():
        raise ValueError("boom")

    def on_error(exc):
        outcome["exc"] = exc
        outcome["thread"] = threading.get_ident()

    run_bg(None, work, on_error=on_error, name="test-error")
    qtbot.waitUntil(lambda: "exc" in outcome, timeout=3000)
    assert isinstance(outcome["exc"], ValueError)
    assert outcome["thread"] == main_thread


def test_run_bg_without_error_handler_logs(qtbot, caplog) -> None:
    def work():
        raise RuntimeError("unhandled")

    with caplog.at_level("ERROR", logger="ai_interviewer.ui.workers"):
        run_bg(None, work, name="test-log")
        qtbot.waitUntil(
            lambda: any("test-log" in record.message for record in caplog.records),
            timeout=3000,
        )


def test_run_bg_drops_callback_for_destroyed_owner(qtbot) -> None:
    from PySide6.QtWidgets import QWidget

    gate = threading.Event()
    called = []

    owner = QWidget()

    def work():
        gate.wait(2)
        return 1

    run_bg(owner, work, on_done=lambda result: called.append(result), name="test-drop")
    owner.deleteLater()
    qtbot.wait(50)  # process deleteLater before the worker finishes
    gate.set()
    qtbot.wait(300)
    assert called == []
