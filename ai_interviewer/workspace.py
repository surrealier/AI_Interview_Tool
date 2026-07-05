from __future__ import annotations

import csv
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_interviewer import __version__
from ai_interviewer.app_state import SessionState
from ai_interviewer.config import (
    DEFAULT_MODEL_ID,
    LARGE_MODEL_ID,
    QWEN_BACKEND,
    SUPPORTED_TTS_BACKENDS,
)
from ai_interviewer.default_questions import (
    default_question_set_name,
    default_questions_text,
    interview_type_label,
    question_set_for_interview_type,
    question_set_names,
)
from ai_interviewer.diagnostics import collect_runtime_diagnostics, diagnostics_text
from ai_interviewer.engine import InterviewEngine
from ai_interviewer.followup import generate_follow_up_question
from ai_interviewer.i18n import SUPPORTED_UI_LANGUAGES, tr, ui_language_label
from ai_interviewer.question_parser import detect_language, parse_questions
from ai_interviewer.session_browser import SessionBrowserDialog
from ai_interviewer.stt import STTError, input_device_id_from_label, list_input_devices
from ai_interviewer.tasks import run_bg
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import (
    backend_display_name,
    default_speaker_for_language,
    speaker_by_id,
    speaker_ids,
    speaker_label,
)
from ai_interviewer.ui_components import (
    SignalCanvas,
    card,
    metric_tile,
    section_header,
    selectable_tile,
    set_text_content,
    status_row,
)
from ai_interviewer.video_player import InterviewerVideoPlayer


