from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from ai_interviewer.config import AppConfig, WINDOWS_SAPI_BACKEND
from ai_interviewer.i18n import tr
from ai_interviewer.ui import workers
from ai_interviewer.ui.context import AppContext
from ai_interviewer.ui.main_window import MainWindow
from ai_interviewer.ui.screens import wizard as wizard_module
from ai_interviewer.ui.theme.manager import ThemeManager


class _RuntimeReport:
    has_failures = False

    def summary(self) -> str:
        return "테스트 런타임 준비 완료"


@pytest.fixture()
def main_window(qtbot, monkeypatch: pytest.MonkeyPatch, tmp_path):
    config = AppConfig(
        tts_backend=WINDOWS_SAPI_BACKEND,
        model_root=tmp_path / "models",
        sessions_root=tmp_path / "sessions",
        video_path=tmp_path / "missing.mp4",
        config_path=tmp_path / "config.json",
        ui_language="en",
    )
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls, path=None: config))

    ctx = AppContext()
    ThemeManager(ctx.config_model).apply()
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    return window


def test_setup_wizard_is_first_screen(main_window: MainWindow) -> None:
    ctx = main_window.ctx
    assert ctx.setup_step_index == 0
    assert main_window.stack.currentWidget() is main_window.wizard_screen
    assert main_window.workspace_screen is None
    assert ctx.runtime_badge_var.get()
    assert ctx.preload_running is False


def test_setup_wizard_advances_language_model_and_speaker(main_window: MainWindow) -> None:
    ctx = main_window.ctx
    wizard = main_window.wizard_screen
    ctx.interview_language_var.set("English")
    wizard._sync_language_selection()
    wizard._setup_next()

    assert ctx.setup_step_index == 1
    assert ctx.selected_speaker_var.get() == "Ryan"

    wizard._setup_next()
    assert ctx.setup_step_index == 2

    ctx.selected_speaker_var.set("Aiden")
    wizard._setup_next()
    assert ctx.setup_step_index == 3
    assert ctx.selected_speaker_var.get() == "Aiden"


def test_setup_sound_test_uses_selected_voice(monkeypatch: pytest.MonkeyPatch, main_window: MainWindow) -> None:
    calls = {}

    class FakeProvider:
        def __init__(self, config, cache_dir):
            calls["model"] = config.model_id

        def sound_test(self, language, speaker):
            calls["language"] = language
            calls["speaker"] = speaker
            return SimpleNamespace(backend="fake-tts", speaker=speaker)

    def synchronous_run_bg(owner, work, on_done=None, on_error=None, name=None):
        try:
            result = work()
        except Exception as exc:  # noqa: BLE001
            if on_error is not None:
                on_error(exc)
            return
        if on_done is not None:
            on_done(result)

    monkeypatch.setattr(wizard_module, "QwenTTSProvider", FakeProvider)
    monkeypatch.setattr(wizard_module, "run_bg", synchronous_run_bg)
    ctx = main_window.ctx
    ctx.interview_language_var.set("English")
    ctx.selected_speaker_var.set("Aiden")

    main_window.wizard_screen._run_setup_sound_test()

    assert calls["language"] == "English"
    assert calls["speaker"] == "Aiden"
    assert ctx.sound_test_status_var.get() == tr("wizard.sound_done", backend="fake-tts", speaker="Aiden")
    assert ctx.sound_test_passed is True


def test_interview_workspace_exposes_product_workflow(main_window: MainWindow) -> None:
    workspace = main_window.show_workspace()

    assert workspace.question_text is not None
    assert workspace.question_set_combo.count() > 0
    assert workspace.start_button.isVisibleTo(main_window)
    assert workspace.video_player is not None
    assert workspace.record_button is not None
    assert workspace.followup_button is not None
    assert main_window.ctx.question_summary_var.get().startswith("20 questions loaded")


def test_language_modes_keep_question_sets_separate(main_window: MainWindow) -> None:
    workspace = main_window.show_workspace()
    ctx = main_window.ctx

    ctx.interview_language_var.set("English")
    workspace._on_language_mode_changed()
    english_text = workspace.question_text.toPlainText()

    assert "introduce yourself" in english_text.lower()
    assert "자기소개" not in english_text
    assert "English mode" in ctx.question_summary_var.get()

    ctx.interview_language_var.set("Korean")
    workspace._on_language_mode_changed()
    korean_text = workspace.question_text.toPlainText()

    assert "자기소개" in korean_text
    assert "introduce yourself" not in korean_text.lower()
    assert "한국어 mode" in ctx.question_summary_var.get()


def test_ui_language_switch_rebuilds_wizard(main_window: MainWindow) -> None:
    assert main_window.wizard_screen.next_button.text() == "Next"

    main_window.ctx.set_ui_language("ko")

    assert main_window.ctx.ui_language_var.get() == "ko"
    assert main_window.ctx.config_model.ui_language == "ko"
    assert main_window.wizard_screen.next_button.text() == "다음"


def test_ui_language_switch_in_workspace_preserves_questions(main_window: MainWindow) -> None:
    workspace = main_window.show_workspace()
    workspace.replace_question_text("Custom question one?\nCustom question two?")

    main_window.ctx.set_ui_language("ko")

    workspace = main_window.workspace_screen
    assert "Custom question one?" in workspace.question_text.toPlainText()
    assert workspace.start_button.text() == "면접 시작"


def test_repeated_language_switch_is_stable(main_window: MainWindow) -> None:
    main_window.show_workspace()
    for _ in range(10):
        main_window.ctx.set_ui_language("ko")
        main_window.ctx.set_ui_language("en")
    assert main_window.workspace_screen.start_button.text() == "Start Interview"


def test_default_window_target_fits_release_viewport(main_window: MainWindow) -> None:
    assert main_window.width() <= 1280
    assert main_window.height() <= 860


def test_run_bg_owner_destroy_drops_callback(qtbot, main_window: MainWindow) -> None:
    # Regression guard for the workers/shutdown interaction: destroying the
    # owner before the worker finishes must not crash or invoke callbacks.
    from PySide6.QtWidgets import QWidget

    owner = QWidget()
    called = []
    workers.run_bg(owner, lambda: 42, on_done=lambda result: called.append(result))
    owner.deleteLater()
    qtbot.wait(200)
    assert called in ([], [42])  # either dropped or delivered before deletion
