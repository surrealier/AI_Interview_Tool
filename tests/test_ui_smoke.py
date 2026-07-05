from __future__ import annotations

import tkinter as tk
import time
from types import SimpleNamespace

import pytest

from ai_interviewer import gui, setup_wizard, tasks
from ai_interviewer.config import AppConfig, WINDOWS_SAPI_BACKEND


class _RuntimeReport:
    has_failures = False

    def summary_ko(self) -> str:
        return "테스트 런타임 준비 완료"


def _tk_available() -> bool:
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except tk.TclError:
        return False
    return True


def _reset_ttkbootstrap_singleton() -> None:
    # ttkbootstrap keeps process-wide state bound to the first Tk root: the
    # Style singleton and the theme-change Publisher subscriptions. Stale
    # references to a destroyed root break later widget creation.
    try:
        import ttkbootstrap
        from ttkbootstrap.publisher import Publisher

        ttkbootstrap.Style.instance = None
        Publisher.clear_subscribers()
    except ImportError:
        pass


@pytest.fixture()
def interview_app(monkeypatch: pytest.MonkeyPatch, tmp_path):
    if not _tk_available():
        pytest.skip("Tk display is not available.")
    _reset_ttkbootstrap_singleton()

    config = AppConfig(
        tts_backend=WINDOWS_SAPI_BACKEND,
        model_root=tmp_path / "models",
        sessions_root=tmp_path / "sessions",
        video_path=tmp_path / "missing.mp4",
        config_path=tmp_path / "config.json",
    )
    monkeypatch.setattr(gui.AppConfig, "load", classmethod(lambda cls, path=None: config))
    monkeypatch.setattr(gui, "collect_runtime_diagnostics", lambda _config: _RuntimeReport())
    monkeypatch.setattr(gui.QwenTTSProvider, "preload", lambda _self: pytest.fail("preload should not run on app startup"))
    monkeypatch.setattr(gui.InterviewApp, "_run_startup_diagnostics", lambda _self: None)

    try:
        app = gui.InterviewApp()
    except tk.TclError as exc:
        pytest.skip(f"Tk could not be initialized: {exc}")
    app.withdraw()
    app.update_idletasks()
    yield app
    if app.winfo_exists():
        app.destroy()
    _reset_ttkbootstrap_singleton()


def test_setup_wizard_is_first_screen(interview_app: gui.InterviewApp) -> None:
    assert interview_app.setup_step_index == 0
    assert interview_app.setup_content is not None
    assert not hasattr(interview_app, "question_text")
    assert not hasattr(interview_app, "video_player")
    assert interview_app.runtime_badge_var.get()
    assert interview_app.preload_running is False


def test_setup_wizard_advances_language_model_and_speaker(interview_app: gui.InterviewApp) -> None:
    interview_app.interview_language_var.set("English")
    interview_app._sync_language_selection()
    interview_app._setup_next()

    assert interview_app.setup_step_index == 1
    assert interview_app.selected_speaker_var.get() == "Ryan"

    interview_app._setup_next()
    assert interview_app.setup_step_index == 2

    interview_app.selected_speaker_var.set("Aiden")
    interview_app._setup_next()
    assert interview_app.setup_step_index == 3
    assert interview_app.selected_speaker_var.get() == "Aiden"


def test_setup_sound_test_uses_selected_voice(monkeypatch: pytest.MonkeyPatch, interview_app: gui.InterviewApp) -> None:
    calls = {}

    class FakeProvider:
        def __init__(self, config, cache_dir):
            calls["model"] = config.model_id

        def sound_test(self, language, speaker):
            calls["language"] = language
            calls["speaker"] = speaker
            return SimpleNamespace(backend="fake-tts", speaker=speaker)

    class FakeThread:
        def __init__(self, target, daemon=True, name=None):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(setup_wizard, "QwenTTSProvider", FakeProvider)
    monkeypatch.setattr(tasks.threading, "Thread", FakeThread)
    interview_app.interview_language_var.set("English")
    interview_app.selected_speaker_var.set("Aiden")

    interview_app._run_setup_sound_test()
    deadline = time.monotonic() + 2
    while "테스트 완료" not in interview_app.sound_test_status_var.get() and time.monotonic() < deadline:
        interview_app.update()
        time.sleep(0.02)

    assert calls["language"] == "English"
    assert calls["speaker"] == "Aiden"
    assert "테스트 완료" in interview_app.sound_test_status_var.get()


def test_interview_workspace_exposes_product_workflow(interview_app: gui.InterviewApp) -> None:
    interview_app._show_interview_workspace()

    assert interview_app.question_text.winfo_exists()
    assert interview_app.question_set_combo.winfo_exists()
    assert interview_app.start_button.winfo_exists()
    assert interview_app.video_player.widget.winfo_exists()
    assert interview_app.record_button.winfo_exists()
    assert interview_app.followup_button.winfo_exists()
    assert interview_app.question_summary_var.get().startswith("20 questions loaded")


def test_language_modes_keep_question_sets_separate(interview_app: gui.InterviewApp) -> None:
    interview_app._show_interview_workspace()
    interview_app.interview_language_var.set("English")
    interview_app._on_language_mode_changed()
    english_text = interview_app.question_text.get("1.0", "end")

    assert "introduce yourself" in english_text.lower()
    assert "자기소개" not in english_text
    assert "English mode" in interview_app.question_summary_var.get()

    interview_app.interview_language_var.set("Korean")
    interview_app._on_language_mode_changed()
    korean_text = interview_app.question_text.get("1.0", "end")

    assert "자기소개" in korean_text
    assert "introduce yourself" not in korean_text.lower()
    assert "한국어 mode" in interview_app.question_summary_var.get()


def test_default_window_target_fits_release_viewport(interview_app: gui.InterviewApp) -> None:
    interview_app.update_idletasks()
    width = interview_app.winfo_width()
    height = interview_app.winfo_height()

    assert width <= 1280
    assert height <= 860