class WorkspaceMixin:
    """Interview workspace construction and session handlers, mixed into InterviewApp."""


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

    def _build_header(self, parent: tk.Widget) -> None:
        header = card(parent, padding=(18, 14), style="Hero.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)

        title_area = ttk.Frame(header, style="Stage.TFrame")
        title_area.grid(row=0, column=0, sticky="w")
        ttk.Label(title_area, text="AI Interviewer", style="HeroTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_area,
            text=tr("ws.subtitle", version=__version__),
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
        ttk.Label(actions, text=tr("ws.interview_mode"), style="RailAccent.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
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
        self.start_button = ttk.Button(actions, text=tr("ws.start_interview"), command=self._start_session, style="Primary.TButton")
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
            tr("ws.question_studio_title"),
            tr("ws.question_studio_sub"),
        ).grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Label(studio, text=tr("ws.question_pack"), style="Section.TLabel").grid(row=1, column=0, sticky="w", pady=(14, 0))
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
        ttk.Button(pack_buttons, text=tr("common.load"), command=self._apply_selected_question_set, style="Tool.TButton").pack(side="left")
        ttk.Button(pack_buttons, text=tr("common.file"), command=self._load_questions_file, style="Tool.TButton").pack(side="left", padx=(6, 0))

        summary = ttk.Frame(studio, padding=(10, 8), style="SubtleCard.TFrame")
        summary.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 10))
        summary.columnconfigure(1, weight=1)
        ttk.Label(summary, textvariable=self.question_summary_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            summary,
            text=tr("ws.pack_isolated"),
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
            tr("ws.room_title"),
            tr("ws.room_sub"),
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
        self._metric(metrics, tr("ws.metric_progress"), self.progress_var, 0)
        self._metric(metrics, tr("ws.metric_answer"), self.answer_timer_var, 1)
        self._metric(metrics, tr("ws.metric_total"), self.total_timer_var, 2)

        question_box = ttk.Frame(room, padding=16, style="ChoiceSelected.TFrame")
        question_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        question_box.columnconfigure(0, weight=1)
        ttk.Label(question_box, text=tr("ws.current_question"), style="QuestionPanelLabel.TLabel").grid(row=0, column=0, sticky="w")
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

        self.prev_button = ttk.Button(controls, text=tr("ws.btn_prev"), command=self._previous_question, style="Tool.TButton")
        self.next_button = ttk.Button(controls, text=tr("ws.btn_next"), command=self._next_question, style="Secondary.TButton")
        self.repeat_button = ttk.Button(controls, text=tr("ws.btn_replay"), command=lambda: self._speak_current(repeat=True), style="Tool.TButton")
        self.stop_button = ttk.Button(controls, text=tr("ws.btn_stop_tts"), command=self._stop_tts, style="Tool.TButton")
        self.record_button = ttk.Button(controls, text=tr("ws.btn_record"), command=self._start_recording, style="Secondary.TButton")
        self.stop_record_button = ttk.Button(controls, text=tr("ws.btn_stop_stt"), command=self._stop_recording_and_transcribe, style="Tool.TButton")
        self.followup_button = ttk.Button(controls, text=tr("ws.btn_followup"), command=self._generate_follow_up, style="Secondary.TButton")
        self.followup_speak_button = ttk.Button(controls, text=tr("ws.btn_read_followup"), command=self._speak_follow_up, style="Tool.TButton")
        self.restart_button = ttk.Button(controls, text=tr("ws.btn_restart"), command=self._restart_session, style="Tool.TButton")
        self.open_folder_button = ttk.Button(controls, text=tr("ws.btn_session_folder"), command=self._open_session_folder, style="Tool.TButton")
        self.sound_test_button = ttk.Button(controls, text=tr("ws.btn_sound_test"), command=self._test_system_sound, style="Tool.TButton")
        self.diagnostics_button = ttk.Button(controls, text=tr("ws.btn_diagnostics"), command=self._diagnose_tts, style="Tool.TButton")
        self.sessions_button = ttk.Button(controls, text=tr("ws.btn_sessions"), command=self._open_session_browser, style="Tool.TButton")

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
            self.sessions_button,
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
        section_header(runtime, tr("ws.runtime_watch_title"), tr("ws.runtime_watch_sub")).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12)
        )
        status_row(runtime, tr("ws.row_state"), self.runtime_badge_var, 1)
        status_row(runtime, tr("ws.row_diagnostics"), self.diagnostic_status_var, 2)
        status_row(runtime, tr("ws.row_notice"), self.warning_var, 3, style="Warning.TLabel")

        settings = card(parent, padding=14)
        settings.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        settings.columnconfigure(0, weight=1)
        section_header(settings, tr("ws.settings_title"), tr("ws.settings_sub")).grid(row=0, column=0, sticky="ew")
        self._build_settings_tabs(settings)

        workspace = card(parent, padding=14)
        workspace.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        section_header(workspace, tr("ws.workspace_title"), tr("ws.workspace_sub")).grid(
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
        detail_tabs.add(memo_box, text=tr("ws.tab_memo"))
        detail_tabs.add(transcript_box, text=tr("ws.tab_stt"))
        detail_tabs.add(followup_box, text=tr("ws.tab_followup"))

    def _build_settings_tabs(self, parent: tk.Widget) -> None:
        settings_tabs = ttk.Notebook(parent)
        settings_tabs.grid(row=1, column=0, sticky="ew", pady=(12, 0))

        voice_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        audio_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        ai_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        media_tab = ttk.Frame(settings_tabs, padding=10, style="Surface.TFrame")
        for tab in (voice_tab, audio_tab, ai_tab, media_tab):
            tab.columnconfigure(1, weight=1)

        settings_tabs.add(voice_tab, text=tr("ws.tab_voice"))
        settings_tabs.add(audio_tab, text=tr("ws.tab_stt_settings"))
        settings_tabs.add(ai_tab, text=tr("ws.tab_ai"))
        settings_tabs.add(media_tab, text=tr("ws.tab_media"))

        self._setting_label(voice_tab, tr("ws.set_tts_engine"), 0)
        self.backend_combo = ttk.Combobox(
            voice_tab,
            values=[backend_display_name(backend) for backend in SUPPORTED_TTS_BACKENDS],
            state="readonly",
        )
        self.backend_combo.set(backend_display_name(self.tts_backend_var.get()))
        self.backend_combo.bind("<<ComboboxSelected>>", self._on_backend_selected)
        self.backend_combo.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Checkbutton(voice_tab, text=tr("ws.windows_fallback"), variable=self.allow_fallback_var).grid(row=0, column=2, sticky="w")
        self._setting_label(voice_tab, tr("ws.set_model"), 1)
        ttk.Combobox(voice_tab, textvariable=self.model_var, values=(DEFAULT_MODEL_ID, LARGE_MODEL_ID), state="readonly").grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0)
        )
        self._setting_label(voice_tab, tr("ws.set_language"), 2)
        ttk.Combobox(voice_tab, textvariable=self.language_var, values=("Auto", "Korean", "English"), state="readonly", width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        self._setting_label(voice_tab, tr("ws.set_speaker"), 3)
        self.speaker_combo = ttk.Combobox(
            voice_tab,
            textvariable=self.selected_speaker_var,
            values=speaker_ids(self.interview_language_var.get()),
            state="readonly",
        )
        self.speaker_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

        self._setting_label(audio_tab, tr("ws.set_stt_model"), 0)
        ttk.Combobox(audio_tab, textvariable=self.stt_model_var, values=("tiny", "base", "small", "medium", "large-v3"), state="readonly", width=12).grid(
            row=0, column=1, sticky="w", padx=8
        )
        self._setting_label(audio_tab, tr("ws.set_input"), 1)
        self.input_device_combo = ttk.Combobox(audio_tab, textvariable=self.input_device_var, values=self._input_device_labels(), state="readonly")
        self.input_device_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(audio_tab, text=tr("ws.refresh"), command=self._refresh_input_devices, style="Tool.TButton").grid(row=1, column=2, pady=(8, 0))
        self._setting_label(audio_tab, tr("ws.set_device_compute"), 2)
        ttk.Combobox(audio_tab, textvariable=self.stt_device_var, values=("auto", "cuda", "cpu"), state="readonly", width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        ttk.Combobox(audio_tab, textvariable=self.stt_compute_var, values=("auto", "float16", "int8", "int8_float16", "float32"), state="readonly", width=12).grid(
            row=2, column=2, sticky="w", pady=(8, 0)
        )

        self._setting_label(ai_tab, tr("ws.set_followup"), 0)
        ttk.Combobox(ai_tab, textvariable=self.followup_provider_var, values=("Auto", "Ollama", "Rules"), state="readonly", width=12).grid(
            row=0, column=1, sticky="w", padx=8
        )
        self._setting_label(ai_tab, tr("ws.set_ollama_model"), 1)
        ttk.Entry(ai_tab, textvariable=self.ollama_model_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        self._setting_label(ai_tab, tr("ws.set_ollama_host"), 2)
        ttk.Entry(ai_tab, textvariable=self.ollama_host_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

        self._setting_label(media_tab, tr("ws.set_model_folder"), 0)
        ttk.Entry(media_tab, textvariable=self.model_root_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(media_tab, text=tr("common.browse"), command=self._choose_model_root, style="Tool.TButton").grid(row=0, column=2)
        ttk.Button(
            media_tab,
            text=tr("ws.model_download"),
            command=lambda: self._open_model_download(self.model_var.get()),
            style="Tool.TButton",
        ).grid(row=0, column=3, padx=(8, 0))
        self._setting_label(media_tab, tr("ws.set_ui_language"), 2)
        ui_lang_row = ttk.Frame(media_tab, style="Surface.TFrame")
        ui_lang_row.grid(row=2, column=1, columnspan=2, sticky="w", padx=8, pady=(8, 0))
        for language in SUPPORTED_UI_LANGUAGES:
            ttk.Radiobutton(
                ui_lang_row,
                text=ui_language_label(language),
                value=language,
                variable=self.ui_language_var,
                command=lambda lang=language: self._set_ui_language(lang),
            ).pack(side="left", padx=(0, 12))
        self._setting_label(media_tab, tr("ws.set_video_file"), 1)
        ttk.Entry(media_tab, textvariable=self.video_path_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(media_tab, text=tr("common.browse"), command=self._choose_video_file, style="Tool.TButton").grid(row=1, column=2, pady=(8, 0))

    def _setting_label(self, parent: tk.Widget, text: str, row: int) -> None:
        ttk.Label(parent, text=text, style="Section.TLabel").grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 8, 0))

    def _on_backend_selected(self, _event=None) -> None:
        display = self.backend_combo.get()
        for backend in SUPPORTED_TTS_BACKENDS:
            if backend_display_name(backend) == display:
                self.tts_backend_var.set(backend)
                break

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
            title=tr("ws.file_dialog_title"),
            filetypes=(("Text or CSV", "*.txt *.csv"), ("All files", "*.*")),
        )
        if not path:
            return
        content = self._read_question_file(Path(path))
        set_text_content(self.question_text, content)
        self._refresh_question_summary()
        self.status_var.set(tr("ws.file_loaded", name=Path(path).name))

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
        self.status_var.set(tr("ws.question_set_loaded_ko") if language == "Korean" else tr("ws.question_set_loaded_en"))

    def _apply_selected_question_set(self) -> None:
        language = self.interview_language_var.get()
        set_name = self.question_set_var.get()
        self.language_var.set(language)
        self._replace_question_text(default_questions_text(language, set_name))
        self.status_var.set(tr("ws.question_set_loaded", set_name=set_name))

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
        self.question_summary_var.set(tr("ws.questions_loaded", count=len(questions), mode=label))

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
        self.status_var.set(tr("ws.devices_refreshed"))

    def _choose_model_root(self) -> None:
        path = filedialog.askdirectory(title=tr("ws.model_root_dialog"), initialdir=self.model_root_var.get())
        if path:
            self.model_root_var.set(path)
            self.config_model.model_root = Path(path).expanduser()
            if self.model_var.get() not in {DEFAULT_MODEL_ID, LARGE_MODEL_ID}:
                self.model_var.set(self.config_model.preferred_model_id())
            self.provider = None
            self._apply_config_from_ui()
            self.status_var.set(tr("ws.model_root_changed"))

    def _choose_video_file(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("ws.video_dialog_title"),
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
            messagebox.showwarning(tr("wizard.no_questions_title"), tr("wizard.no_questions_body"))
            return

        self._apply_config_from_ui()
        self.runtime_report = collect_runtime_diagnostics(self.config_model)
        self.diagnostic_status_var.set(self.runtime_report.summary())
        if self.runtime_report.has_failures and not messagebox.askyesno(
            tr("ws.runtime_warning_title"),
            tr("ws.runtime_warning_ask"),
        ):
            return
        self.engine = InterviewEngine(questions=questions, sessions_root=self.config_model.sessions_root)
        self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        self._set_state(SessionState.READY)
        self.runtime_badge_var.set(tr("badge.session_ready"))
        self.warning_var.set(tr("ws.answer_timer_hint"))
        self._set_session_controls(True)
        self._render_current_question()
        self.status_var.set(tr("ws.session_started"))
        self._speak_current(repeat=False)

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
        self.runtime_badge_var.set(tr("badge.session_speaking"))
        self.repeat_button.configure(state="disabled")
        self.video_player.start()
        if self.config_model.tts_backend == QWEN_BACKEND:
            self.status_var.set(tr("ws.tts_generating"))
            self.after(15000, lambda: self._show_slow_tts_notice(token))
        else:
            self.status_var.set(tr("ws.tts_sapi_playing"))

        run_bg(
            self,
            lambda: self.engine.speak_current(provider, repeat=repeat),
            on_done=lambda result: self._on_tts_done(token, result),
            on_error=lambda exc: self._on_tts_error(token, exc),
            name="tts-speak",
        )

    def _show_slow_tts_notice(self, token: int) -> None:
        if token == self.tts_token and self.tts_running:
            self.status_var.set(tr("ws.tts_slow"))

    def _on_tts_done(self, token: int, result) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        if result.warning:
            self.status_var.set(tr("ws.tts_fallback_played", name=result.wav_path.name))
            self.runtime_badge_var.set(tr("badge.fallback"))
            self.warning_var.set(result.warning)
            messagebox.showwarning("Qwen3-TTS fallback", result.warning)
        else:
            self.status_var.set(tr("ws.answer_timing", backend=result.backend, name=result.wav_path.name))
            self.runtime_badge_var.set(tr("badge.session_answering"))
            self.warning_var.set(tr("ws.answer_timing_hint"))
        self._set_state(SessionState.ANSWERING)
        self._render_current_question()

    def _on_tts_error(self, token: int, exc: Exception) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self._set_state(SessionState.ERROR)
        self.runtime_badge_var.set(tr("badge.session_error"))
        self.warning_var.set(str(exc))
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        self.status_var.set(tr("ws.tts_error_status"))
        messagebox.showerror(tr("ws.tts_error_title"), str(exc))

    def _stop_tts(self) -> None:
        self.tts_token += 1
        self.tts_running = False
        self._set_state(SessionState.ANSWERING if self.engine is not None else SessionState.IDLE)
        self.runtime_badge_var.set(tr("badge.session_answering") if self.engine is not None else tr("badge.ready"))
        self.repeat_button.configure(state="normal")
        if self.provider is not None:
            self.provider.stop()
        if hasattr(self, "video_player"):
            self.video_player.stop()
        if self.engine is not None:
            self.engine.session.start_answer(self.engine.current_index)
            self.engine.session.save()
        self.status_var.set(tr("ws.tts_stopped"))

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
            messagebox.showerror(tr("ws.record_failed_title"), str(exc))
            self._set_state(SessionState.ERROR)
            return

        self.recording = True
        self._set_state(SessionState.RECORDING)
        self.runtime_badge_var.set(tr("badge.session_recording"))
        self.warning_var.set(tr("ws.recording_hint"))
        self.recording_path = path
        self.record_button.configure(state="disabled")
        self.stop_record_button.configure(state="normal")
        self.status_var.set(tr("ws.recording"))
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
            self.runtime_badge_var.set(tr("badge.session_error"))
            self.warning_var.set(str(exc))
            messagebox.showerror(tr("ws.record_stop_failed_title"), str(exc))
            return

        self.recording = False
        self._set_state(SessionState.TRANSCRIBING)
        self.runtime_badge_var.set(tr("badge.session_stt"))
        self.warning_var.set(tr("ws.transcribing_hint"))
        self.recording_path = path
        self.record_button.configure(state="normal")
        self.stop_record_button.configure(state="disabled")
        self.engine.session.set_answer_audio_path(self.engine.current_index, path)
        self.engine.finish_current_answer()
        self.status_var.set(tr("ws.transcribing"))
        index = self.engine.current_index
        question = self.engine.current_record.clean_question
        language = detect_language(question)

        run_bg(
            self,
            lambda: self.transcriber.transcribe(path, language=language),
            on_done=lambda result: self._on_transcript_done(index, result.text),
            on_error=self._on_transcript_error,
            name="stt-transcribe",
        )

    def _on_transcript_done(self, index: int, transcript: str) -> None:
        if self.engine is None:
            return
        self.engine.session.set_transcript(index, transcript)
        self.engine.session.save()
        if index == self.engine.current_index:
            self.transcript_text.delete("1.0", "end")
            self.transcript_text.insert("1.0", transcript)
        self.status_var.set(tr("ws.transcript_done"))
        self.runtime_badge_var.set(tr("badge.session_answering"))
        self.warning_var.set(tr("ws.transcript_hint"))
        self._set_state(SessionState.ANSWERING)

    def _on_transcript_error(self, exc: Exception) -> None:
        self.status_var.set(tr("ws.transcript_failed"))
        self._set_state(SessionState.ERROR)
        self.runtime_badge_var.set(tr("badge.session_error"))
        self.warning_var.set(str(exc))
        messagebox.showerror(tr("ws.stt_error_title"), str(exc))

    def _generate_follow_up(self) -> None:
        if self.engine is None:
            return
        self._apply_config_from_ui()
        self._save_current_memo()
        record = self.engine.current_record
        transcript = self.transcript_text.get("1.0", "end").strip() or record.memo
        question = record.clean_question
        language = detect_language(question)
        self.status_var.set(tr("ws.followup_generating"))
        self._set_state(SessionState.FOLLOW_UP_GENERATING)
        self.runtime_badge_var.set(tr("badge.session_followup"))
        self.warning_var.set(tr("ws.followup_hint"))

        run_bg(
            self,
            lambda: generate_follow_up_question(
                question,
                transcript,
                language,
                provider=self.config_model.followup_provider,
                ollama_model=self.config_model.ollama_model,
                ollama_host=self.config_model.ollama_host,
            ),
            on_done=self._on_follow_up_done,
            name="follow-up",
        )

    def _on_follow_up_done(self, follow_up: str) -> None:
        if self.engine is None:
            return
        self.engine.session.set_follow_up_question(self.engine.current_index, follow_up)
        self.engine.session.save()
        self.followup_text.delete("1.0", "end")
        self.followup_text.insert("1.0", follow_up)
        self.status_var.set(tr("ws.followup_done"))
        self.runtime_badge_var.set(tr("badge.session_answering"))
        self.warning_var.set(tr("ws.followup_edit_hint"))
        self._set_state(SessionState.ANSWERING)

    def _speak_follow_up(self) -> None:
        if self.engine is None or self.tts_running:
            return
        self._apply_config_from_ui()
        self._save_current_memo()
        follow_up = self.followup_text.get("1.0", "end").strip()
        if not follow_up:
            messagebox.showwarning(tr("ws.followup_missing_title"), tr("ws.followup_missing_body"))
            return

        provider = self._get_provider()
        token = self.tts_token + 1
        self.tts_token = token
        self.tts_running = True
        self._set_state(SessionState.SPEAKING)
        self.repeat_button.configure(state="disabled")
        self.video_player.start()
        self.status_var.set(tr("ws.followup_playing"))
        session_id = self.engine.session.session_id
        current_index = self.engine.current_index

        def speak_follow_up() -> None:
            language, speaker = provider.resolve_voice(follow_up)
            provider.speak(
                text=follow_up,
                cache_key=f"{session_id}-{current_index + 1}-followup",
                language=language,
                speaker=speaker,
            )

        run_bg(
            self,
            speak_follow_up,
            on_done=lambda _result: self._on_follow_up_tts_done(token),
            on_error=lambda exc: self._on_tts_error(token, exc),
            name="tts-follow-up",
        )

    def _on_follow_up_tts_done(self, token: int) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        if hasattr(self, "video_player"):
            self.video_player.stop()
        self.status_var.set(tr("ws.followup_played"))
        self._set_state(SessionState.ANSWERING)

    def _test_system_sound(self) -> None:
        try:
            provider = self._get_provider() if self.engine is not None else QwenTTSProvider(
                self.config_model,
                self.config_model.sessions_root / "_diagnostics",
            )
            provider.play_system_beep()
            self.status_var.set(tr("ws.beep_done"))
        except Exception as exc:
            messagebox.showerror(tr("ws.beep_failed_title"), str(exc))

    def _diagnose_tts(self) -> None:
        self._apply_config_from_ui()
        self.runtime_report = collect_runtime_diagnostics(self.config_model)
        self.diagnostic_status_var.set(self.runtime_report.summary())
        if self.tts_backend_var.get() == QWEN_BACKEND and not self._selected_model_installed():
            if messagebox.askyesno(
                tr("ws.diagnostics_title"),
                tr("ws.diagnostics_download_ask", report=diagnostics_text(self.runtime_report)),
            ):
                self._open_model_download(self.model_var.get())
            return
        messagebox.showinfo(tr("ws.diagnostics_title"), diagnostics_text(self.runtime_report))

    def _next_question(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning(tr("ws.recording_title"), tr("ws.stop_before_next"))
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
            messagebox.showwarning(tr("ws.recording_title"), tr("ws.stop_before_prev"))
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
            messagebox.showwarning(tr("ws.recording_title"), tr("ws.stop_before_restart"))
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.restart()
        self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        self._render_current_question()
        self.status_var.set(tr("ws.session_restarted"))
        self._speak_current(repeat=False)

    def _open_session_folder(self) -> None:
        if self.engine is None:
            return
        self._save_current_memo()
        path = self.engine.session.session_dir
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo(tr("ws.session_folder_title"), str(path))

    def _open_session_browser(self) -> None:
        active_session_id = self.engine.session.session_id if self.engine is not None else None
        SessionBrowserDialog(self, self.config_model.sessions_root, active_session_id=active_session_id)
