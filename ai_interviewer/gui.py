from __future__ import annotations

import csv
import logging
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_interviewer import __version__
from ai_interviewer.app_state import SessionState
from ai_interviewer.setup_wizard import SetupWizardMixin
from ai_interviewer.workspace import WorkspaceMixin
from ai_interviewer.config import (
    AppConfig,
    DEFAULT_MODEL_ID,
    LARGE_MODEL_ID,
    QWEN_BACKEND,
    SUPPORTED_TTS_BACKENDS,
    TOKENIZER_MODEL_ID,
    is_model_installed,
)
from ai_interviewer.default_questions import (
    INTERVIEW_TYPE_HR,
    default_questions_text,
    interview_type_label,
    interview_type_options,
    question_set_for_interview_type,
)
from ai_interviewer.default_questions import default_question_set_name, question_set_names
from ai_interviewer.diagnostics import collect_runtime_diagnostics, diagnostics_text
from ai_interviewer.engine import InterviewEngine
from ai_interviewer.error_dialog import show_crash_dialog
from ai_interviewer.followup import generate_follow_up_question
from ai_interviewer.model_download_dialog import ModelDownloadDialog
from ai_interviewer.model_downloader import approx_download_bytes, format_bytes
from ai_interviewer.question_parser import detect_language, parse_questions
from ai_interviewer.stt import (
    MicrophoneRecorder,
    STTError,
    WhisperTranscriber,
    input_device_id_from_label,
    list_input_devices,
)
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import (
    InterviewSetupState,
    default_speaker_for_language,
    model_option_by_id,
    speaker_by_id,
    speaker_ids,
    speaker_label,
    speaker_options,
    tts_model_options,
)
from ai_interviewer.ui_components import (
    SignalCanvas,
    card,
    metric_tile,
    section_header,
    selectable_tile,
    set_text_content,
    status_row,
    step_rail,
)
from ai_interviewer.ui_theme import LIGHT_THEME, apply_ttk_styles
from ai_interviewer.video_player import InterviewerVideoPlayer


logger = logging.getLogger(__name__)


