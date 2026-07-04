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


class InterviewApp(tk.Tk):
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

    def _show_interview_workspace(self) -> None:
        self._clear_app_root()
        self.workspace_built = True
        self.app_root.rowconfigure(0, weight=0)
        self.app_root.rowconfigure(1, weight=1)
        self.app_root.columnconfigure(0, weight=1)
        self._build_header(self.app_root)

        main = ttk.Frame(self.app_root, style="App.TFrame")
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=4, minsize=330)
        main.columnconfigure(1, weight=6, minsize=460)
        main.columnconfigure(2, weight=4, minsize=330)
        main.rowconfigure(0, weight=1)

        question_column = ttk.Frame(main, padding=(0, 0, 12, 0), style="App.TFrame")
        room_column = ttk.Frame(main, padding=(0, 0, 12, 0), style="App.TFrame")
        side_column = ttk.Frame(main, style="App.TFrame")
        question_column.grid(row=0, column=0, sticky="nsew")
        room_column.grid(row=0, column=1, sticky="nsew")
        side_column.grid(row=0, column=2, sticky="nsew")

        self._build_question_studio(question_column)
        self._build_interview_room(room_column)
        self._build_side_panel(side_column)
        self._set_session_controls(False)
        self._refresh_question_summary()

    def _show_setup_wizard(self) -> None:
        self._clear_app_root()
        self.workspace_built = False
        self.app_root.rowconfigure(0, weight=1)
        wizard = ttk.Frame(self.app_root, padding=(28, 24), style="Hero.TFrame")
        wizard.grid(row=0, column=0, sticky="nsew")
        wizard.columnconfigure(0, weight=0, minsize=290)
        wizard.columnconfigure(1, weight=1)
        wizard.rowconfigure(0, weight=1)

        rail = ttk.Frame(wizard, padding=(0, 2, 26, 0), style="Rail.TFrame")
        rail.grid(row=0, column=0, sticky="nsew")
        rail.columnconfigure(0, weight=1)
        rail.rowconfigure(3, weight=1)
        ttk.Label(rail, text="AI Interviewer", style="HeroTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(rail, text=f"beta {__version__} · Interview Studio", style="RailAccent.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            rail,
            text="언어, 모델, 목소리, 질문팩을 차례대로 정하고 바로 실전 모드로 들어갑니다.",
            style="RailMuted.TLabel",
            wraplength=250,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(16, 18))
        self.setup_signal = SignalCanvas(rail, theme=self.ui_theme, height=150, animated=True)
        self.setup_signal.grid(row=3, column=0, sticky="ew", pady=(0, 18))
        self.setup_rail_holder = ttk.Frame(rail, style="Rail.TFrame")
        self.setup_rail_holder.grid(row=4, column=0, sticky="nsew")

        stage = ttk.Frame(wizard, padding=(34, 30), style="Surface.TFrame")
        stage.grid(row=0, column=1, sticky="nsew")
        stage.columnconfigure(0, weight=1)
        stage.rowconfigure(1, weight=1)

        top = ttk.Frame(stage, style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        ttk.Label(top, textvariable=self.runtime_badge_var, style="Kicker.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.diagnostic_status_var, style="Muted.TLabel").grid(row=0, column=1, sticky="e")

        self.setup_content = ttk.Frame(stage, style="Surface.TFrame")
        self.setup_content.grid(row=1, column=0, sticky="nsew", pady=(20, 0))
        self.setup_content.columnconfigure(0, weight=1)
        self.setup_content.rowconfigure(1, weight=1)

        nav = ttk.Frame(stage, style="Surface.TFrame")
        nav.grid(row=2, column=0, sticky="ew", pady=(22, 0))
        nav.columnconfigure(1, weight=1)
        self.setup_back_button = ttk.Button(nav, text="Back", command=self._setup_back, style="Tool.TButton")
        self.setup_next_button = ttk.Button(nav, text="Next", command=self._setup_next, style="Primary.TButton")
        self.setup_back_button.grid(row=0, column=0, sticky="w")
        self.setup_next_button.grid(row=0, column=2, sticky="e")
        self.bind("<Return>", lambda _event: self._setup_next())
        self._render_setup_step(animated=False)

    @property
    def _setup_steps(self) -> tuple[str, ...]:
        return ("language", "model", "speaker", "type", "questions", "sound", "preferences", "review")

    @property
    def _setup_step_labels(self) -> tuple[str, ...]:
        return ("Language", "Model", "Speaker", "Interview", "Questions", "Sound", "Options", "Review")

    def _render_setup_step(self, animated: bool = True) -> None:
        if self.setup_content is None:
            return
        for child in self.setup_content.winfo_children():
            child.destroy()
        if hasattr(self, "setup_rail_holder"):
            for child in self.setup_rail_holder.winfo_children():
                child.destroy()
            step_rail(self.setup_rail_holder, self._setup_step_labels, self.setup_step_index, self.ui_theme)

        progress = ttk.Frame(self.setup_content, style="Surface.TFrame")
        progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            progress,
            text=f"STEP {self.setup_step_index + 1:02d}",
            style="Kicker.TLabel",
        ).pack(side="left")
        ttk.Label(progress, text=self._setup_step_labels[self.setup_step_index], style="Muted.TLabel").pack(side="left", padx=(10, 0))
        ttk.Label(progress, text=f"{self.setup_step_index + 1} / {len(self._setup_steps)}", style="Muted.TLabel").pack(side="right")

        body = ttk.Frame(self.setup_content, style="Surface.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        step = self._setup_steps[self.setup_step_index]
        getattr(self, f"_build_setup_{step}")(body)
        self.setup_back_button.configure(state="disabled" if self.setup_step_index == 0 else "normal")
        self.setup_next_button.configure(text="Start Interview" if step == "review" else "Next")
        if animated:
            self._animate_step_in(body)

    def _animate_step_in(self, widget: tk.Widget) -> None:
        for delay, pad in enumerate((24, 16, 10, 5, 0)):
            widget.after(delay * 35, lambda value=pad: widget.grid_configure(padx=(value, 0)))

    def _setup_back(self) -> None:
        if self.setup_step_index > 0:
            self.setup_step_index -= 1
            self._render_setup_step()

    def _setup_next(self) -> None:
        if not self._validate_setup_step():
            return
        if self.setup_step_index >= len(self._setup_steps) - 1:
            self._begin_interview_from_setup()
            return
        self.setup_step_index += 1
        self._render_setup_step()

    def _select_and_continue(self, variable: tk.Variable, value: str) -> None:
        variable.set(value)
        if variable is self.interview_language_var:
            self._sync_language_selection()
        if variable is self.model_var:
            self.provider = None
            self.preload_provider = None
        if variable is self.interview_type_var:
            self.question_set_var.set(question_set_for_interview_type(self.interview_language_var.get(), value))
        self.after(80, self._setup_next)

    def _build_setup_language(self, parent: tk.Widget) -> None:
        section_header(parent, "면접 언어를 선택하세요", "질문팩, TTS 언어, 추천 speaker가 함께 바뀝니다.").grid(row=0, column=0, sticky="ew")
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        choices.columnconfigure(0, weight=1)
        choices.columnconfigure(1, weight=1)
        self._choice_button(choices, "한국어", "한국어 질문팩과 Sohee voice를 기본으로 사용합니다.", 0, 0, self.interview_language_var, "Korean")
        self._choice_button(choices, "English", "Use English question packs with Ryan voice by default.", 0, 1, self.interview_language_var, "English")

    def _build_setup_model(self, parent: tk.Widget) -> None:
        section_header(parent, "TTS 모델을 선택하세요", "모델은 여기서 선택만 하고, 사운드 테스트 또는 면접 시작 때 처음 로드합니다.").grid(
            row=0, column=0, sticky="ew"
        )
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        choices.columnconfigure(0, weight=1)
        choices.columnconfigure(1, weight=1)
        for index, option in enumerate(tts_model_options(self.config_model)):
            if option.installed:
                installed = "설치됨"
            else:
                size = approx_download_bytes(self.config_model.model_root, option.model_id)
                installed = f"미설치 · 다운로드 필요 (~{format_bytes(size)})"
            tone = "Tone control ON" if option.supports_tone_control else "Tone control limited"
            suffix = " · Recommended" if option.recommended else ""
            self._choice_button(
                choices,
                f"{option.display_name}{suffix}",
                f"{installed}\n{tone}\n{option.description}",
                0,
                index,
                self.model_var,
                option.model_id,
            )
        if not self._selected_model_installed():
            download_row = ttk.Frame(parent, style="Surface.TFrame")
            download_row.grid(row=2, column=0, sticky="ew", pady=(14, 0))
            ttk.Label(
                download_row,
                text="선택한 모델이 설치되어 있지 않습니다. 다음 단계로 가기 전에 다운로드하세요.",
                style="Muted.TLabel",
            ).pack(side="left")
            ttk.Button(
                download_row,
                text="지금 다운로드",
                command=lambda: self._open_model_download(self.model_var.get()),
            ).pack(side="right")

    def _selected_model_installed(self) -> bool:
        return is_model_installed(self.config_model.model_root, self.model_var.get()) and is_model_installed(
            self.config_model.model_root, TOKENIZER_MODEL_ID
        )

    def _open_model_download(self, model_id: str, on_complete=None) -> None:
        def completed() -> None:
            self.provider = None
            self.preload_provider = None
            if self.setup_content is not None and self._setup_steps[self.setup_step_index] == "model":
                self._render_setup_step(animated=False)
            self.status_var.set("모델 다운로드가 완료되었습니다.")
            if on_complete is not None:
                on_complete()

        ModelDownloadDialog(self, self.config_model, model_id, on_complete=completed)

    def _build_setup_speaker(self, parent: tk.Widget) -> None:
        section_header(parent, "면접관 voice를 선택하세요", "지원 speaker를 직접 고르는 방식입니다. native language와 설명을 함께 표시합니다.").grid(
            row=0, column=0, sticky="ew"
        )
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        for column in range(3):
            choices.columnconfigure(column, weight=1)
        for index, speaker in enumerate(speaker_options(self.interview_language_var.get())):
            row, column = divmod(index, 3)
            title = speaker.display_name
            if self.interview_language_var.get() in speaker.recommended_languages:
                title += " · Recommended"
            self._choice_button(
                choices,
                title,
                f"{speaker.native_language}\n{speaker.description}",
                row,
                column,
                self.selected_speaker_var,
                speaker.speaker_id,
            )

    def _build_setup_type(self, parent: tk.Widget) -> None:
        section_header(parent, "어떤 면접을 연습할까요?", "선택한 유형에 맞는 기본 질문팩을 준비합니다.").grid(row=0, column=0, sticky="ew")
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        for column in range(2):
            choices.columnconfigure(column, weight=1)
        descriptions = {
            "hr": "자기소개, 지원동기, 강점/약점 등 기본 인성 면접입니다.",
            "star": "경험을 상황-행동-결과 중심으로 깊게 묻습니다.",
            "role": "직무 이해도와 회사/업무 적합성을 확인합니다.",
            "technical": "프로젝트, 설계, 테스트, 장애 대응 등 기술 역량을 봅니다.",
        }
        for index, (interview_type, label) in enumerate(interview_type_options(self.interview_language_var.get())):
            row, column = divmod(index, 2)
            self._choice_button(
                choices,
                label,
                descriptions.get(interview_type, ""),
                row,
                column,
                self.interview_type_var,
                interview_type,
            )

    def _build_setup_questions(self, parent: tk.Widget) -> None:
        section_header(parent, "질문 리스트가 있나요?", "없으면 선택한 유형의 기본 20문항으로 시작합니다.").grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, style="Surface.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        top = ttk.Frame(body, style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        ttk.Radiobutton(
            top,
            text="기본 질문 사용",
            value="default",
            variable=self.question_source_var,
            command=self._on_question_source_changed,
        ).pack(side="left")
        ttk.Radiobutton(
            top,
            text="내 질문 붙여넣기",
            value="custom",
            variable=self.question_source_var,
            command=self._on_question_source_changed,
        ).pack(side="left", padx=(18, 0))
        selected_set = question_set_for_interview_type(self.interview_language_var.get(), self.interview_type_var.get())
        ttk.Label(body, text=f"Default pack: {selected_set}", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 8))
        if self.question_source_var.get() == "custom":
            self.setup_questions_text = self._make_text_widget(body, height=12)
            self.setup_questions_text.grid(row=2, column=0, sticky="nsew")
            if self.setup_custom_questions:
                set_text_content(self.setup_questions_text, self.setup_custom_questions)
            elif hasattr(self, "question_text"):
                content = self.question_text.get("1.0", "end").strip()
                if content:
                    set_text_content(self.setup_questions_text, content)
        else:
            preview = tk.Text(
                body,
                height=12,
                wrap="word",
                bg=self.ui_theme.surface_deep,
                fg=self.ui_theme.muted,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=self.ui_theme.border,
                highlightcolor=self.ui_theme.primary,
                padx=10,
                pady=8,
                font=(self.ui_theme.font, 10),
            )
            preview.grid(row=2, column=0, sticky="nsew")
            preview.insert("1.0", default_questions_text(self.interview_language_var.get(), selected_set))
            preview.configure(state="disabled")

    def _on_question_source_changed(self) -> None:
        if hasattr(self, "setup_questions_text"):
            self.setup_custom_questions = self.setup_questions_text.get("1.0", "end").strip()
        self._render_setup_step()

    def _build_setup_sound(self, parent: tk.Widget) -> None:
        section_header(parent, "사운드 테스트를 할까요?", "이 버튼을 누르는 순간에만 Qwen 모델 로드가 시작됩니다.").grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, style="Surface.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(0, weight=1)
        model = model_option_by_id(self.config_model, self.model_var.get())
        speaker = speaker_by_id(self.selected_speaker_var.get())
        signal = SignalCanvas(body, theme=self.ui_theme, height=118, animated=False, compact=True)
        signal.grid(row=0, column=0, sticky="ew")
        summary = ttk.Frame(body, padding=(14, 12), style="SubtleCard.TFrame")
        summary.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        summary.columnconfigure(1, weight=1)
        ttk.Label(summary, text="MODEL", style="MetricLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(summary, text=model.display_name, style="Status.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0))
        ttk.Label(summary, text="SPEAKER", style="MetricLabel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(summary, text=speaker_label(speaker), style="Status.TLabel", wraplength=620).grid(
            row=1, column=1, sticky="ew", padx=(14, 0), pady=(8, 0)
        )
        ttk.Label(body, textvariable=self.sound_test_status_var, style="Warning.TLabel", wraplength=720).grid(
            row=2, column=0, sticky="w", pady=(16, 0)
        )
        ttk.Button(body, text="Run Sound Test", command=self._run_setup_sound_test, style="Primary.TButton").grid(
            row=3, column=0, sticky="w", pady=(18, 0)
        )
        ttk.Checkbutton(body, text="면접 시작 전 사운드 테스트를 권장 알림으로 유지", variable=self.sound_test_required_var).grid(
            row=4, column=0, sticky="w", pady=(16, 0)
        )

    def _build_setup_preferences(self, parent: tk.Widget) -> None:
        section_header(parent, "진행 방식을 선택하세요", "면접 화면에서도 다시 바꿀 수 있습니다.").grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, style="Surface.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(1, weight=1)
        ttk.Checkbutton(body, text="답변 녹음/STT 사용", variable=self.enable_stt_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(body, text="Qwen 실패 시 Windows 기본 음성 fallback 허용", variable=self.allow_fallback_var).grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Label(body, text="꼬리질문 provider", style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(18, 0))
        ttk.Combobox(body, textvariable=self.followup_provider_var, values=("Auto", "Ollama", "Rules"), state="readonly").grid(
            row=2, column=1, sticky="ew", padx=(10, 0), pady=(18, 0)
        )

    def _build_setup_review(self, parent: tk.Widget) -> None:
        section_header(parent, "설정이 완료되었습니다", "요약을 확인하고 면접을 시작하세요.").grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, padding=16, style="SubtleCard.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(1, weight=1)
        selected_set = question_set_for_interview_type(self.interview_language_var.get(), self.interview_type_var.get())
        rows = (
            ("Language", self.interview_language_var.get()),
            ("Model", model_option_by_id(self.config_model, self.model_var.get()).display_name),
            ("Speaker", speaker_label(speaker_by_id(self.selected_speaker_var.get()))),
            ("Interview", interview_type_label(self.interview_language_var.get(), self.interview_type_var.get())),
            ("Questions", "Custom pasted questions" if self.question_source_var.get() == "custom" else selected_set),
            ("Sound", self.sound_test_status_var.get()),
            ("STT", "ON" if self.enable_stt_var.get() else "OFF"),
            ("Fallback", "ON" if self.allow_fallback_var.get() else "OFF"),
        )
        for row, (label, value) in enumerate(rows):
            ttk.Label(body, text=label, style="MetricLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 8, 0))
            ttk.Label(body, text=value, style="Status.TLabel", wraplength=740, justify="left").grid(
                row=row, column=1, sticky="ew", padx=(14, 0), pady=(0 if row == 0 else 8, 0)
            )

    def _choice_button(
        self,
        parent: tk.Widget,
        title: str,
        description: str,
        row: int,
        column: int,
        variable: tk.Variable,
        value: str,
    ) -> None:
        selected = variable.get() == value
        selectable_tile(
            parent,
            title=title,
            description=description,
            selected=selected,
            command=lambda: self._select_and_continue(variable, value),
            theme=self.ui_theme,
            row=row,
            column=column,
        )

    def _validate_setup_step(self) -> bool:
        step = self._setup_steps[self.setup_step_index]
        if step == "model" and self.tts_backend_var.get() == QWEN_BACKEND and not self._selected_model_installed():
            if messagebox.askyesno(
                "모델 미설치",
                "선택한 TTS 모델이 아직 설치되어 있지 않습니다.\n지금 다운로드할까요?",
            ):
                self._open_model_download(self.model_var.get())
            return False
        if step == "questions":
            self._apply_setup_questions()
            questions = parse_questions(self._setup_questions_content())
            if not questions:
                messagebox.showwarning("질문 없음", "질문을 한 개 이상 입력하세요.")
                return False
        return True

    def _setup_questions_content(self) -> str:
        if self.question_source_var.get() == "custom" and hasattr(self, "setup_questions_text"):
            self.setup_custom_questions = self.setup_questions_text.get("1.0", "end").strip()
            return self.setup_custom_questions
        if self.question_source_var.get() == "custom":
            return self.setup_custom_questions
        selected_set = question_set_for_interview_type(self.interview_language_var.get(), self.interview_type_var.get())
        return default_questions_text(self.interview_language_var.get(), selected_set)

    def _apply_setup_questions(self) -> None:
        content = self._setup_questions_content()
        if hasattr(self, "question_text"):
            set_text_content(self.question_text, content)
            self._refresh_question_summary()

    def _sync_language_selection(self) -> None:
        language = self.interview_language_var.get()
        self.language_var.set(language)
        speaker = default_speaker_for_language(language)
        self.selected_speaker_var.set(speaker.speaker_id)
        if language == "Korean":
            self.korean_speaker_var.set(speaker.speaker_id)
        else:
            self.english_speaker_var.set(speaker.speaker_id)
        selected_set = question_set_for_interview_type(language, self.interview_type_var.get())
        self.question_set_var.set(selected_set)

    def _run_setup_sound_test(self) -> None:
        self._apply_config_from_ui(save=False)
        language = self.interview_language_var.get()
        speaker = self.selected_speaker_var.get()
        self.sound_test_status_var.set("Qwen3-TTS 모델을 로드하고 테스트 음성을 생성 중입니다...")
        self.runtime_badge_var.set("Runtime: Sound test")
        provider = QwenTTSProvider(self.config_model, self.config_model.sessions_root / "_setup_sound_test")
        self.preload_provider = provider

        def worker() -> None:
            try:
                result = provider.sound_test(language, speaker)
            except Exception as exc:
                self.after(0, lambda: self._on_setup_sound_test_error(exc))
                return
            self.after(0, lambda: self._on_setup_sound_test_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_setup_sound_test_done(self, result) -> None:
        self.sound_test_status_var.set(f"테스트 완료: {result.backend}, speaker={result.speaker}")
        self.runtime_badge_var.set("Runtime: Ready")

    def _on_setup_sound_test_error(self, exc: Exception) -> None:
        self.sound_test_status_var.set(f"테스트 실패: {exc}")
        self.runtime_badge_var.set("Runtime: Warning")
        messagebox.showerror("사운드 테스트 실패", str(exc))

    def _begin_interview_from_setup(self) -> None:
        self._apply_setup_questions()
        self._apply_config_from_ui(save=True)
        if self.sound_test_required_var.get() and not self.sound_test_status_var.get().startswith("테스트 완료"):
            if not messagebox.askyesno("사운드 테스트 미완료", "사운드 테스트를 아직 완료하지 않았습니다. 그래도 면접을 시작할까요?"):
                return
        self.config_model.setup_completed = True
        self.config_model.save()
        self._show_interview_workspace()
        if hasattr(self, "question_text"):
            self._replace_question_text(self._setup_questions_content())
        self._start_session()

    def _build_header(self, parent: tk.Widget) -> None:
        header = card(parent, padding=(18, 14), style="Hero.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)

        title_area = ttk.Frame(header, style="Stage.TFrame")
        title_area.grid(row=0, column=0, sticky="w")
        ttk.Label(title_area, text="AI Interviewer", style="HeroTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_area,
            text=f"Interview Studio beta {__version__}",
            style="HeroSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        status = ttk.Frame(header, padding=(12, 8), style="SubtleCard.TFrame")
        status.grid(row=0, column=1, sticky="ew", padx=18)
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.runtime_badge_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.status_var, style="Subtitle.TLabel", wraplength=430).grid(
            row=1, column=0, sticky="ew", pady=(2, 0)
        )
        ttk.Label(status, textvariable=self.diagnostic_status_var, style="Muted.TLabel", wraplength=430).grid(
            row=2, column=0, sticky="ew", pady=(2, 0)
        )

        actions = ttk.Frame(header, style="Stage.TFrame")
        actions.grid(row=0, column=2, sticky="e")
        ttk.Label(actions, text="Interview mode", style="RailAccent.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self.korean_mode_button = ttk.Radiobutton(
            actions,
            text="한국어",
            value="Korean",
            variable=self.interview_language_var,
            command=self._on_language_mode_changed,
        )
        self.english_mode_button = ttk.Radiobutton(
            actions,
            text="English",
            value="English",
            variable=self.interview_language_var,
            command=self._on_language_mode_changed,
        )
        self.korean_mode_button.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.english_mode_button.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(4, 0))
        self.start_button = ttk.Button(actions, text="Start Interview", command=self._start_session, style="Primary.TButton")
        self.start_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _build_question_studio(self, parent: tk.Widget) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        studio = card(parent, padding=16)
        studio.grid(row=0, column=0, sticky="nsew")
        studio.columnconfigure(0, weight=1)
        studio.rowconfigure(3, weight=1)

        section_header(
            studio,
            "Question Studio",
            "Pick a curated pack or paste your own questions. Number prefixes are cleaned before TTS.",
        ).grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Label(studio, text="Question pack", style="Section.TLabel").grid(row=1, column=0, sticky="w", pady=(14, 0))
        self.question_set_combo = ttk.Combobox(
            studio,
            textvariable=self.question_set_var,
            values=question_set_names(self.interview_language_var.get()),
            state="readonly",
        )
        self.question_set_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=(14, 0))
        self.question_set_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_selected_question_set())
        pack_buttons = ttk.Frame(studio, style="Surface.TFrame")
        pack_buttons.grid(row=1, column=2, sticky="e", pady=(14, 0))
        ttk.Button(pack_buttons, text="Load", command=self._apply_selected_question_set, style="Tool.TButton").pack(side="left")
        ttk.Button(pack_buttons, text="File", command=self._load_questions_file, style="Tool.TButton").pack(side="left", padx=(6, 0))

        summary = ttk.Frame(studio, padding=(10, 8), style="SubtleCard.TFrame")
        summary.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 10))
        summary.columnconfigure(1, weight=1)
        ttk.Label(summary, textvariable=self.question_summary_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            summary,
            text="Separate Korean/English packs stay isolated by mode.",
            style="Subtitle.TLabel",
        ).grid(row=0, column=1, sticky="e")

        editor_frame = ttk.Frame(studio, style="Surface.TFrame")
        editor_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        self.question_text = self._make_text_widget(editor_frame, height=18, font_size=10)
        self.question_text.grid(row=0, column=0, sticky="nsew")
        text_scroll = ttk.Scrollbar(editor_frame, orient="vertical", command=self.question_text.yview)
        text_scroll.grid(row=0, column=1, sticky="ns")
        self.question_text.configure(yscrollcommand=text_scroll.set)
        set_text_content(self.question_text, default_questions_text(self.interview_language_var.get(), self.question_set_var.get()))
        self.question_text.bind("<<Modified>>", self._on_question_text_modified)

    def _build_interview_room(self, parent: tk.Widget) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        room = card(parent, padding=16)
        room.grid(row=0, column=0, sticky="nsew")
        room.columnconfigure(0, weight=1)
        room.rowconfigure(1, weight=0)

        section_header(
            room,
            "Interview Room",
            "Live interviewer stage, question playback, answer timing, and follow-up generation.",
        ).grid(row=0, column=0, sticky="ew")

        video_shell = ttk.Frame(room, padding=10, style="Stage.TFrame")
        video_shell.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        video_shell.columnconfigure(0, weight=1)
        self.video_player = InterviewerVideoPlayer(video_shell, width=520, height=292)
        self.video_player.widget.grid(row=0, column=0, sticky="ew")
        self.video_player.set_video_path(self.config_model.video_path)
        room_signal = SignalCanvas(video_shell, theme=self.ui_theme, height=58, animated=True, compact=True)
        room_signal.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        metrics = ttk.Frame(room, style="Surface.TFrame")
        metrics.grid(row=2, column=0, sticky="ew")
        for index in range(3):
            metrics.columnconfigure(index, weight=1)
        self._metric(metrics, "Progress", self.progress_var, 0)
        self._metric(metrics, "Answer", self.answer_timer_var, 1)
        self._metric(metrics, "Total", self.total_timer_var, 2)

        question_box = ttk.Frame(room, padding=16, style="ChoiceSelected.TFrame")
        question_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        question_box.columnconfigure(0, weight=1)
        ttk.Label(question_box, text="CURRENT QUESTION", style="QuestionPanelLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            question_box,
            textvariable=self.current_question_var,
            wraplength=470,
            justify="left",
            style="QuestionPanel.TLabel",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self._build_session_controls(room)

    def _build_session_controls(self, parent: tk.Widget) -> None:
        controls = ttk.Frame(parent, style="Surface.TFrame")
        controls.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        for index in range(4):
            controls.columnconfigure(index, weight=1)

        self.prev_button = ttk.Button(controls, text="Previous", command=self._previous_question, style="Tool.TButton")
        self.next_button = ttk.Button(controls, text="Next", command=self._next_question, style="Secondary.TButton")
        self.repeat_button = ttk.Button(controls, text="Replay", command=lambda: self._speak_current(repeat=True), style="Tool.TButton")
        self.stop_button = ttk.Button(controls, text="Stop TTS", command=self._stop_tts, style="Tool.TButton")
        self.record_button = ttk.Button(controls, text="Record", command=self._start_recording, style="Secondary.TButton")
        self.stop_record_button = ttk.Button(controls, text="Stop + STT", command=self._stop_recording_and_transcribe, style="Tool.TButton")
        self.followup_button = ttk.Button(controls, text="Follow-up", command=self._generate_follow_up, style="Secondary.TButton")
        self.followup_speak_button = ttk.Button(controls, text="Read Follow-up", command=self._speak_follow_up, style="Tool.TButton")
        self.restart_button = ttk.Button(controls, text="Restart", command=self._restart_session, style="Tool.TButton")
        self.open_folder_button = ttk.Button(controls, text="Session Folder", command=self._open_session_folder, style="Tool.TButton")
        self.sound_test_button = ttk.Button(controls, text="Sound Test", command=self._test_system_sound, style="Tool.TButton")
        self.diagnostics_button = ttk.Button(controls, text="Diagnostics", command=self._diagnose_tts, style="Tool.TButton")

        buttons = (
            self.prev_button,
            self.next_button,
            self.repeat_button,
            self.stop_button,
            self.record_button,
            self.stop_record_button,
            self.followup_button,
            self.followup_speak_button,
            self.restart_button,
            self.open_folder_button,
            self.sound_test_button,
            self.diagnostics_button,
        )
        for index, button in enumerate(buttons):
            row, column = divmod(index, 4)
            button.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(0 if row == 0 else 7, 0))

    def _build_side_panel(self, parent: tk.Widget) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        runtime = card(parent, padding=14)
        runtime.grid(row=0, column=0, sticky="ew")
        runtime.columnconfigure(1, weight=1)
        section_header(runtime, "Runtime Watch", "Warnings stay visible before and during the session.").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12)
        )
        status_row(runtime, "State", self.runtime_badge_var, 1)
        status_row(runtime, "Diagnostics", self.diagnostic_status_var, 2)
        status_row(runtime, "Notice", self.warning_var, 3, style="Warning.TLabel")

        settings = card(parent, padding=14)
        settings.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        settings.columnconfigure(0, weight=1)
        section_header(settings, "Runtime Settings", "Voice, recording, AI, and media paths.").grid(row=0, column=0, sticky="ew")
        self._build_settings_tabs(settings)

        workspace = card(parent, padding=14)
        workspace.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        section_header(workspace, "Answer Workspace", "Write notes, review STT, and edit follow-up questions.").grid(
            row=0, column=0, sticky="ew", pady=(0, 10)
        )
        detail_tabs = ttk.Notebook(workspace)
        detail_tabs.grid(row=1, column=0, sticky="nsew")

        memo_box = ttk.Frame(detail_tabs, padding=8, style="Surface.TFrame")
        transcript_box = ttk.Frame(detail_tabs, padding=8, style="Surface.TFrame")
        followup_box = ttk.Frame(detail_tabs, padding=8, style="Surface.TFrame")
        for box in (memo_box, transcript_box, followup_box):
            box.columnconfigure(0, weight=1)
            box.rowconfigure(0, weight=1)
        self.memo_text = self._make_text_widget(memo_box, height=7)
        self.memo_text.grid(row=0, column=0, sticky="nsew")
        self.transcript_text = self._make_text_widget(transcript_box, height=7)
        self.transcript_text.grid(row=0, column=0, sticky="nsew")
        self.followup_text = self._make_text_widget(followup_box, height=7)
        self.followup_text.grid(row=0, column=0, sticky="nsew")
        detail_tabs.add(memo_box, text="Memo")
        detail_tabs.add(transcript_box, text="Answer STT")
        detail_tabs.add(followup_box, text="Follow-up")

    def _build_settings_tabs(self, parent: tk.Widget) -> None:
        settings_tabs = ttk.Notebook(parent)
        settings_tabs.grid(row=1, column=0, sticky="ew", pady=(12, 0))

        voice_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        audio_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        ai_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        media_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        for tab in (voice_tab, audio_tab, ai_tab, media_tab):
            tab.columnconfigure(1, weight=1)

        settings_tabs.add(voice_tab, text="Voice")
        settings_tabs.add(audio_tab, text="STT")
        settings_tabs.add(ai_tab, text="AI")
        settings_tabs.add(media_tab, text="Media")

        self._setting_label(voice_tab, "TTS engine", 0)
        ttk.Combobox(voice_tab, textvariable=self.tts_backend_var, values=SUPPORTED_TTS_BACKENDS, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Checkbutton(voice_tab, text="Windows fallback", variable=self.allow_fallback_var).grid(row=0, column=2, sticky="w")
        self._setting_label(voice_tab, "Model", 1)
        ttk.Combobox(voice_tab, textvariable=self.model_var, values=(DEFAULT_MODEL_ID, LARGE_MODEL_ID), state="readonly").grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0)
        )
        self._setting_label(voice_tab, "Language", 2)
        ttk.Combobox(voice_tab, textvariable=self.language_var, values=("Auto", "Korean", "English"), state="readonly", width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        self._setting_label(voice_tab, "Speaker", 3)
        self.speaker_combo = ttk.Combobox(
            voice_tab,
            textvariable=self.selected_speaker_var,
            values=speaker_ids(self.interview_language_var.get()),
            state="readonly",
        )
        self.speaker_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

        self._setting_label(audio_tab, "STT model", 0)
        ttk.Combobox(audio_tab, textvariable=self.stt_model_var, values=("tiny", "base", "small", "medium", "large-v3"), state="readonly", width=12).grid(
            row=0, column=1, sticky="w", padx=8
        )
        self._setting_label(audio_tab, "Input", 1)
        self.input_device_combo = ttk.Combobox(audio_tab, textvariable=self.input_device_var, values=self._input_device_labels(), state="readonly")
        self.input_device_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(audio_tab, text="Refresh", command=self._refresh_input_devices, style="Tool.TButton").grid(row=1, column=2, pady=(8, 0))
        self._setting_label(audio_tab, "Device / compute", 2)
        ttk.Combobox(audio_tab, textvariable=self.stt_device_var, values=("auto", "cuda", "cpu"), state="readonly", width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        ttk.Combobox(audio_tab, textvariable=self.stt_compute_var, values=("auto", "float16", "int8", "int8_float16", "float32"), state="readonly", width=12).grid(
            row=2, column=2, sticky="w", pady=(8, 0)
        )

        self._setting_label(ai_tab, "Follow-up", 0)
        ttk.Combobox(ai_tab, textvariable=self.followup_provider_var, values=("Auto", "Ollama", "Rules"), state="readonly", width=12).grid(
            row=0, column=1, sticky="w", padx=8
        )
        self._setting_label(ai_tab, "Ollama model", 1)
        ttk.Entry(ai_tab, textvariable=self.ollama_model_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        self._setting_label(ai_tab, "Ollama host", 2)
        ttk.Entry(ai_tab, textvariable=self.ollama_host_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

        self._setting_label(media_tab, "Model folder", 0)
        ttk.Entry(media_tab, textvariable=self.model_root_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(media_tab, text="Browse", command=self._choose_model_root, style="Tool.TButton").grid(row=0, column=2)
        ttk.Button(
            media_tab,
            text="모델 다운로드",
            command=lambda: self._open_model_download(self.model_var.get()),
            style="Tool.TButton",
        ).grid(row=0, column=3, padx=(8, 0))
        self._setting_label(media_tab, "Video file", 1)
        ttk.Entry(media_tab, textvariable=self.video_path_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(media_tab, text="Browse", command=self._choose_video_file, style="Tool.TButton").grid(row=1, column=2, pady=(8, 0))

    def _setting_label(self, parent: tk.Widget, text: str, row: int) -> None:
        ttk.Label(parent, text=text, style="Section.TLabel").grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 8, 0))

    def _make_text_widget(self, parent: tk.Widget, height: int, font_size: int = 10) -> tk.Text:
        return tk.Text(
            parent,
            wrap="word",
            undo=True,
            height=height,
            bg=self.ui_theme.surface_deep,
            fg=self.ui_theme.ink,
            insertbackground=self.ui_theme.accent,
            selectbackground=self.ui_theme.selection,
            selectforeground=self.ui_theme.ink,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.ui_theme.border,
            highlightcolor=self.ui_theme.primary,
            padx=12,
            pady=10,
            font=(self.ui_theme.font, font_size),
        )

    def _set_session_controls(self, enabled: bool) -> None:
        if not hasattr(self, "prev_button"):
            return
        state = "normal" if enabled else "disabled"
        for button in (
            self.prev_button,
            self.next_button,
            self.repeat_button,
            self.stop_button,
            self.restart_button,
            self.open_folder_button,
            self.record_button,
            self.followup_button,
            self.followup_speak_button,
        ):
            button.configure(state=state)
        if not self.enable_stt_var.get():
            self.record_button.configure(state="disabled")
            self.stop_record_button.configure(state="disabled")
            return
        self.stop_record_button.configure(state="normal" if self.recording else "disabled")
        self.sound_test_button.configure(state="normal")
        self.diagnostics_button.configure(state="normal")

    def _load_questions_file(self) -> None:
        path = filedialog.askopenfilename(
            title="질문 파일 선택",
            filetypes=(("Text or CSV", "*.txt *.csv"), ("All files", "*.*")),
        )
        if not path:
            return
        content = self._read_question_file(Path(path))
        set_text_content(self.question_text, content)
        self._refresh_question_summary()
        self.status_var.set(f"파일을 불러왔습니다: {Path(path).name}")

    def _read_question_file(self, path: Path) -> str:
        if path.suffix.lower() != ".csv":
            return path.read_text(encoding="utf-8-sig")
        rows: list[str] = []
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0].strip():
                    rows.append(row[0].strip())
        return "\n".join(rows)

    def _on_language_mode_changed(self) -> None:
        language = self.interview_language_var.get()
        names = question_set_names(language)
        selected = question_set_for_interview_type(language, self.interview_type_var.get())
        self.question_set_var.set(selected)
        if hasattr(self, "question_set_combo"):
            self.question_set_combo.configure(values=names)
        if hasattr(self, "speaker_combo"):
            self.speaker_combo.configure(values=speaker_ids(language))
        self.selected_speaker_var.set(default_speaker_for_language(language).speaker_id)
        self.language_var.set(language)
        if hasattr(self, "question_text"):
            self._replace_question_text(default_questions_text(language, selected))
        self.status_var.set("한국어 질문셋을 불러왔습니다." if language == "Korean" else "English question set loaded.")

    def _apply_selected_question_set(self) -> None:
        language = self.interview_language_var.get()
        set_name = self.question_set_var.get()
        self.language_var.set(language)
        self._replace_question_text(default_questions_text(language, set_name))
        self.status_var.set(f"질문셋을 불러왔습니다: {set_name}")

    def _replace_question_text(self, content: str) -> None:
        set_text_content(self.question_text, content)
        self._refresh_question_summary()

    def _metric(self, parent: tk.Widget, label: str, variable: tk.StringVar, column: int) -> None:
        metric_tile(parent, label, variable, column)

    def _on_question_text_modified(self, _event: tk.Event) -> None:
        if self.question_text.edit_modified():
            self.question_text.edit_modified(False)
            self._refresh_question_summary()

    def _refresh_question_summary(self) -> None:
        if not hasattr(self, "question_text"):
            return
        questions = parse_questions(self.question_text.get("1.0", "end"))
        mode = self.interview_language_var.get()
        label = "한국어" if mode == "Korean" else "English"
        self.question_summary_var.set(f"{len(questions)} questions loaded · {label} mode")

    def _input_device_labels(self) -> tuple[str, ...]:
        try:
            labels = tuple(device.label for device in list_input_devices())
        except STTError:
            labels = ()
        return ("Default", *labels)

    def _refresh_input_devices(self) -> None:
        labels = self._input_device_labels()
        self.input_device_combo.configure(values=labels)
        if self.input_device_var.get() not in labels:
            self.input_device_var.set("Default")
        self.status_var.set("마이크 장치 목록을 갱신했습니다.")

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

    def _choose_model_root(self) -> None:
        path = filedialog.askdirectory(title="models 폴더 선택", initialdir=self.model_root_var.get())
        if path:
            self.model_root_var.set(path)
            self.config_model.model_root = Path(path).expanduser()
            if self.model_var.get() not in {DEFAULT_MODEL_ID, LARGE_MODEL_ID}:
                self.model_var.set(self.config_model.preferred_model_id())
            self.provider = None
            self._apply_config_from_ui()
            self.status_var.set("모델 폴더를 변경했습니다. 모델은 사운드 테스트 또는 면접 시작 때 로드됩니다.")

    def _choose_video_file(self) -> None:
        path = filedialog.askopenfilename(
            title="면접관 영상 파일 선택",
            filetypes=(("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")),
        )
        if path:
            self.video_path_var.set(path)
            self.config_model.video_path = Path(path).expanduser()
            if hasattr(self, "video_player"):
                self.video_player.set_video_path(self.config_model.video_path)
            self._apply_config_from_ui()

    def _start_session(self) -> None:
        questions = parse_questions(self.question_text.get("1.0", "end"))
        if not questions:
            messagebox.showwarning("질문 없음", "질문을 한 개 이상 입력하세요.")
            return

        self._apply_config_from_ui()
        self.runtime_report = collect_runtime_diagnostics(self.config_model)
        self.diagnostic_status_var.set(self.runtime_report.summary_ko())
        if self.runtime_report.has_failures and not messagebox.askyesno(
            "런타임 경고",
            "필수 런타임 문제가 있습니다. TTS/STT 일부 기능이 실패할 수 있습니다.\n\n계속 시작할까요?",
        ):
            return
        self.engine = InterviewEngine(questions=questions, sessions_root=self.config_model.sessions_root)
        self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        self._set_state(SessionState.READY)
        self.runtime_badge_var.set("Session: Ready")
        self.warning_var.set("질문 재생 후 답변 시간이 자동으로 기록됩니다.")
        self._set_session_controls(True)
        self._render_current_question()
        self.status_var.set("세션을 시작했습니다.")
        self._speak_current(repeat=False)

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

    def _render_current_question(self) -> None:
        if self.engine is None:
            return
        record = self.engine.current_record
        self.progress_var.set(f"{self.engine.current_index + 1} / {self.engine.question_count}")
        self.current_question_var.set(record.clean_question)
        self.memo_text.delete("1.0", "end")
        self.memo_text.insert("1.0", record.memo)
        self.transcript_text.delete("1.0", "end")
        self.transcript_text.insert("1.0", record.transcript)
        self.followup_text.delete("1.0", "end")
        self.followup_text.insert("1.0", record.follow_up_question)
        self.prev_button.configure(state="normal" if self.engine.current_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.engine.current_index < self.engine.question_count - 1 else "disabled")

    def _save_current_memo(self) -> None:
        if self.engine is None:
            return
        self.engine.set_current_memo(self.memo_text.get("1.0", "end"))
        self.engine.session.set_transcript(self.engine.current_index, self.transcript_text.get("1.0", "end"))
        self.engine.session.set_follow_up_question(self.engine.current_index, self.followup_text.get("1.0", "end"))
        self.engine.session.save()

    def _get_provider(self) -> QwenTTSProvider:
        if self.engine is None:
            raise RuntimeError("Session has not started.")
        if self.provider is None:
            self._apply_config_from_ui()
            self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        return self.provider

    def _speak_current(self, repeat: bool) -> None:
        if self.engine is None or self.tts_running:
            return
        self._apply_config_from_ui()
        self._save_current_memo()
        provider = self._get_provider()
        token = self.tts_token + 1
        self.tts_token = token
        self.tts_running = True
        self._set_state(SessionState.SPEAKING)
        self.runtime_badge_var.set("Session: Speaking")
        self.repeat_button.configure(state="disabled")
        self.video_player.start()
        if self.config_model.tts_backend == QWEN_BACKEND:
            self.status_var.set("Qwen3-TTS 생성 및 재생 중...")
            self.after(15000, lambda: self._show_slow_tts_notice(token))
        else:
            self.status_var.set("Windows 기본 음성으로 재생 중...")

        def worker() -> None:
            try:
                result = self.engine.speak_current(provider, repeat=repeat)
            except Exception as exc:
                self.after(0, lambda: self._on_tts_error(token, exc))
                return
            self.after(0, lambda: self._on_tts_done(token, result))

        threading.Thread(target=worker, daemon=True).start()

    def _show_slow_tts_notice(self, token: int) -> None:
        if token == self.tts_token and self.tts_running:
            self.status_var.set("Qwen3-TTS 생성 중입니다. 모델이 아직 준비 중이면 첫 질문은 조금 걸릴 수 있습니다.")

    def _on_tts_done(self, token: int, result) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        if result.warning:
            self.status_var.set(f"Windows 기본 음성 fallback으로 재생했습니다. 오디오: {result.wav_path.name}")
            self.runtime_badge_var.set("Runtime: Fallback")
            self.warning_var.set(result.warning)
            messagebox.showwarning("Qwen3-TTS fallback", result.warning)
        else:
            self.status_var.set(f"답변 시간을 기록 중입니다. backend={result.backend}, 오디오: {result.wav_path.name}")
            self.runtime_badge_var.set("Session: Answering")
            self.warning_var.set("답변 시간 기록 중입니다. 녹음 또는 메모를 남길 수 있습니다.")
        self._set_state(SessionState.ANSWERING)
        self._render_current_question()

    def _on_tts_error(self, token: int, exc: Exception) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self._set_state(SessionState.ERROR)
        self.runtime_badge_var.set("Session: Error")
        self.warning_var.set(str(exc))
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        self.status_var.set("TTS 오류가 발생했습니다.")
        messagebox.showerror("TTS 오류", str(exc))

    def _stop_tts(self) -> None:
        self.tts_token += 1
        self.tts_running = False
        self._set_state(SessionState.ANSWERING if self.engine is not None else SessionState.IDLE)
        self.runtime_badge_var.set("Session: Answering" if self.engine is not None else "Runtime: Ready")
        self.repeat_button.configure(state="normal")
        if self.provider is not None:
            self.provider.stop()
        if hasattr(self, "video_player"):
            self.video_player.stop()
        if self.engine is not None:
            self.engine.session.start_answer(self.engine.current_index)
            self.engine.session.save()
        self.status_var.set("TTS를 중지했습니다. 답변 시간 기록을 계속합니다.")

    def _start_recording(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            return
        self._save_current_memo()
        self.engine.session.start_answer(self.engine.current_index)
        index = self.engine.current_index + 1
        path = self.engine.session.answers_dir / f"answer_{index:03d}.wav"
        try:
            self.recorder.start(path, input_device=input_device_id_from_label(self.input_device_var.get()))
        except STTError as exc:
            messagebox.showerror("녹음 시작 실패", str(exc))
            self._set_state(SessionState.ERROR)
            return

        self.recording = True
        self._set_state(SessionState.RECORDING)
        self.runtime_badge_var.set("Session: Recording")
        self.warning_var.set("답변 음성을 녹음 중입니다. 완료 후 Stop + STT를 누르세요.")
        self.recording_path = path
        self.record_button.configure(state="disabled")
        self.stop_record_button.configure(state="normal")
        self.status_var.set("답변 녹음 중입니다.")
        self.engine.session.set_answer_audio_path(self.engine.current_index, path)
        self.engine.session.save()

    def _stop_recording_and_transcribe(self) -> None:
        if self.engine is None or not self.recording:
            return
        try:
            path = self.recorder.stop()
        except STTError as exc:
            self.recording = False
            self.recording_path = None
            self.record_button.configure(state="normal")
            self.stop_record_button.configure(state="disabled")
            self._set_state(SessionState.ERROR)
            self.runtime_badge_var.set("Session: Error")
            self.warning_var.set(str(exc))
            messagebox.showerror("녹음 중지 실패", str(exc))
            return

        self.recording = False
        self._set_state(SessionState.TRANSCRIBING)
        self.runtime_badge_var.set("Session: STT")
        self.warning_var.set("답변 음성을 전사 중입니다.")
        self.recording_path = path
        self.record_button.configure(state="normal")
        self.stop_record_button.configure(state="disabled")
        self.engine.session.set_answer_audio_path(self.engine.current_index, path)
        self.engine.finish_current_answer()
        self.status_var.set("답변 음성을 STT 변환 중입니다...")
        index = self.engine.current_index
        question = self.engine.current_record.clean_question
        language = detect_language(question)

        def worker() -> None:
            try:
                result = self.transcriber.transcribe(path, language=language)
            except Exception as exc:
                self.after(0, lambda: self._on_transcript_error(exc))
                return
            self.after(0, lambda: self._on_transcript_done(index, result.text))

        threading.Thread(target=worker, daemon=True).start()

    def _on_transcript_done(self, index: int, transcript: str) -> None:
        if self.engine is None:
            return
        self.engine.session.set_transcript(index, transcript)
        self.engine.session.save()
        if index == self.engine.current_index:
            self.transcript_text.delete("1.0", "end")
            self.transcript_text.insert("1.0", transcript)
        self.status_var.set("STT 변환이 완료되었습니다.")
        self.runtime_badge_var.set("Session: Answering")
        self.warning_var.set("전사 결과를 확인하고 꼬리질문을 생성할 수 있습니다.")
        self._set_state(SessionState.ANSWERING)

    def _on_transcript_error(self, exc: Exception) -> None:
        self.status_var.set("STT 변환 실패")
        self._set_state(SessionState.ERROR)
        self.runtime_badge_var.set("Session: Error")
        self.warning_var.set(str(exc))
        messagebox.showerror("STT 오류", str(exc))

    def _generate_follow_up(self) -> None:
        if self.engine is None:
            return
        self._apply_config_from_ui()
        self._save_current_memo()
        record = self.engine.current_record
        transcript = self.transcript_text.get("1.0", "end").strip() or record.memo
        question = record.clean_question
        language = detect_language(question)
        self.status_var.set("꼬리질문 생성 중입니다...")
        self._set_state(SessionState.FOLLOW_UP_GENERATING)
        self.runtime_badge_var.set("Session: Follow-up")
        self.warning_var.set("전사/메모 내용을 기반으로 꼬리질문을 생성합니다.")

        def worker() -> None:
            follow_up = generate_follow_up_question(
                question,
                transcript,
                language,
                provider=self.config_model.followup_provider,
                ollama_model=self.config_model.ollama_model,
                ollama_host=self.config_model.ollama_host,
            )
            self.after(0, lambda: self._on_follow_up_done(follow_up))

        threading.Thread(target=worker, daemon=True).start()

    def _on_follow_up_done(self, follow_up: str) -> None:
        if self.engine is None:
            return
        self.engine.session.set_follow_up_question(self.engine.current_index, follow_up)
        self.engine.session.save()
        self.followup_text.delete("1.0", "end")
        self.followup_text.insert("1.0", follow_up)
        self.status_var.set("꼬리질문이 생성되었습니다.")
        self.runtime_badge_var.set("Session: Answering")
        self.warning_var.set("꼬리질문을 편집하거나 Read Follow-up으로 읽을 수 있습니다.")
        self._set_state(SessionState.ANSWERING)

    def _speak_follow_up(self) -> None:
        if self.engine is None or self.tts_running:
            return
        self._apply_config_from_ui()
        self._save_current_memo()
        follow_up = self.followup_text.get("1.0", "end").strip()
        if not follow_up:
            messagebox.showwarning("꼬리질문 없음", "먼저 꼬리질문을 생성하세요.")
            return

        provider = self._get_provider()
        token = self.tts_token + 1
        self.tts_token = token
        self.tts_running = True
        self._set_state(SessionState.SPEAKING)
        self.repeat_button.configure(state="disabled")
        self.video_player.start()
        self.status_var.set("꼬리질문을 재생 중입니다...")
        session_id = self.engine.session.session_id
        current_index = self.engine.current_index

        def worker() -> None:
            try:
                language, speaker = provider.resolve_voice(follow_up)
                provider.speak(
                    text=follow_up,
                    cache_key=f"{session_id}-{current_index + 1}-followup",
                    language=language,
                    speaker=speaker,
                )
            except Exception as exc:
                self.after(0, lambda: self._on_tts_error(token, exc))
                return
            self.after(0, lambda: self._on_follow_up_tts_done(token))

        threading.Thread(target=worker, daemon=True).start()

    def _on_follow_up_tts_done(self, token: int) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        if hasattr(self, "video_player"):
            self.video_player.stop()
        self.status_var.set("꼬리질문 재생이 끝났습니다.")
        self._set_state(SessionState.ANSWERING)

    def _test_system_sound(self) -> None:
        try:
            provider = self._get_provider() if self.engine is not None else QwenTTSProvider(
                self.config_model,
                self.config_model.sessions_root / "_diagnostics",
            )
            provider.play_system_beep()
            self.status_var.set("Windows 시스템 소리 테스트를 실행했습니다.")
        except Exception as exc:
            messagebox.showerror("소리 테스트 실패", str(exc))

    def _diagnose_tts(self) -> None:
        self._apply_config_from_ui()
        self.runtime_report = collect_runtime_diagnostics(self.config_model)
        self.diagnostic_status_var.set(self.runtime_report.summary_ko())
        if self.tts_backend_var.get() == QWEN_BACKEND and not self._selected_model_installed():
            if messagebox.askyesno(
                "런타임 진단",
                diagnostics_text(self.runtime_report) + "\n\nQwen 모델이 설치되어 있지 않습니다. 지금 다운로드할까요?",
            ):
                self._open_model_download(self.model_var.get())
            return
        messagebox.showinfo("런타임 진단", diagnostics_text(self.runtime_report))

    def _next_question(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning("녹음 중", "녹음을 중지한 뒤 다음 질문으로 이동하세요.")
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.move_next()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _previous_question(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning("녹음 중", "녹음을 중지한 뒤 이전 질문으로 이동하세요.")
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.move_previous()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _restart_session(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning("녹음 중", "녹음을 중지한 뒤 다시 시작하세요.")
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.restart()
        self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        self._render_current_question()
        self.status_var.set("새 세션으로 다시 시작했습니다.")
        self._speak_current(repeat=False)

    def _open_session_folder(self) -> None:
        if self.engine is None:
            return
        self._save_current_memo()
        path = self.engine.session.session_dir
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("저장 폴더", str(path))

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
