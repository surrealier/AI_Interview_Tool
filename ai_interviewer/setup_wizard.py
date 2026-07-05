from __future__ import annotations

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
from ai_interviewer.i18n import SUPPORTED_UI_LANGUAGES, tr, ui_language_label
from ai_interviewer.model_download_dialog import ModelDownloadDialog
from ai_interviewer.model_downloader import approx_download_bytes, format_bytes
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.tasks import run_bg
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import (
    InterviewSetupState,
    default_speaker_for_language,
    model_option_by_id,
    native_language_label,
    speaker_by_id,
    speaker_description,
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
        ttk.Label(rail, text=tr("wizard.rail_version", version=__version__), style="RailAccent.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            rail,
            text=tr("wizard.rail_tagline"),
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
        self.setup_back_button = ttk.Button(nav, text=tr("common.back"), command=self._setup_back, style="Tool.TButton")
        self.setup_next_button = ttk.Button(nav, text=tr("common.next"), command=self._setup_next, style="Primary.TButton")
        self.setup_back_button.grid(row=0, column=0, sticky="w")
        self.setup_next_button.grid(row=0, column=2, sticky="e")
        self.bind("<Return>", lambda _event: self._setup_next())
        self._render_setup_step(animated=False)

    @property
    def _setup_steps(self) -> tuple[str, ...]:
        return ("language", "model", "speaker", "type", "questions", "sound", "preferences", "review")

    @property
    def _setup_step_labels(self) -> tuple[str, ...]:
        return (
            tr("wizard.step.language"),
            tr("wizard.step.model"),
            tr("wizard.step.speaker"),
            tr("wizard.step.interview"),
            tr("wizard.step.questions"),
            tr("wizard.step.sound"),
            tr("wizard.step.options"),
            tr("wizard.step.review"),
        )

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
            text=tr("wizard.step_prefix", number=f"{self.setup_step_index + 1:02d}"),
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
        self.setup_next_button.configure(text=tr("wizard.start_interview") if step == "review" else tr("common.next"))
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
        section_header(parent, tr("wizard.language_title"), tr("wizard.language_sub")).grid(row=0, column=0, sticky="ew")
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        choices.columnconfigure(0, weight=1)
        choices.columnconfigure(1, weight=1)
        self._choice_button(choices, "한국어", tr("wizard.lang_ko_desc"), 0, 0, self.interview_language_var, "Korean")
        self._choice_button(choices, "English", tr("wizard.lang_en_desc"), 0, 1, self.interview_language_var, "English")

        ui_row = ttk.Frame(parent, style="Surface.TFrame")
        ui_row.grid(row=2, column=0, sticky="ew", pady=(22, 0))
        ttk.Label(ui_row, text=tr("wizard.ui_language_title"), style="Section.TLabel").pack(side="left")
        for language in SUPPORTED_UI_LANGUAGES:
            ttk.Radiobutton(
                ui_row,
                text=ui_language_label(language),
                value=language,
                variable=self.ui_language_var,
                command=lambda lang=language: self._set_ui_language(lang),
            ).pack(side="left", padx=(14, 0))

    def _build_setup_model(self, parent: tk.Widget) -> None:
        section_header(parent, tr("wizard.model_title"), tr("wizard.model_sub")).grid(
            row=0, column=0, sticky="ew"
        )
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        choices.columnconfigure(0, weight=1)
        choices.columnconfigure(1, weight=1)
        for index, option in enumerate(tts_model_options(self.config_model)):
            if option.installed:
                installed = tr("wizard.model_installed")
            else:
                size = approx_download_bytes(self.config_model.model_root, option.model_id)
                installed = tr("wizard.model_not_installed", size=format_bytes(size))
            tone = tr("wizard.tone_on") if option.supports_tone_control else tr("wizard.tone_limited")
            suffix = tr("wizard.recommended_suffix") if option.recommended else ""
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
                text=tr("wizard.model_download_hint"),
                style="Muted.TLabel",
            ).pack(side="left")
            ttk.Button(
                download_row,
                text=tr("wizard.download_now"),
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
            self.status_var.set(tr("wizard.model_download_done"))
            if on_complete is not None:
                on_complete()

        ModelDownloadDialog(self, self.config_model, model_id, on_complete=completed)

    def _build_setup_speaker(self, parent: tk.Widget) -> None:
        section_header(parent, tr("wizard.speaker_title"), tr("wizard.speaker_sub")).grid(
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
                title += tr("wizard.recommended_suffix")
            self._choice_button(
                choices,
                title,
                f"{native_language_label(speaker)}\n{speaker_description(speaker)}",
                row,
                column,
                self.selected_speaker_var,
                speaker.speaker_id,
            )

    def _build_setup_type(self, parent: tk.Widget) -> None:
        section_header(parent, tr("wizard.type_title"), tr("wizard.type_sub")).grid(row=0, column=0, sticky="ew")
        choices = ttk.Frame(parent, style="Surface.TFrame")
        choices.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        for column in range(2):
            choices.columnconfigure(column, weight=1)
        descriptions = {
            "hr": tr("wizard.type_desc_hr"),
            "star": tr("wizard.type_desc_star"),
            "role": tr("wizard.type_desc_role"),
            "technical": tr("wizard.type_desc_technical"),
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
        section_header(parent, tr("wizard.questions_title"), tr("wizard.questions_sub")).grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, style="Surface.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        top = ttk.Frame(body, style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        ttk.Radiobutton(
            top,
            text=tr("wizard.use_default_questions"),
            value="default",
            variable=self.question_source_var,
            command=self._on_question_source_changed,
        ).pack(side="left")
        ttk.Radiobutton(
            top,
            text=tr("wizard.paste_questions"),
            value="custom",
            variable=self.question_source_var,
            command=self._on_question_source_changed,
        ).pack(side="left", padx=(18, 0))
        selected_set = question_set_for_interview_type(self.interview_language_var.get(), self.interview_type_var.get())
        ttk.Label(body, text=tr("wizard.default_pack", set_name=selected_set), style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 8))
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
        section_header(parent, tr("wizard.sound_title"), tr("wizard.sound_sub")).grid(row=0, column=0, sticky="ew")
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
        ttk.Button(body, text=tr("wizard.run_sound_test"), command=self._run_setup_sound_test, style="Primary.TButton").grid(
            row=3, column=0, sticky="w", pady=(18, 0)
        )
        ttk.Checkbutton(body, text=tr("wizard.sound_keep_reminder"), variable=self.sound_test_required_var).grid(
            row=4, column=0, sticky="w", pady=(16, 0)
        )

    def _build_setup_preferences(self, parent: tk.Widget) -> None:
        section_header(parent, tr("wizard.pref_title"), tr("wizard.pref_sub")).grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, style="Surface.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(1, weight=1)
        ttk.Checkbutton(body, text=tr("wizard.pref_stt"), variable=self.enable_stt_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(body, text=tr("wizard.pref_fallback"), variable=self.allow_fallback_var).grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Label(body, text=tr("wizard.pref_followup"), style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(18, 0))
        ttk.Combobox(body, textvariable=self.followup_provider_var, values=("Auto", "Ollama", "Rules"), state="readonly").grid(
            row=2, column=1, sticky="ew", padx=(10, 0), pady=(18, 0)
        )

    def _build_setup_review(self, parent: tk.Widget) -> None:
        section_header(parent, tr("wizard.review_title"), tr("wizard.review_sub")).grid(row=0, column=0, sticky="ew")
        body = ttk.Frame(parent, padding=16, style="SubtleCard.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(1, weight=1)
        selected_set = question_set_for_interview_type(self.interview_language_var.get(), self.interview_type_var.get())
        rows = (
            (tr("wizard.step.language"), self.interview_language_var.get()),
            (tr("wizard.step.model"), model_option_by_id(self.config_model, self.model_var.get()).display_name),
            (tr("wizard.step.speaker"), speaker_label(speaker_by_id(self.selected_speaker_var.get()))),
            (tr("wizard.step.interview"), interview_type_label(self.interview_language_var.get(), self.interview_type_var.get())),
            (tr("wizard.step.questions"), tr("wizard.custom_questions") if self.question_source_var.get() == "custom" else selected_set),
            (tr("wizard.step.sound"), self.sound_test_status_var.get()),
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
                tr("wizard.model_missing_title"),
                tr("wizard.model_missing_body"),
            ):
                self._open_model_download(self.model_var.get())
            return False
        if step == "questions":
            self._apply_setup_questions()
            questions = parse_questions(self._setup_questions_content())
            if not questions:
                messagebox.showwarning(tr("wizard.no_questions_title"), tr("wizard.no_questions_body"))
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
        self.sound_test_passed = False
        self.sound_test_status_var.set(tr("wizard.sound_testing"))
        self.runtime_badge_var.set(tr("badge.sound_test"))
        provider = QwenTTSProvider(self.config_model, self.config_model.sessions_root / "_setup_sound_test")
        self.preload_provider = provider

        run_bg(
            self,
            lambda: provider.sound_test(language, speaker),
            on_done=self._on_setup_sound_test_done,
            on_error=self._on_setup_sound_test_error,
            name="setup-sound-test",
        )

    def _on_setup_sound_test_done(self, result) -> None:
        self.sound_test_passed = True
        self.sound_test_status_var.set(tr("wizard.sound_done", backend=result.backend, speaker=result.speaker))
        self.runtime_badge_var.set(tr("badge.ready"))

    def _on_setup_sound_test_error(self, exc: Exception) -> None:
        self.sound_test_passed = False
        self.sound_test_status_var.set(tr("wizard.sound_failed", error=exc))
        self.runtime_badge_var.set(tr("badge.warning"))
        messagebox.showerror(tr("wizard.sound_failed_title"), str(exc))

    def _begin_interview_from_setup(self) -> None:
        self._apply_setup_questions()
        self._apply_config_from_ui(save=True)
        if self.sound_test_required_var.get() and not self.sound_test_passed:
            if not messagebox.askyesno(tr("wizard.sound_not_done_title"), tr("wizard.sound_not_done_ask")):
                return
        self.config_model.setup_completed = True
        self.config_model.save()
        self._show_interview_workspace()
        if hasattr(self, "question_text"):
            self._replace_question_text(self._setup_questions_content())
        self._start_session()
