from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from ai_interviewer.app_state import SessionState
from ai_interviewer.config import (
    AppConfig,
    default_tts_cache_dir,
    DEFAULT_MODEL_ID,
    LARGE_MODEL_ID,
    QWEN_BACKEND,
    TOKENIZER_MODEL_ID,
    is_model_installed,
)
from ai_interviewer.default_questions import (
    INTERVIEW_TYPE_HR,
    default_question_set_name,
    question_set_names,
)
from ai_interviewer.diagnostics import collect_runtime_diagnostics
from ai_interviewer.engine import InterviewEngine
from ai_interviewer.i18n import (
    SUPPORTED_UI_LANGUAGES,
    get_language,
    resolve_system_ui_language,
    set_language,
    tr,
)
from ai_interviewer import credentials
from ai_interviewer.intelligence import AISettings, ProviderChain, build_chain
from ai_interviewer.stt import MicrophoneRecorder, WhisperTranscriber
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import default_speaker_for_language
from ai_interviewer.ui.state import BoolProp, Prop
from ai_interviewer.ui.workers import run_bg

if TYPE_CHECKING:
    from ai_interviewer.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


class AppContext(QObject):
    """Owns services and reactive state shared by every screen.

    Replaces the Tk mixin god-object: what used to live as attributes on the
    Tk root now lives here, and screens receive the context explicitly.
    """

    timersTicked = Signal()
    languageRebuildRequested = Signal()
    configApplied = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.window: "MainWindow | None" = None

        self.config_model = AppConfig.load()
        self.config_model.ensure_directories()
        if self.config_model.model_id not in {DEFAULT_MODEL_ID, LARGE_MODEL_ID}:
            self.config_model.model_id = DEFAULT_MODEL_ID
        if self.config_model.ui_language not in SUPPORTED_UI_LANGUAGES:
            self.config_model.ui_language = resolve_system_ui_language()
        set_language(self.config_model.ui_language)

        self.engine: InterviewEngine | None = None
        self.provider: QwenTTSProvider | None = None
        self.preload_provider: QwenTTSProvider | None = None
        self.recorder = MicrophoneRecorder()
        self.transcriber = WhisperTranscriber(self.config_model)
        self.recording = False
        self.recording_path: Path | None = None
        self.preload_running = False
        self.tts_token = 0
        self.tts_running = False
        self.runtime_report = None
        self.session_state = SessionState.IDLE
        self.setup_step_index = 0
        self.setup_custom_questions = ""
        self.sound_test_passed = False

        self._build_variables()

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_timers)
        self._timer.start()

    # -- state ------------------------------------------------------------

    def set_state(self, state: SessionState) -> None:
        self.session_state = state

    def _build_variables(self) -> None:
        interview_language = self.config_model.interview_language
        if interview_language not in {"Korean", "English"}:
            interview_language = "Korean"
        question_set_name = self.config_model.question_set_name
        if question_set_name not in question_set_names(interview_language):
            question_set_name = default_question_set_name(interview_language)

        self.interview_language_var = Prop(interview_language)
        self.question_set_var = Prop(question_set_name)
        self.tts_backend_var = Prop(self.config_model.tts_backend)
        self.model_var = Prop(self.config_model.model_id)
        self.model_root_var = Prop(str(self.config_model.model_root))
        self.video_path_var = Prop(str(self.config_model.video_path))
        self.stt_model_var = Prop(self.config_model.stt_model_size)
        self.stt_device_var = Prop(self.config_model.stt_device)
        self.stt_compute_var = Prop(self.config_model.stt_compute_type)
        self.input_device_var = Prop(self.config_model.input_device)
        self.followup_provider_var = Prop(self.config_model.followup_provider)
        self.ollama_model_var = Prop(self.config_model.ollama_model)
        self.ollama_host_var = Prop(self.config_model.ollama_host)
        # -- analysis layer -------------------------------------------------
        self.ai_provider_var = Prop(self.config_model.ai_provider)
        self.claude_model_var = Prop(self.config_model.claude_model)
        self.ai_effort_var = Prop(self.config_model.ai_effort)
        self.cloud_ai_var = BoolProp(self.config_model.enable_cloud_ai)
        self.live_scoring_var = BoolProp(self.config_model.enable_live_scoring)
        self.adaptive_probing_var = BoolProp(self.config_model.enable_adaptive_probing)
        self.auto_speak_probe_var = BoolProp(self.config_model.auto_speak_probe)
        self.probe_depth_var = Prop(str(self.config_model.max_probe_depth))
        self.target_role_var = Prop(self.config_model.target_role)
        self.seniority_var = Prop(self.config_model.target_seniority)
        self.job_description_var = Prop(self.config_model.job_description)
        self.resume_summary_var = Prop(self.config_model.resume_summary)
        self.coach_status_var = Prop(tr("ws.coach_idle"))
        self.analysis_engine_var = Prop("")
        self.last_score_var = Prop("—")
        self.coverage_var = Prop("0 / 0")
        self.allow_fallback_var = BoolProp(self.config_model.enable_windows_sapi_fallback)
        tts_language = self.config_model.default_language
        if tts_language == "Auto":
            tts_language = interview_language
        self.language_var = Prop(tts_language)
        selected_speaker = self.config_model.selected_speaker or default_speaker_for_language(interview_language).speaker_id
        self.selected_speaker_var = Prop(selected_speaker)
        self.korean_speaker_var = Prop(self.config_model.korean_speaker or "Sohee")
        self.english_speaker_var = Prop(self.config_model.english_speaker or "Ryan")
        self.interview_type_var = Prop(self.config_model.interview_type or INTERVIEW_TYPE_HR)
        self.question_source_var = Prop("default")
        self.ui_language_var = Prop(self.config_model.ui_language)
        self.sound_test_status_var = Prop(tr("app.sound_test_not_run"))
        self.enable_stt_var = BoolProp(self.config_model.enable_stt)
        self.sound_test_required_var = BoolProp(self.config_model.sound_test_required)
        self.status_var = Prop(tr("app.status_initial"))
        self.diagnostic_status_var = Prop(tr("app.diag_waiting"))
        self.runtime_badge_var = Prop(tr("badge.checking"))
        self.question_summary_var = Prop("")
        self.warning_var = Prop(tr("app.warning_initial"))
        self.progress_var = Prop("0 / 0")
        self.answer_timer_var = Prop("00:00")
        self.total_timer_var = Prop("00:00")
        self.current_question_var = Prop(tr("app.no_session"))

    # -- config ------------------------------------------------------------

    def apply_config_from_ui(self, save: bool = True) -> None:
        self.config_model.interview_language = self.interview_language_var.get()
        self.config_model.question_set_name = self.question_set_var.get()
        self.config_model.model_id = self.model_var.get()
        self.config_model.tts_backend = self.tts_backend_var.get()
        self.config_model.model_root = Path(self.model_root_var.get()).expanduser()
        self.config_model.video_path = Path(self.video_path_var.get()).expanduser()
        self.config_model.default_language = self.language_var.get()
        selected_speaker = (
            self.selected_speaker_var.get().strip()
            or default_speaker_for_language(self.interview_language_var.get()).speaker_id
        )
        self.config_model.selected_speaker = selected_speaker
        if self.interview_language_var.get() == "Korean":
            self.korean_speaker_var.set(selected_speaker)
            self.config_model.korean_speaker = selected_speaker
        else:
            self.english_speaker_var.set(selected_speaker)
            self.config_model.english_speaker = selected_speaker
        self.config_model.interview_type = self.interview_type_var.get()
        self.config_model.sound_test_required = bool(self.sound_test_required_var.get())
        self.config_model.enable_stt = bool(self.enable_stt_var.get())
        self.config_model.stt_model_size = self.stt_model_var.get()
        self.config_model.stt_device = self.stt_device_var.get()
        self.config_model.stt_compute_type = self.stt_compute_var.get()
        self.config_model.input_device = self.input_device_var.get()
        self.config_model.followup_provider = self.followup_provider_var.get()
        self.config_model.ollama_model = self.ollama_model_var.get().strip()
        self.config_model.ollama_host = self.ollama_host_var.get().strip() or "http://127.0.0.1:11434"
        self.config_model.enable_windows_sapi_fallback = bool(self.allow_fallback_var.get())
        self.config_model.ui_language = self.ui_language_var.get() or self.config_model.ui_language
        self._apply_ai_config_from_ui()
        self.config_model.ensure_directories()
        self.configApplied.emit()
        if save:
            self.config_model.save()

    def _apply_ai_config_from_ui(self) -> None:
        self.config_model.ai_provider = self.ai_provider_var.get()
        self.config_model.claude_model = self.claude_model_var.get().strip()
        self.config_model.ai_effort = self.ai_effort_var.get()
        self.config_model.enable_cloud_ai = bool(self.cloud_ai_var.get())
        self.config_model.enable_live_scoring = bool(self.live_scoring_var.get())
        self.config_model.enable_adaptive_probing = bool(self.adaptive_probing_var.get())
        self.config_model.auto_speak_probe = bool(self.auto_speak_probe_var.get())
        try:
            self.config_model.max_probe_depth = int(self.probe_depth_var.get())
        except (TypeError, ValueError):
            pass
        self.config_model.target_role = self.target_role_var.get().strip()
        self.config_model.target_seniority = self.seniority_var.get()
        self.config_model.job_description = self.job_description_var.get().strip()
        self.config_model.resume_summary = self.resume_summary_var.get().strip()
        # normalize_ai_settings clamps the depth and drops a cloud provider the
        # user has not consented to, so the UI can never persist a bad combo.
        self.config_model.normalize_ai_settings()
        self.ai_provider_var.set(self.config_model.ai_provider)
        self.probe_depth_var.set(str(self.config_model.max_probe_depth))

    # -- analysis ------------------------------------------------------------

    def ai_settings(self) -> AISettings:
        return AISettings.from_config(self.config_model, credentials.anthropic_api_key())

    def ai_chain(self) -> ProviderChain:
        """Build the provider chain for one analysis call.

        Rebuilt per call rather than cached: the user can change the engine or
        drop in an API key between two questions.
        """
        return build_chain(self.ai_settings())

    def ai_effort(self) -> str:
        return self.config_model.ai_effort

    def selected_model_installed(self) -> bool:
        return is_model_installed(self.config_model.model_root, self.model_var.get()) and is_model_installed(
            self.config_model.model_root, TOKENIZER_MODEL_ID
        )

    # -- diagnostics --------------------------------------------------------

    def run_startup_diagnostics(self) -> None:
        self.apply_config_from_ui(save=False)
        run_bg(
            self,
            lambda: collect_runtime_diagnostics(self.config_model),
            on_done=self._on_runtime_diagnostics,
            name="startup-diagnostics",
        )

    def _on_runtime_diagnostics(self, report) -> None:
        self.runtime_report = report
        self.diagnostic_status_var.set(report.summary())
        if report.has_failures:
            self.runtime_badge_var.set(tr("badge.warning"))
            self.warning_var.set(tr("app.runtime_issues_warning"))
            self.status_var.set(tr("app.runtime_issues_status"))
        else:
            self.runtime_badge_var.set(tr("badge.ready"))
            self.warning_var.set(tr("app.runtime_ok"))

    # -- language -----------------------------------------------------------

    def set_ui_language(self, language: str) -> None:
        if language not in SUPPORTED_UI_LANGUAGES or language == get_language():
            return
        set_language(language)
        self.ui_language_var.set(language)
        self.config_model.ui_language = language
        self.config_model.save()
        self.languageRebuildRequested.emit()

    # -- TTS preload ----------------------------------------------------------

    def preload_tts_model(self) -> None:
        if self.preload_running:
            return
        self.apply_config_from_ui()
        if self.config_model.tts_backend != QWEN_BACKEND:
            return

        self.preload_running = True
        self.set_state(SessionState.PRELOADING)
        self.runtime_badge_var.set(tr("badge.preloading"))
        self.warning_var.set(tr("app.preload_first_run"))
        self.status_var.set(tr("app.preloading"))
        cache_dir = default_tts_cache_dir()
        provider = QwenTTSProvider(self.config_model, cache_dir)
        self.preload_provider = provider

        run_bg(
            self,
            provider.preload,
            on_done=lambda _result: self._on_preload_done(),
            on_error=self._on_preload_error,
            name="tts-preload",
        )

    def _on_preload_done(self) -> None:
        self.preload_running = False
        self.set_state(SessionState.READY)
        cpu_mode = self.preload_provider is not None and self.preload_provider.is_cpu_runtime
        self.runtime_badge_var.set(tr("badge.ready_cpu") if cpu_mode else tr("badge.ready"))
        if self.engine is None:
            if self.config_model.supports_style_instruction():
                self.status_var.set(tr("app.preload_done_17_status"))
                self.warning_var.set(tr("app.preload_done_17_warning"))
            else:
                self.status_var.set(tr("app.preload_done_06_status"))
                self.warning_var.set(tr("app.preload_done_06_warning"))
            if cpu_mode:
                self.warning_var.set(tr("app.cpu_mode"))

    def _on_preload_error(self, exc: Exception) -> None:
        from ai_interviewer.ui.dialogs import messages

        self.preload_running = False
        self.set_state(SessionState.ERROR)
        self.runtime_badge_var.set(tr("badge.error"))
        self.warning_var.set(tr("app.preload_failed_warning"))
        if self.engine is None:
            self.status_var.set(tr("app.preload_failed_status"))
            if not self.selected_model_installed():
                if messages.ask_yes_no(
                    self.window,
                    tr("app.preload_title"),
                    tr("app.model_missing_ask", error=exc),
                ):
                    if self.window is not None:
                        self.window.open_model_download(self.model_var.get())
                return
            messages.warning(self.window, tr("app.preload_title"), str(exc))

    # -- timers -----------------------------------------------------------------

    def _update_timers(self) -> None:
        if self.engine is not None:
            self.total_timer_var.set(format_seconds(self.engine.session.elapsed_seconds()))
            record = self.engine.current_record
            if record.answer_started_at and not record.answer_finished_at and record._answer_start_monotonic is not None:
                self.answer_timer_var.set(format_seconds(time.monotonic() - record._answer_start_monotonic))
            elif record.answer_seconds is not None:
                self.answer_timer_var.set(format_seconds(record.answer_seconds))
            else:
                self.answer_timer_var.set("00:00")
        self.timersTicked.emit()

    # -- shutdown -----------------------------------------------------------------

    def shutdown(self) -> None:
        """Port of the Tk _on_close teardown (minus widget-local saves,
        which MainWindow.closeEvent handles before calling this)."""
        try:
            self.apply_config_from_ui()
        except Exception:
            logger.exception("Could not persist the configuration on close.")
        if self.recording:
            try:
                self.recorder.stop()
            except Exception:
                logger.exception("Could not stop the recorder on close.")
            self.recording = False
        if self.engine is not None:
            self.engine.finish_current_answer()
        self.set_state(SessionState.IDLE)


def format_seconds(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
