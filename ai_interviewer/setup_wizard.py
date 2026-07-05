from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ai_interviewer import __version__
from ai_interviewer.app_state import SessionState
from ai_interviewer.config import QWEN_BACKEND, TOKENIZER_MODEL_ID, is_model_installed
from ai_interviewer.default_questions import (
    default_questions_text,
    interview_type_label,
    interview_type_options,
    question_set_for_interview_type,
)
from ai_interviewer.model_download_dialog import ModelDownloadDialog
from ai_interviewer.model_downloader import approx_download_bytes, format_bytes
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import (
    InterviewSetupState,
    default_speaker_for_language,
    model_option_by_id,
    speaker_by_id,
    speaker_label,
    speaker_options,
    tts_model_options,
)
from ai_interviewer.ui_components import (
    SignalCanvas,
    section_header,
    selectable_tile,
    set_text_content,
    step_rail,
)


class SetupWizardMixin:
    """Setup wizard construction and flow, mixed into InterviewApp."""


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