class InterviewApp(SetupWizardMixin, WorkspaceMixin, tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Interviewer")
        self.geometry("1280x860")
        self.minsize(1180, 760)

        self.config_model = AppConfig.load()
        self.config_model.ensure_directories()
        if self.config_model.model_id not in {DEFAULT_MODEL_ID, LARGE_MODEL_ID}:
            self.config_model.model_id = DEFAULT_MODEL_ID
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
        self.setup_content: ttk.Frame | None = None
        self.workspace_built = False
        self.setup_state: InterviewSetupState | None = None
        self.setup_custom_questions = ""

        self._build_variables()
        self._build_ui()
        self.after(100, self._run_startup_diagnostics)
        self.after(250, self._update_timers)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_state(self, state: SessionState) -> None:
        self.session_state = state

    def report_callback_exception(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        logger.critical("Unhandled exception in Tk callback", exc_info=(exc_type, exc, tb))
        show_crash_dialog(exc_type, exc, tb)

    def _configure_styles(self) -> None:
        self.ui_theme = LIGHT_THEME
        self.using_ttkbootstrap = apply_ttk_styles(self, self.ui_theme)
        self.configure(bg=self.ui_theme.app_bg)

    def _build_variables(self) -> None:
        interview_language = self.config_model.interview_language
        if interview_language not in {"Korean", "English"}:
            interview_language = "Korean"
        question_set_name = self.config_model.question_set_name
        if question_set_name not in question_set_names(interview_language):
            question_set_name = default_question_set_name(interview_language)

        self.interview_language_var = tk.StringVar(value=interview_language)
        self.question_set_var = tk.StringVar(value=question_set_name)
        self.tts_backend_var = tk.StringVar(value=self.config_model.tts_backend)
        self.model_var = tk.StringVar(value=self.config_model.model_id)
        self.model_root_var = tk.StringVar(value=str(self.config_model.model_root))
        self.video_path_var = tk.StringVar(value=str(self.config_model.video_path))
        self.stt_model_var = tk.StringVar(value=self.config_model.stt_model_size)
        self.stt_device_var = tk.StringVar(value=self.config_model.stt_device)
        self.stt_compute_var = tk.StringVar(value=self.config_model.stt_compute_type)
        self.input_device_var = tk.StringVar(value=self.config_model.input_device)
        self.followup_provider_var = tk.StringVar(value=self.config_model.followup_provider)
        self.ollama_model_var = tk.StringVar(value=self.config_model.ollama_model)
        self.ollama_host_var = tk.StringVar(value=self.config_model.ollama_host)
        self.allow_fallback_var = tk.BooleanVar(value=self.config_model.enable_windows_sapi_fallback)
        tts_language = self.config_model.default_language
        if tts_language == "Auto":
            tts_language = interview_language
        self.language_var = tk.StringVar(value=tts_language)
        selected_speaker = self.config_model.selected_speaker or default_speaker_for_language(interview_language).speaker_id
        self.selected_speaker_var = tk.StringVar(value=selected_speaker)
        self.korean_speaker_var = tk.StringVar(value=self.config_model.korean_speaker or "Sohee")
        self.english_speaker_var = tk.StringVar(value=self.config_model.english_speaker or "Ryan")
        self.interview_type_var = tk.StringVar(value=self.config_model.interview_type or INTERVIEW_TYPE_HR)
        self.question_source_var = tk.StringVar(value="default")
        self.sound_test_status_var = tk.StringVar(value="사운드 테스트 전")
        self.enable_stt_var = tk.BooleanVar(value=self.config_model.enable_stt)
        self.sound_test_required_var = tk.BooleanVar(value=self.config_model.sound_test_required)
        self.status_var = tk.StringVar(value="질문을 입력하거나 파일을 불러오세요.")
        self.diagnostic_status_var = tk.StringVar(value="런타임 진단 대기")
        self.runtime_badge_var = tk.StringVar(value="Runtime: Checking")
        self.question_summary_var = tk.StringVar(value="20 questions loaded")
        self.warning_var = tk.StringVar(value="Qwen3-TTS/STT 런타임을 백그라운드에서 점검합니다.")
        self.progress_var = tk.StringVar(value="0 / 0")
        self.answer_timer_var = tk.StringVar(value="00:00")
        self.total_timer_var = tk.StringVar(value="00:00")
        self.current_question_var = tk.StringVar(value="세션이 시작되지 않았습니다.")

    def _build_ui(self) -> None:
        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.app_root = ttk.Frame(self, padding=(18, 16), style="App.TFrame")
        self.app_root.grid(row=0, column=0, sticky="nsew")
        self.app_root.columnconfigure(0, weight=1)
        self.app_root.rowconfigure(0, weight=1)
        self._show_setup_wizard()

    def _clear_app_root(self) -> None:
        for child in self.app_root.winfo_children():
            child.destroy()

    def _run_startup_diagnostics(self) -> None:
        self._apply_config_from_ui(save=False)

        def worker() -> None:
            report = collect_runtime_diagnostics(self.config_model)
            self.after(0, lambda: self._on_runtime_diagnostics(report))

        threading.Thread(target=worker, daemon=True).start()

    def _on_runtime_diagnostics(self, report) -> None:
        self.runtime_report = report
        self.diagnostic_status_var.set(report.summary_ko())
        if report.has_failures:
            self.runtime_badge_var.set("Runtime: Warning")
            self.warning_var.set("필수 런타임 문제가 있습니다. Diagnostics에서 원인을 확인하세요.")
            self.status_var.set("필수 런타임 문제가 있습니다. 런타임 진단을 확인하세요.")
        else:
            self.runtime_badge_var.set("Runtime: Ready")
            self.warning_var.set("Qwen3-TTS/STT/영상 런타임 사전 점검이 통과했습니다.")

    def _apply_config_from_ui(self, save: bool = True) -> None:
        self.config_model.interview_language = self.interview_language_var.get()
        self.config_model.question_set_name = self.question_set_var.get()
        self.config_model.model_id = self.model_var.get()
        self.config_model.tts_backend = self.tts_backend_var.get()
        self.config_model.model_root = Path(self.model_root_var.get()).expanduser()
        self.config_model.video_path = Path(self.video_path_var.get()).expanduser()
        self.config_model.default_language = self.language_var.get()
        selected_speaker = self.selected_speaker_var.get().strip() or default_speaker_for_language(self.interview_language_var.get()).speaker_id
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
        self.config_model.ui_theme = self.ui_theme.name
        self.config_model.ensure_directories()
        if hasattr(self, "video_player"):
            self.video_player.set_video_path(self.config_model.video_path)
        if save:
            self.config_model.save()

    def _preload_tts_model(self) -> None:
        if self.preload_running:
            return
        self._apply_config_from_ui()
        if self.config_model.tts_backend != QWEN_BACKEND:
            return

        self.preload_running = True
        self._set_state(SessionState.PRELOADING)
        self.runtime_badge_var.set("Runtime: Preloading")
        self.warning_var.set("첫 실행은 모델 로딩 때문에 시간이 걸릴 수 있습니다.")
        self.status_var.set("Qwen3-TTS 모델을 미리 로딩 중입니다...")
        cache_dir = self.config_model.sessions_root / "_preload"
        provider = QwenTTSProvider(self.config_model, cache_dir)
        self.preload_provider = provider

        def worker() -> None:
            try:
                provider.preload()
            except Exception as exc:
                self.after(0, lambda: self._on_preload_error(exc))
                return
            self.after(0, self._on_preload_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_preload_done(self) -> None:
        self.preload_running = False
        self._set_state(SessionState.READY)
        cpu_mode = self.preload_provider is not None and self.preload_provider.is_cpu_runtime
        self.runtime_badge_var.set("Runtime: Ready (CPU)" if cpu_mode else "Runtime: Ready")
        if self.engine is None:
            if self.config_model.supports_style_instruction():
                self.status_var.set("Qwen3-TTS 모델 준비 완료. 면접관 말투 지시가 적용됩니다.")
                self.warning_var.set("Qwen3-TTS 1.7B 말투 지시가 적용되는 상태입니다.")
            else:
                self.status_var.set("Qwen3-TTS 0.6B 준비 완료. 말투 지시는 1.7B 모델에서 적용됩니다.")
                self.warning_var.set("0.6B 모델은 말투 지시 적용이 제한됩니다. 1.7B 모델을 권장합니다.")
            if cpu_mode:
                self.warning_var.set("CPU 모드로 실행 중입니다. 음성 생성이 느릴 수 있습니다.")

    def _on_preload_error(self, exc: Exception) -> None:
        self.preload_running = False
        self._set_state(SessionState.ERROR)
        self.runtime_badge_var.set("Runtime: Error")
        self.warning_var.set("Qwen3-TTS 모델 로딩 실패. Windows fallback은 명시적으로 켠 경우에만 사용됩니다.")
        if self.engine is None:
            self.status_var.set("Qwen3-TTS 모델 로딩 실패. 런타임 진단을 확인하세요.")
            if not self._selected_model_installed():
                if messagebox.askyesno(
                    "Qwen3-TTS preload",
                    f"{exc}\n\nQwen 모델이 설치되어 있지 않습니다. 지금 다운로드할까요?",
                ):
                    self._open_model_download(self.model_var.get())
                return
            messagebox.showwarning("Qwen3-TTS preload", str(exc))

    def _update_timers(self) -> None:
        if self.engine is not None:
            self.total_timer_var.set(_format_seconds(self.engine.session.elapsed_seconds()))
            record = self.engine.current_record
            if record.answer_started_at and not record.answer_finished_at and record._answer_start_monotonic is not None:
                self.answer_timer_var.set(_format_seconds(time.monotonic() - record._answer_start_monotonic))
            elif record.answer_seconds is not None:
                self.answer_timer_var.set(_format_seconds(record.answer_seconds))
            else:
                self.answer_timer_var.set("00:00")
        self.after(250, self._update_timers)

    def _on_close(self) -> None:
        try:
            self._apply_config_from_ui()
        except Exception:
            pass
        if self.recording:
            try:
                self.recorder.stop()
            except Exception:
                pass
            self.recording = False
        self.video_player.stop()
        if self.engine is not None:
            self._save_current_memo()
            self.engine.finish_current_answer()
        self._set_state(SessionState.IDLE)
        self.destroy()


def _format_seconds(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def run_app() -> int:
    app = InterviewApp()
    app.mainloop()
    return 0
