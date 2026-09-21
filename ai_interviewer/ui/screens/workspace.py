from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_interviewer import __version__, credentials
from ai_interviewer.app_state import SessionState
from ai_interviewer.config import (
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_OFFLINE,
    DEFAULT_MODEL_ID,
    LARGE_MODEL_ID,
    MAX_PROBE_DEPTH,
    QWEN_BACKEND,
    SUGGESTED_OLLAMA_MODELS,
    SUPPORTED_AI_EFFORTS,
    SUPPORTED_AI_PROVIDERS,
    SUPPORTED_SENIORITY_LEVELS,
    SUPPORTED_STT_MODELS,
    SUPPORTED_TTS_BACKENDS,
    STT_MODEL_AUTO,
)
from ai_interviewer.default_questions import (
    default_questions_text,
    question_set_for_interview_type,
    question_set_names,
)
from ai_interviewer.diagnostics import collect_runtime_diagnostics, diagnostics_text
from ai_interviewer.engine import InterviewEngine
from ai_interviewer.i18n import SUPPORTED_UI_LANGUAGES, tr, ui_language_label
from ai_interviewer.intelligence import (
    AnswerInsight,
    analyze_answer_turn,
    follow_up_for_answer,
    generate_blueprint,
    insight_from_record,
    provider_statuses,
)
from ai_interviewer.question_parser import detect_language, parse_questions
from ai_interviewer.stt import (
    STTError,
    effective_model_size,
    input_device_id_from_label,
    list_input_devices,
)
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import (
    backend_display_name,
    default_speaker_for_language,
    speaker_ids,
)
from ai_interviewer.ui.context import AppContext
from ai_interviewer.ui.dialogs import messages
from ai_interviewer.ui.dialogs.session_browser import SessionBrowserDialog
from ai_interviewer.ui.widgets import cards
from ai_interviewer.ui.widgets.binding import bind_checkbox, bind_combo, bind_line_edit
from ai_interviewer.ui.widgets.buttons import IconButton
from ai_interviewer.ui.widgets.coach_panel import CoachPanel
from ai_interviewer.ui.widgets.signal_widget import SignalWidget
from ai_interviewer.ui.widgets.text_edit import make_text_edit, set_text_content
from ai_interviewer.ui.widgets.video_widget import InterviewerVideoWidget
from ai_interviewer.ui.workers import run_bg

if TYPE_CHECKING:
    from ai_interviewer.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


class WorkspaceScreen(QWidget):
    """The live interview screen: question studio, interview room, side panel."""

    def __init__(self, ctx: AppContext, window: "MainWindow") -> None:
        super().__init__()
        self.ctx = ctx
        self.window = window
        self._evaluating = False
        self._prefetching = False
        self._pending_blueprint = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)

        self._build_header(outer)

        main = QHBoxLayout()
        main.setSpacing(12)
        outer.addLayout(main, 1)

        question_column = QWidget()
        question_column_layout = QVBoxLayout(question_column)
        question_column_layout.setContentsMargins(0, 0, 0, 0)
        room_column = QWidget()
        room_column_layout = QVBoxLayout(room_column)
        room_column_layout.setContentsMargins(0, 0, 0, 0)
        side_column = QWidget()
        side_column_layout = QVBoxLayout(side_column)
        side_column_layout.setContentsMargins(0, 0, 0, 0)
        side_column_layout.setSpacing(12)
        main.addWidget(question_column, 4)
        main.addWidget(room_column, 6)
        main.addWidget(side_column, 4)

        self._build_question_studio(question_column_layout)
        self._build_interview_room(room_column_layout)
        self._build_side_panel(side_column_layout)
        self._set_session_controls(False)
        self._refresh_question_summary()

        self.ctx.configApplied.connect(self._on_config_applied)

    # -- construction -------------------------------------------------------

    def _build_header(self, outer: QVBoxLayout) -> None:
        header = cards.frame("hero")
        outer.addWidget(header)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(18)

        title_area = QVBoxLayout()
        title_area.setSpacing(2)
        title = cards.label("AI Interviewer", "display")
        subtitle = cards.label(tr("ws.subtitle", version=__version__), "heroSubtitle")
        title_area.addWidget(title)
        title_area.addWidget(subtitle)
        layout.addLayout(title_area)

        status = cards.frame("subtle")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(2)
        status_layout.addWidget(cards.bound_label(self.ctx.runtime_badge_var, "status"))
        status_layout.addWidget(cards.bound_label(self.ctx.status_var, "subtitle", wrap=True))
        status_layout.addWidget(cards.bound_label(self.ctx.diagnostic_status_var, "muted", wrap=True))
        layout.addWidget(status, 1)

        actions = QVBoxLayout()
        actions.setSpacing(4)
        actions.addWidget(cards.label(tr("ws.interview_mode"), "railAccent"))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        mode_group = QButtonGroup(self)
        self.korean_mode_button = QRadioButton("한국어")
        self.english_mode_button = QRadioButton("English")
        self.korean_mode_button.setChecked(self.ctx.interview_language_var.get() == "Korean")
        self.english_mode_button.setChecked(self.ctx.interview_language_var.get() == "English")
        for button, value in ((self.korean_mode_button, "Korean"), (self.english_mode_button, "English")):
            mode_group.addButton(button)
            button.toggled.connect(
                lambda checked, v=value: self._on_language_mode_selected(v) if checked else None
            )
            mode_row.addWidget(button)
        actions.addLayout(mode_row)
        self.start_button = IconButton(tr("ws.start_interview"), icon_name="play", kind="primary")
        self.start_button.clicked.connect(self.start_session)
        actions.addSpacing(6)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)

    def _build_question_studio(self, column: QVBoxLayout) -> None:
        studio = cards.frame("card")
        column.addWidget(studio, 1)
        layout = QVBoxLayout(studio)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        layout.addWidget(cards.section_header(tr("ws.question_studio_title"), tr("ws.question_studio_sub")))

        pack_row = QHBoxLayout()
        pack_row.setSpacing(8)
        pack_row.addWidget(cards.label(tr("ws.question_pack"), "section"))
        self.question_set_combo = QComboBox()
        self.question_set_combo.addItems(question_set_names(self.ctx.interview_language_var.get()))
        self.question_set_combo.setCurrentText(self.ctx.question_set_var.get())
        self.question_set_combo.currentTextChanged.connect(self.ctx.question_set_var.set)
        self.question_set_combo.activated.connect(lambda _index: self._apply_selected_question_set())
        pack_row.addWidget(self.question_set_combo, 1)
        load_button = IconButton(tr("common.load"), kind="tool")
        load_button.clicked.connect(self._apply_selected_question_set)
        file_button = IconButton(tr("common.file"), icon_name="file-text", kind="tool")
        file_button.clicked.connect(self._load_questions_file)
        self.design_button = IconButton(tr("ws.btn_design_plan"), icon_name="sparkles", kind="tool")
        self.design_button.clicked.connect(self._design_question_plan)
        pack_row.addWidget(load_button)
        pack_row.addWidget(file_button)
        pack_row.addWidget(self.design_button)
        layout.addSpacing(14)
        layout.addLayout(pack_row)

        summary = cards.frame("subtle")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.addWidget(cards.bound_label(self.ctx.question_summary_var, "status"))
        summary_layout.addStretch(1)
        summary_layout.addWidget(cards.label(tr("ws.pack_isolated"), "subtitle"))
        layout.addSpacing(12)
        layout.addWidget(summary)

        self.question_text = make_text_edit(min_lines=14)
        self.question_text.textChanged.connect(self._refresh_question_summary)
        set_text_content(
            self.question_text,
            default_questions_text(self.ctx.interview_language_var.get(), self.ctx.question_set_var.get()),
        )
        layout.addSpacing(10)
        layout.addWidget(self.question_text, 1)

    def _build_interview_room(self, column: QVBoxLayout) -> None:
        room = cards.frame("card")
        column.addWidget(room, 1)
        layout = QVBoxLayout(room)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        layout.addWidget(cards.section_header(tr("ws.room_title"), tr("ws.room_sub")))

        video_shell = cards.frame("stage")
        shell_layout = QVBoxLayout(video_shell)
        shell_layout.setContentsMargins(10, 10, 10, 10)
        shell_layout.setSpacing(10)
        self.video_player = InterviewerVideoWidget(width=520, height=292)
        self.video_player.set_video_path(self.ctx.config_model.video_path)
        shell_layout.addWidget(self.video_player)
        shell_layout.addWidget(SignalWidget(height=58, animated=True, compact=True))
        layout.addSpacing(14)
        layout.addWidget(video_shell)

        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        metrics.addWidget(cards.metric_tile(tr("ws.metric_progress"), self.ctx.progress_var), 1)
        metrics.addWidget(cards.metric_tile(tr("ws.metric_answer"), self.ctx.answer_timer_var), 1)
        metrics.addWidget(cards.metric_tile(tr("ws.metric_total"), self.ctx.total_timer_var), 1)
        metrics.addWidget(cards.metric_tile(tr("ws.metric_score"), self.ctx.last_score_var), 1)
        metrics.addWidget(cards.metric_tile(tr("ws.metric_coverage"), self.ctx.coverage_var), 1)
        layout.addSpacing(12)
        layout.addLayout(metrics)

        question_box = cards.frame("questionPanel")
        question_layout = QVBoxLayout(question_box)
        question_layout.setContentsMargins(16, 16, 16, 16)
        question_layout.setSpacing(6)
        question_layout.addWidget(cards.label(tr("ws.current_question"), "questionKicker"))
        question_layout.addWidget(cards.bound_label(self.ctx.current_question_var, "question", wrap=True))
        layout.addSpacing(12)
        layout.addWidget(question_box)

        self._build_session_controls(layout)
        layout.addStretch(1)

    def _build_session_controls(self, layout: QVBoxLayout) -> None:
        controls = QGridLayout()
        controls.setHorizontalSpacing(6)
        controls.setVerticalSpacing(7)

        self.prev_button = IconButton(tr("ws.btn_prev"), icon_name="skip-back", kind="tool")
        self.next_button = IconButton(tr("ws.btn_next"), icon_name="skip-forward", kind="secondary")
        self.repeat_button = IconButton(tr("ws.btn_replay"), icon_name="rotate-ccw", kind="tool")
        self.stop_button = IconButton(tr("ws.btn_stop_tts"), icon_name="square", kind="tool")
        self.record_button = IconButton(tr("ws.btn_record"), icon_name="mic", kind="secondary")
        self.stop_record_button = IconButton(tr("ws.btn_stop_stt"), icon_name="mic-off", kind="tool")
        self.evaluate_button = IconButton(tr("ws.btn_evaluate"), icon_name="activity", kind="primary")
        self.probe_button = IconButton(tr("ws.btn_ask_probe"), icon_name="message-circle-question", kind="secondary")
        self.report_button = IconButton(tr("ws.btn_report"), icon_name="file-text", kind="secondary")
        self.followup_button = IconButton(tr("ws.btn_followup"), icon_name="sparkles", kind="secondary")
        self.followup_speak_button = IconButton(tr("ws.btn_read_followup"), icon_name="volume-2", kind="tool")
        self.restart_button = IconButton(tr("ws.btn_restart"), icon_name="refresh-cw", kind="tool")
        self.open_folder_button = IconButton(tr("ws.btn_session_folder"), icon_name="folder-open", kind="tool")
        self.sound_test_button = IconButton(tr("ws.btn_sound_test"), icon_name="volume-2", kind="tool")
        self.diagnostics_button = IconButton(tr("ws.btn_diagnostics"), icon_name="activity", kind="tool")
        self.sessions_button = IconButton(tr("ws.btn_sessions"), icon_name="history", kind="tool")

        self.prev_button.clicked.connect(self._previous_question)
        self.next_button.clicked.connect(self._next_question)
        self.repeat_button.clicked.connect(lambda: self._speak_current(repeat=True))
        self.stop_button.clicked.connect(self._stop_tts)
        self.record_button.clicked.connect(self._start_recording)
        self.stop_record_button.clicked.connect(self._stop_recording_and_transcribe)
        self.evaluate_button.clicked.connect(self._evaluate_answer)
        self.probe_button.clicked.connect(self._ask_probe)
        self.report_button.clicked.connect(self._open_report)
        self.followup_button.clicked.connect(self._generate_follow_up)
        self.followup_speak_button.clicked.connect(self._speak_follow_up)
        self.restart_button.clicked.connect(self._restart_session)
        self.open_folder_button.clicked.connect(self._open_session_folder)
        self.sound_test_button.clicked.connect(self._test_system_sound)
        self.diagnostics_button.clicked.connect(self._diagnose_tts)
        self.sessions_button.clicked.connect(self._open_session_browser)

        buttons = (
            self.prev_button,
            self.next_button,
            self.repeat_button,
            self.stop_button,
            self.record_button,
            self.stop_record_button,
            self.evaluate_button,
            self.probe_button,
            self.followup_button,
            self.followup_speak_button,
            self.report_button,
            self.restart_button,
            self.open_folder_button,
            self.sound_test_button,
            self.diagnostics_button,
            self.sessions_button,
        )
        for index, button in enumerate(buttons):
            button.setProperty("dense", "true")
            button.setIconSize(QSize(14, 14))
            row, column = divmod(index, 4)
            controls.addWidget(button, row, column)
        for column in range(4):
            controls.setColumnStretch(column, 1)
        layout.addSpacing(14)
        layout.addLayout(controls)

    def _build_side_panel(self, column: QVBoxLayout) -> None:
        runtime = cards.frame("card")
        column.addWidget(runtime)
        runtime_layout = QVBoxLayout(runtime)
        runtime_layout.setContentsMargins(14, 14, 14, 14)
        runtime_layout.setSpacing(12)
        runtime_layout.addWidget(cards.section_header(tr("ws.runtime_watch_title"), tr("ws.runtime_watch_sub")))
        rows = QGridLayout()
        rows.setHorizontalSpacing(10)
        rows.setVerticalSpacing(8)
        rows.setColumnStretch(1, 1)
        cards.status_row(rows, 0, tr("ws.row_state"), self.ctx.runtime_badge_var)
        cards.status_row(rows, 1, tr("ws.row_diagnostics"), self.ctx.diagnostic_status_var)
        cards.status_row(rows, 2, tr("ws.row_notice"), self.ctx.warning_var, role="warning")
        runtime_layout.addLayout(rows)

        settings = cards.frame("card")
        column.addWidget(settings)
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_layout.setSpacing(12)
        settings_layout.addWidget(cards.section_header(tr("ws.settings_title"), tr("ws.settings_sub")))
        self._build_settings_tabs(settings_layout)

        workspace = cards.frame("card")
        column.addWidget(workspace, 1)
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(14, 14, 14, 14)
        workspace_layout.setSpacing(10)
        workspace_layout.addWidget(cards.section_header(tr("ws.workspace_title"), tr("ws.workspace_sub")))
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setDocumentMode(True)
        self.memo_text = make_text_edit(min_lines=6)
        self.transcript_text = make_text_edit(min_lines=6)
        self.followup_text = make_text_edit(min_lines=6)
        self.coach_panel = CoachPanel()
        self.coach_tab_index = self.detail_tabs.addTab(self.coach_panel, tr("ws.tab_coach"))
        self.detail_tabs.addTab(self.transcript_text, tr("ws.tab_stt"))
        self.detail_tabs.addTab(self.memo_text, tr("ws.tab_memo"))
        self.detail_tabs.addTab(self.followup_text, tr("ws.tab_followup"))
        workspace_layout.addWidget(self.detail_tabs, 1)

    def _build_settings_tabs(self, parent_layout: QVBoxLayout) -> None:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        parent_layout.addWidget(tabs)

        # -- voice tab -------------------------------------------------------
        voice_tab = QWidget()
        voice = QGridLayout(voice_tab)
        voice.setContentsMargins(10, 10, 10, 10)
        voice.setHorizontalSpacing(8)
        voice.setVerticalSpacing(8)
        voice.setColumnStretch(1, 1)

        voice.addWidget(cards.label(tr("ws.set_tts_engine"), "section"), 0, 0)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems([backend_display_name(backend) for backend in SUPPORTED_TTS_BACKENDS])
        self.backend_combo.setCurrentText(backend_display_name(self.ctx.tts_backend_var.get()))
        self.backend_combo.currentTextChanged.connect(self._on_backend_selected)
        voice.addWidget(self.backend_combo, 0, 1)
        fallback_check = QCheckBox(tr("ws.windows_fallback"))
        bind_checkbox(fallback_check, self.ctx.allow_fallback_var)
        voice.addWidget(fallback_check, 0, 2)

        voice.addWidget(cards.label(tr("ws.set_model"), "section"), 1, 0)
        model_combo = QComboBox()
        model_combo.addItems((DEFAULT_MODEL_ID, LARGE_MODEL_ID))
        bind_combo(model_combo, self.ctx.model_var)
        voice.addWidget(model_combo, 1, 1, 1, 2)

        voice.addWidget(cards.label(tr("ws.set_language"), "section"), 2, 0)
        language_combo = QComboBox()
        language_combo.addItems(("Auto", "Korean", "English"))
        bind_combo(language_combo, self.ctx.language_var)
        voice.addWidget(language_combo, 2, 1)

        voice.addWidget(cards.label(tr("ws.set_speaker"), "section"), 3, 0)
        self.speaker_combo = QComboBox()
        self.speaker_combo.addItems(speaker_ids(self.ctx.interview_language_var.get()))
        bind_combo(self.speaker_combo, self.ctx.selected_speaker_var)
        voice.addWidget(self.speaker_combo, 3, 1, 1, 2)
        tabs.addTab(voice_tab, tr("ws.tab_voice"))

        # -- STT tab ----------------------------------------------------------
        audio_tab = QWidget()
        audio = QGridLayout(audio_tab)
        audio.setContentsMargins(10, 10, 10, 10)
        audio.setHorizontalSpacing(8)
        audio.setVerticalSpacing(8)
        audio.setColumnStretch(1, 1)

        audio.addWidget(cards.label(tr("ws.set_stt_model"), "section"), 0, 0)
        stt_model_combo = QComboBox()
        stt_model_combo.addItems(SUPPORTED_STT_MODELS)
        bind_combo(stt_model_combo, self.ctx.stt_model_var)
        audio.addWidget(stt_model_combo, 0, 1)
        self.stt_effective_label = cards.label("", "muted", wrap=True)
        audio.addWidget(self.stt_effective_label, 0, 2)
        self.ctx.stt_model_var.changed.connect(lambda _v: self._refresh_stt_hint())
        self.ctx.stt_device_var.changed.connect(lambda _v: self._refresh_stt_hint())

        audio.addWidget(cards.label(tr("ws.set_input"), "section"), 1, 0)
        self.input_device_combo = QComboBox()
        self.input_device_combo.addItems(self._input_device_labels())
        bind_combo(self.input_device_combo, self.ctx.input_device_var)
        audio.addWidget(self.input_device_combo, 1, 1)
        refresh_button = IconButton(tr("ws.refresh"), icon_name="refresh-cw", kind="tool")
        refresh_button.clicked.connect(self._refresh_input_devices)
        audio.addWidget(refresh_button, 1, 2)

        audio.addWidget(cards.label(tr("ws.set_device_compute"), "section"), 2, 0)
        stt_device_combo = QComboBox()
        stt_device_combo.addItems(("auto", "cuda", "cpu"))
        bind_combo(stt_device_combo, self.ctx.stt_device_var)
        audio.addWidget(stt_device_combo, 2, 1)
        stt_compute_combo = QComboBox()
        stt_compute_combo.addItems(("auto", "float16", "int8", "int8_float16", "float32"))
        bind_combo(stt_compute_combo, self.ctx.stt_compute_var)
        audio.addWidget(stt_compute_combo, 2, 2)
        tabs.addTab(audio_tab, tr("ws.tab_stt_settings"))
        self._refresh_stt_hint()

        # -- AI tab -------------------------------------------------------------
        ai_tab = QWidget()
        ai = QGridLayout(ai_tab)
        ai.setContentsMargins(10, 10, 10, 10)
        ai.setHorizontalSpacing(8)
        ai.setVerticalSpacing(8)
        ai.setColumnStretch(1, 1)

        ai.addWidget(cards.label(tr("ws.set_ai_provider"), "section"), 0, 0)
        self.ai_provider_combo = QComboBox()
        for provider in SUPPORTED_AI_PROVIDERS:
            self.ai_provider_combo.addItem(tr(f"ai.provider.{provider}"), provider)
        self.ai_provider_combo.setCurrentIndex(
            max(0, self.ai_provider_combo.findData(self.ctx.ai_provider_var.get()))
        )
        self.ai_provider_combo.activated.connect(self._on_ai_provider_selected)
        ai.addWidget(self.ai_provider_combo, 0, 1)
        effort_combo = QComboBox()
        for effort in SUPPORTED_AI_EFFORTS:
            effort_combo.addItem(tr(f"ai.effort.{effort}"), effort)
        effort_combo.setCurrentIndex(max(0, effort_combo.findData(self.ctx.ai_effort_var.get())))
        effort_combo.activated.connect(
            lambda index: self.ctx.ai_effort_var.set(effort_combo.itemData(index))
        )
        ai.addWidget(effort_combo, 0, 2)

        ai.addWidget(cards.label(tr("ws.provider_status"), "section"), 1, 0)
        self.provider_status_label = cards.label("", "muted", wrap=True)
        ai.addWidget(self.provider_status_label, 1, 1, 1, 3)

        scoring_check = QCheckBox(tr("ws.set_live_scoring"))
        bind_checkbox(scoring_check, self.ctx.live_scoring_var)
        ai.addWidget(scoring_check, 2, 1)
        probing_check = QCheckBox(tr("ws.set_adaptive_probing"))
        bind_checkbox(probing_check, self.ctx.adaptive_probing_var)
        ai.addWidget(probing_check, 2, 2)
        auto_speak_check = QCheckBox(tr("ws.set_auto_speak_probe"))
        bind_checkbox(auto_speak_check, self.ctx.auto_speak_probe_var)
        ai.addWidget(auto_speak_check, 2, 3)

        ai.addWidget(cards.label(tr("ws.set_probe_depth"), "section"), 3, 0)
        depth_combo = QComboBox()
        depth_combo.addItems([str(value) for value in range(MAX_PROBE_DEPTH + 1)])
        bind_combo(depth_combo, self.ctx.probe_depth_var)
        ai.addWidget(depth_combo, 3, 1)

        ai.addWidget(cards.label(tr("ws.set_target_role"), "section"), 4, 0)
        role_edit = QLineEdit()
        bind_line_edit(role_edit, self.ctx.target_role_var)
        ai.addWidget(role_edit, 4, 1, 1, 2)
        seniority_combo = QComboBox()
        for level in SUPPORTED_SENIORITY_LEVELS:
            seniority_combo.addItem(tr(f"ai.seniority.{level}"), level)
        seniority_combo.setCurrentIndex(max(0, seniority_combo.findData(self.ctx.seniority_var.get())))
        seniority_combo.activated.connect(
            lambda index: self.ctx.seniority_var.set(seniority_combo.itemData(index))
        )
        ai.addWidget(seniority_combo, 4, 3)

        ai.addWidget(cards.label(tr("ws.set_claude_model"), "section"), 5, 0)
        claude_model_edit = QLineEdit()
        bind_line_edit(claude_model_edit, self.ctx.claude_model_var)
        ai.addWidget(claude_model_edit, 5, 1, 1, 3)

        ai.addWidget(cards.label(tr("ws.set_api_key"), "section"), 6, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText(tr("ws.set_api_key_hint"))
        ai.addWidget(self.api_key_edit, 6, 1)
        save_key_button = IconButton(tr("ws.btn_save_key"), kind="tool")
        save_key_button.clicked.connect(self._save_api_key)
        ai.addWidget(save_key_button, 6, 2)
        clear_key_button = IconButton(tr("ws.btn_clear_key"), kind="tool")
        clear_key_button.clicked.connect(self._clear_api_key)
        ai.addWidget(clear_key_button, 6, 3)
        self.api_key_status_label = cards.label("", "muted", wrap=True)
        ai.addWidget(self.api_key_status_label, 7, 1, 1, 3)

        ai.addWidget(cards.label(tr("ws.set_ollama_model"), "section"), 8, 0)
        ollama_model_combo = QComboBox()
        ollama_model_combo.setEditable(True)
        ollama_model_combo.addItems(SUGGESTED_OLLAMA_MODELS)
        ollama_model_combo.setCurrentText(self.ctx.ollama_model_var.get())
        ollama_model_combo.currentTextChanged.connect(self.ctx.ollama_model_var.set)
        ai.addWidget(ollama_model_combo, 8, 1, 1, 2)
        ai.addWidget(cards.label(tr("ws.ollama_model_hint"), "muted", wrap=True), 8, 3)

        ai.addWidget(cards.label(tr("ws.set_ollama_host"), "section"), 9, 0)
        ollama_host_edit = QLineEdit()
        bind_line_edit(ollama_host_edit, self.ctx.ollama_host_var)
        ai.addWidget(ollama_host_edit, 9, 1, 1, 3)

        ai.addWidget(cards.label(tr("ws.set_jd"), "section"), 10, 0)
        self.job_description_text = make_text_edit(min_lines=3)
        set_text_content(self.job_description_text, self.ctx.job_description_var.get())
        self.job_description_text.textChanged.connect(
            lambda: self.ctx.job_description_var.set(self.job_description_text.toPlainText())
        )
        ai.addWidget(self.job_description_text, 10, 1, 1, 3)

        ai.addWidget(cards.label(tr("ws.set_resume"), "section"), 11, 0)
        self.resume_text = make_text_edit(min_lines=3)
        set_text_content(self.resume_text, self.ctx.resume_summary_var.get())
        self.resume_text.textChanged.connect(
            lambda: self.ctx.resume_summary_var.set(self.resume_text.toPlainText())
        )
        ai.addWidget(self.resume_text, 11, 1, 1, 3)
        tabs.addTab(ai_tab, tr("ws.tab_ai"))
        self._refresh_provider_status()

        # -- media tab -------------------------------------------------------------
        media_tab = QWidget()
        media = QGridLayout(media_tab)
        media.setContentsMargins(10, 10, 10, 10)
        media.setHorizontalSpacing(8)
        media.setVerticalSpacing(8)
        media.setColumnStretch(1, 1)

        media.addWidget(cards.label(tr("ws.set_model_folder"), "section"), 0, 0)
        model_root_edit = QLineEdit()
        bind_line_edit(model_root_edit, self.ctx.model_root_var)
        media.addWidget(model_root_edit, 0, 1)
        browse_model_button = IconButton(tr("common.browse"), kind="tool")
        browse_model_button.clicked.connect(self._choose_model_root)
        media.addWidget(browse_model_button, 0, 2)
        download_button = IconButton(tr("ws.model_download"), icon_name="download", kind="tool")
        download_button.clicked.connect(lambda: self.window.open_model_download(self.ctx.model_var.get()))
        media.addWidget(download_button, 0, 3)

        media.addWidget(cards.label(tr("ws.set_video_file"), "section"), 1, 0)
        video_edit = QLineEdit()
        bind_line_edit(video_edit, self.ctx.video_path_var)
        media.addWidget(video_edit, 1, 1)
        browse_video_button = IconButton(tr("common.browse"), kind="tool")
        browse_video_button.clicked.connect(self._choose_video_file)
        media.addWidget(browse_video_button, 1, 2)

        media.addWidget(cards.label(tr("ws.set_ui_language"), "section"), 2, 0)
        ui_lang_row = QHBoxLayout()
        ui_lang_row.setSpacing(12)
        group = QButtonGroup(self)
        for language in SUPPORTED_UI_LANGUAGES:
            radio = QRadioButton(ui_language_label(language))
            radio.setChecked(language == self.ctx.ui_language_var.get())
            radio.toggled.connect(
                lambda checked, lang=language: self.ctx.set_ui_language(lang) if checked else None
            )
            group.addButton(radio)
            ui_lang_row.addWidget(radio)
        ui_lang_row.addStretch(1)
        media.addLayout(ui_lang_row, 2, 1, 1, 3)

        from ai_interviewer.ui.screens.wizard import build_theme_selector

        media.addWidget(cards.label(tr("ws.set_theme"), "section"), 3, 0)
        media.addWidget(build_theme_selector(media_tab), 3, 1, 1, 3)
        tabs.addTab(media_tab, tr("ws.tab_media"))

    # -- helpers -----------------------------------------------------------------

    def _on_backend_selected(self, display: str) -> None:
        for backend in SUPPORTED_TTS_BACKENDS:
            if backend_display_name(backend) == display:
                self.ctx.tts_backend_var.set(backend)
                break

    def _on_config_applied(self) -> None:
        self.video_player.set_video_path(self.ctx.config_model.video_path)
        self._refresh_provider_status()

    # -- analysis engine settings ---------------------------------------------

    def _on_ai_provider_selected(self, index: int) -> None:
        """Switch engines, asking for consent before anything leaves the PC."""
        provider = self.ai_provider_combo.itemData(index)
        if provider in {AI_PROVIDER_CLAUDE} and not self.ctx.cloud_ai_var.get():
            if not messages.ask_yes_no(
                self.window,
                tr("ws.cloud_consent_title"),
                tr("ws.cloud_consent_body"),
            ):
                self.ctx.status_var.set(tr("ws.cloud_declined"))
                self._select_provider(AI_PROVIDER_OFFLINE)
                return
            self.ctx.cloud_ai_var.set(True)
        self.ctx.ai_provider_var.set(provider)
        self.ctx.apply_config_from_ui()

    def _select_provider(self, provider: str) -> None:
        self.ctx.ai_provider_var.set(provider)
        position = self.ai_provider_combo.findData(provider)
        if position >= 0:
            self.ai_provider_combo.setCurrentIndex(position)
        self.ctx.apply_config_from_ui()

    def _refresh_stt_hint(self) -> None:
        """Say which checkpoint `auto` resolves to on this machine."""
        if not hasattr(self, "stt_effective_label"):
            return
        self.ctx.config_model.stt_model_size = self.ctx.stt_model_var.get()
        self.ctx.config_model.stt_device = self.ctx.stt_device_var.get()
        resolved = effective_model_size(self.ctx.config_model)
        if self.ctx.stt_model_var.get() == STT_MODEL_AUTO:
            self.stt_effective_label.setText(tr("ws.stt_auto_hint", model=resolved))
        else:
            self.stt_effective_label.setText("")

    def _refresh_provider_status(self) -> None:
        if not hasattr(self, "provider_status_label"):
            return
        lines = []
        for status in provider_statuses(self.ctx.ai_settings()):
            mark = "✓" if status.available else "·"
            model = f" ({status.model})" if status.model else ""
            lines.append(f"{mark} {status.name}{model} — {status.detail}")
        self.provider_status_label.setText("\n".join(lines))
        self._refresh_key_status()

    def _refresh_key_status(self) -> None:
        if not hasattr(self, "api_key_status_label"):
            return
        source = credentials.anthropic_key_source()
        if source == credentials.SOURCE_ENV:
            text = tr("ws.key_source_env")
        elif source == credentials.SOURCE_FILE:
            text = tr("ws.key_source_file", masked=credentials.masked(credentials.anthropic_api_key()))
        else:
            text = tr("ws.key_source_none")
        self.api_key_status_label.setText(f"{text}\n{tr('ws.set_api_key_hint')}")

    def _save_api_key(self) -> None:
        key = self.api_key_edit.text().strip()
        if not key:
            return
        credentials.store_anthropic_api_key(key)
        self.api_key_edit.clear()
        self.ctx.status_var.set(tr("ws.key_saved"))
        self._refresh_provider_status()

    def _clear_api_key(self) -> None:
        credentials.clear_anthropic_api_key()
        self.api_key_edit.clear()
        self.ctx.status_var.set(tr("ws.key_cleared"))
        self._refresh_provider_status()

    def _set_session_controls(self, enabled: bool) -> None:
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
            self.evaluate_button,
            self.report_button,
        ):
            button.setEnabled(enabled)
        # A probe needs a scored answer first; _on_insight turns it back on.
        self.probe_button.setEnabled(False)
        if not self.ctx.enable_stt_var.get():
            self.record_button.setEnabled(False)
            self.stop_record_button.setEnabled(False)
            return
        self.stop_record_button.setEnabled(self.ctx.recording)
        self.sound_test_button.setEnabled(True)
        self.diagnostics_button.setEnabled(True)

    def question_text_content(self) -> str:
        return self.question_text.toPlainText()

    def replace_question_text(self, content: str) -> None:
        set_text_content(self.question_text, content)
        self._refresh_question_summary()

    def _refresh_question_summary(self) -> None:
        questions = parse_questions(self.question_text.toPlainText())
        mode = self.ctx.interview_language_var.get()
        label = "한국어" if mode == "Korean" else "English"
        self.ctx.question_summary_var.set(tr("ws.questions_loaded", count=len(questions), mode=label))

    # -- question sources ------------------------------------------------------------

    def _load_questions_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            tr("ws.file_dialog_title"),
            "",
            "Text or CSV (*.txt *.csv);;All files (*.*)",
        )
        if not path:
            return
        content = self._read_question_file(Path(path))
        self.replace_question_text(content)
        self.ctx.status_var.set(tr("ws.file_loaded", name=Path(path).name))

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

    def _on_language_mode_selected(self, language: str) -> None:
        if language == self.ctx.interview_language_var.get():
            return
        self.ctx.interview_language_var.set(language)
        self._on_language_mode_changed()

    def _on_language_mode_changed(self) -> None:
        language = self.ctx.interview_language_var.get()
        names = question_set_names(language)
        selected = question_set_for_interview_type(language, self.ctx.interview_type_var.get())
        self.ctx.question_set_var.set(selected)
        self.question_set_combo.blockSignals(True)
        self.question_set_combo.clear()
        self.question_set_combo.addItems(names)
        self.question_set_combo.setCurrentText(selected)
        self.question_set_combo.blockSignals(False)
        self.speaker_combo.blockSignals(True)
        self.speaker_combo.clear()
        self.speaker_combo.addItems(speaker_ids(language))
        self.speaker_combo.blockSignals(False)
        self.ctx.selected_speaker_var.set(default_speaker_for_language(language).speaker_id)
        self.speaker_combo.setCurrentText(self.ctx.selected_speaker_var.get())
        self.ctx.language_var.set(language)
        self.replace_question_text(default_questions_text(language, selected))
        self.ctx.status_var.set(
            tr("ws.question_set_loaded_ko") if language == "Korean" else tr("ws.question_set_loaded_en")
        )

    def _design_question_plan(self) -> None:
        """Ask the configured engine for a role-specific question plan.

        Offline there is nothing to design from, so the button explains that
        instead of silently rewriting the pack with the pack.
        """
        ctx = self.ctx
        ctx.apply_config_from_ui()
        chain = ctx.ai_chain()
        if not chain.enabled:
            messages.info(
                self.window,
                tr("ws.btn_design_plan"),
                tr("ws.blueprint_needs_engine"),
            )
            return

        language = ctx.interview_language_var.get()
        current = [question.clean for question in parse_questions(self.question_text.toPlainText())]
        config = ctx.config_model
        self.design_button.setEnabled(False)
        ctx.status_var.set(tr("ws.blueprint_generating"))

        run_bg(
            self,
            lambda: generate_blueprint(
                chain=chain,
                language=language,
                interview_type=config.interview_type,
                role=config.target_role,
                seniority=config.target_seniority,
                job_description=config.job_description,
                resume_summary=config.resume_summary,
                question_count=max(5, min(len(current) or 8, 12)),
                fallback_questions=current,
                effort=ctx.ai_effort(),
            ),
            on_done=self._on_question_plan_ready,
            on_error=self._on_question_plan_error,
            name="question-plan",
        )

    def _on_question_plan_ready(self, blueprint) -> None:
        self.design_button.setEnabled(True)
        if blueprint.engine == "offline" or not blueprint.question_count:
            self.ctx.status_var.set(tr("ws.blueprint_failed"))
            return
        self._pending_blueprint = blueprint
        self.replace_question_text(
            "\n".join(
                f"{index}. {text}"
                for index, text in enumerate(blueprint.question_texts(), start=1)
            )
        )
        self.ctx.status_var.set(tr("ws.blueprint_done", engine=blueprint.engine))
        if blueprint.notes:
            self.ctx.warning_var.set(blueprint.notes)

    def _on_question_plan_error(self, exc: Exception) -> None:
        self.design_button.setEnabled(True)
        logger.exception("Could not design a question plan.", exc_info=exc)
        self.ctx.status_var.set(tr("ws.blueprint_failed"))

    def _apply_selected_question_set(self) -> None:
        language = self.ctx.interview_language_var.get()
        set_name = self.ctx.question_set_var.get()
        self.ctx.language_var.set(language)
        self.replace_question_text(default_questions_text(language, set_name))
        self.ctx.status_var.set(tr("ws.question_set_loaded", set_name=set_name))

    def _input_device_labels(self) -> tuple[str, ...]:
        try:
            labels = tuple(device.label for device in list_input_devices())
        except STTError:
            labels = ()
        return ("Default", *labels)

    def _refresh_input_devices(self) -> None:
        labels = self._input_device_labels()
        self.input_device_combo.blockSignals(True)
        self.input_device_combo.clear()
        self.input_device_combo.addItems(labels)
        self.input_device_combo.blockSignals(False)
        if self.ctx.input_device_var.get() not in labels:
            self.ctx.input_device_var.set("Default")
        self.input_device_combo.setCurrentText(self.ctx.input_device_var.get())
        self.ctx.status_var.set(tr("ws.devices_refreshed"))

    def _choose_model_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("ws.model_root_dialog"), self.ctx.model_root_var.get())
        if path:
            self.ctx.model_root_var.set(path)
            self.ctx.config_model.model_root = Path(path).expanduser()
            if self.ctx.model_var.get() not in {DEFAULT_MODEL_ID, LARGE_MODEL_ID}:
                self.ctx.model_var.set(self.ctx.config_model.preferred_model_id())
            self.ctx.provider = None
            self.ctx.apply_config_from_ui()
            self.ctx.status_var.set(tr("ws.model_root_changed"))

    def _choose_video_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            tr("ws.video_dialog_title"),
            "",
            "Interviewer media (*.mp4 *.avi *.mov *.mkv *.png *.jpg *.jpeg *.webp *.bmp);;"
            "Video files (*.mp4 *.avi *.mov *.mkv);;"
            "Photo files (*.png *.jpg *.jpeg *.webp *.bmp);;"
            "All files (*.*)",
        )
        if path:
            self.ctx.video_path_var.set(path)
            self.ctx.config_model.video_path = Path(path).expanduser()
            self.video_player.set_video_path(self.ctx.config_model.video_path)
            self.ctx.apply_config_from_ui()

    # -- session flow ------------------------------------------------------------

    def start_session(self) -> None:
        questions = parse_questions(self.question_text.toPlainText())
        if not questions:
            messages.warning(self.window, tr("wizard.no_questions_title"), tr("wizard.no_questions_body"))
            return

        self.ctx.apply_config_from_ui()
        # Diagnostics probe the filesystem and installed packages; keep them
        # off the UI thread (the Tk app used to freeze briefly here).
        self.start_button.setEnabled(False)
        self.ctx.status_var.set(tr("app.diag_checking"))
        run_bg(
            self,
            lambda: collect_runtime_diagnostics(self.ctx.config_model),
            on_done=lambda report: self._start_session_with_report(report, questions),
            on_error=self._on_start_session_error,
            name="pre-session-diagnostics",
        )

    def _on_start_session_error(self, exc: Exception) -> None:
        self.start_button.setEnabled(True)
        self.ctx.status_var.set(tr("app.runtime_issues_status"))
        messages.error(self.window, tr("ws.runtime_warning_title"), str(exc))

    def _start_session_with_report(self, report, questions) -> None:
        self.start_button.setEnabled(True)
        self.ctx.runtime_report = report
        self.ctx.diagnostic_status_var.set(report.summary())
        if report.has_failures and not messages.ask_yes_no(
            self.window,
            tr("ws.runtime_warning_title"),
            tr("ws.runtime_warning_ask"),
        ):
            self.ctx.status_var.set(tr("app.runtime_issues_status"))
            return
        config = self.ctx.config_model
        self.ctx.engine = InterviewEngine(
            questions=questions,
            sessions_root=config.sessions_root,
            interview_type=config.interview_type,
            language=self.ctx.interview_language_var.get(),
            role=config.target_role,
        )
        self._attach_designed_plan(questions)
        self.ctx.provider = QwenTTSProvider(config, self.ctx.engine.session.audio_cache_dir)
        self.ctx.set_state(SessionState.READY)
        self.ctx.runtime_badge_var.set(tr("badge.session_ready"))
        self.ctx.warning_var.set(tr("ws.answer_timer_hint"))
        self._set_session_controls(True)
        self._render_current_question()
        self.ctx.status_var.set(tr("ws.session_started"))
        self._speak_current(repeat=False)

    def _attach_designed_plan(self, questions) -> None:
        """Keep a generated plan's competency tags if the questions still match.

        The user can edit the text after designing a plan; when they have, the
        engine's own offline tagging is the honest fallback.
        """
        blueprint = self._pending_blueprint
        if blueprint is None or self.ctx.engine is None:
            return
        if blueprint.question_texts() == tuple(question.clean for question in questions):
            self.ctx.engine.attach_blueprint(blueprint)

    def _render_current_question(self) -> None:
        engine = self.ctx.engine
        if engine is None:
            return
        record = engine.current_record
        self.ctx.progress_var.set(f"{engine.current_index + 1} / {engine.question_count}")
        self.ctx.current_question_var.set(record.clean_question)
        set_text_content(self.memo_text, record.memo)
        set_text_content(self.transcript_text, record.transcript)
        set_text_content(self.followup_text, record.follow_up_question)
        self.prev_button.setEnabled(engine.current_index > 0)
        self.next_button.setEnabled(engine.current_index < engine.question_count - 1)
        self._restore_coach_panel(record)
        self._refresh_coverage()

    def _restore_coach_panel(self, record) -> None:
        """Show the saved verdict when returning to a question already scored."""
        engine = self.ctx.engine
        if engine is None:
            return
        if not record.evaluation:
            self.coach_panel.set_message(tr("ws.coach_idle"))
            self.probe_button.setEnabled(False)
            self.ctx.last_score_var.set("—")
            return
        insight = insight_from_record(record, engine.language or "English")
        self.coach_panel.show_insight(
            insight,
            engine.language or "English",
            competency_key=engine.current_competency,
            stage=engine.current_stage,
        )
        self.ctx.last_score_var.set(str(insight.evaluation.overall))
        self.probe_button.setEnabled(insight.has_probe)

    def _refresh_coverage(self) -> None:
        engine = self.ctx.engine
        if engine is None:
            self.ctx.coverage_var.set("0 / 0")
            return
        coverage = engine.coverage()
        covered = sum(1 for count in coverage.values() if count)
        self.ctx.coverage_var.set(f"{covered} / {max(1, len(coverage))}")

    def save_current_memo(self) -> None:
        engine = self.ctx.engine
        if engine is None:
            return
        engine.set_current_memo(self.memo_text.toPlainText())
        engine.session.set_transcript(engine.current_index, self.transcript_text.toPlainText())
        engine.session.set_follow_up_question(engine.current_index, self.followup_text.toPlainText())
        engine.session.save()

    def _get_provider(self) -> QwenTTSProvider:
        if self.ctx.engine is None:
            raise RuntimeError("Session has not started.")
        if self.ctx.provider is None:
            self.ctx.apply_config_from_ui()
            self.ctx.provider = QwenTTSProvider(self.ctx.config_model, self.ctx.engine.session.audio_cache_dir)
        return self.ctx.provider

    def _speak_current(self, repeat: bool) -> None:
        ctx = self.ctx
        if ctx.engine is None or ctx.tts_running:
            return
        ctx.apply_config_from_ui()
        self.save_current_memo()
        provider = self._get_provider()
        token = ctx.tts_token + 1
        ctx.tts_token = token
        ctx.tts_running = True
        ctx.set_state(SessionState.SPEAKING)
        ctx.runtime_badge_var.set(tr("badge.session_speaking"))
        self.repeat_button.setEnabled(False)
        self.video_player.start()
        if ctx.config_model.tts_backend == QWEN_BACKEND:
            ctx.status_var.set(tr("ws.tts_generating"))
            QTimer.singleShot(15000, lambda: self._show_slow_tts_notice(token))
        else:
            ctx.status_var.set(tr("ws.tts_sapi_playing"))

        engine = ctx.engine
        run_bg(
            self,
            lambda: engine.speak_current(provider, repeat=repeat),
            on_done=lambda result: self._on_tts_done(token, result),
            on_error=lambda exc: self._on_tts_error(token, exc),
            name="tts-speak",
        )

    def _show_slow_tts_notice(self, token: int) -> None:
        if token == self.ctx.tts_token and self.ctx.tts_running:
            self.ctx.status_var.set(tr("ws.tts_slow"))

    def _on_tts_done(self, token: int, result) -> None:
        ctx = self.ctx
        if token != ctx.tts_token:
            return
        ctx.tts_running = False
        self.repeat_button.setEnabled(True)
        self.video_player.stop()
        if result.warning:
            ctx.status_var.set(tr("ws.tts_fallback_played", name=result.wav_path.name))
            ctx.runtime_badge_var.set(tr("badge.fallback"))
            ctx.warning_var.set(result.warning)
            messages.warning(self.window, tr("ws.tts_fallback_title"), result.warning)
        else:
            ctx.status_var.set(tr("ws.answer_timing", backend=result.backend, name=result.wav_path.name))
            ctx.runtime_badge_var.set(tr("badge.session_answering"))
            ctx.warning_var.set(tr("ws.answer_timing_hint"))
        ctx.set_state(SessionState.ANSWERING)
        self._render_current_question()
        self._prefetch_next_question()

    def _prefetch_next_question(self) -> None:
        """Generate the next question's audio while the candidate answers.

        Synthesis costs more than the audio it produces (about 13s on CUDA and
        27s on CPU for a 4s sentence), so doing it now hides the whole wait
        inside the answer window; the cache makes the next Next instant.
        """
        ctx = self.ctx
        engine = ctx.engine
        if engine is None or ctx.tts_running or self._prefetching:
            return
        if engine.next_question_audio() is None:
            return
        provider = ctx.provider
        if provider is None:
            return

        self._prefetching = True

        def finished(_result=None) -> None:
            self._prefetching = False

        run_bg(
            self,
            lambda: engine.prefetch_next_question(provider),
            on_done=finished,
            on_error=lambda _exc: finished(),
            name="tts-prefetch",
        )

    def _on_tts_error(self, token: int, exc: Exception) -> None:
        ctx = self.ctx
        if token != ctx.tts_token:
            return
        ctx.tts_running = False
        ctx.set_state(SessionState.ERROR)
        ctx.runtime_badge_var.set(tr("badge.session_error"))
        ctx.warning_var.set(str(exc))
        self.repeat_button.setEnabled(True)
        self.video_player.stop()
        ctx.status_var.set(tr("ws.tts_error_status"))
        messages.error(self.window, tr("ws.tts_error_title"), str(exc))

    def _stop_tts(self) -> None:
        ctx = self.ctx
        ctx.tts_token += 1
        ctx.tts_running = False
        ctx.set_state(SessionState.ANSWERING if ctx.engine is not None else SessionState.IDLE)
        ctx.runtime_badge_var.set(tr("badge.session_answering") if ctx.engine is not None else tr("badge.ready"))
        self.repeat_button.setEnabled(True)
        if ctx.provider is not None:
            ctx.provider.stop()
        self.video_player.stop()
        if ctx.engine is not None:
            ctx.engine.session.start_answer(ctx.engine.current_index)
            ctx.engine.session.save()
        ctx.status_var.set(tr("ws.tts_stopped"))

    # -- recording / STT ------------------------------------------------------------

    def _start_recording(self) -> None:
        ctx = self.ctx
        if ctx.engine is None or ctx.recording:
            return
        self.save_current_memo()
        ctx.engine.session.start_answer(ctx.engine.current_index)
        index = ctx.engine.current_index + 1
        path = ctx.engine.session.answers_dir / f"answer_{index:03d}.wav"
        try:
            ctx.recorder.start(path, input_device=input_device_id_from_label(ctx.input_device_var.get()))
        except STTError as exc:
            messages.error(self.window, tr("ws.record_failed_title"), str(exc))
            ctx.set_state(SessionState.ERROR)
            return

        ctx.recording = True
        ctx.set_state(SessionState.RECORDING)
        ctx.runtime_badge_var.set(tr("badge.session_recording"))
        ctx.warning_var.set(tr("ws.recording_hint"))
        ctx.recording_path = path
        self.record_button.setEnabled(False)
        self.stop_record_button.setEnabled(True)
        ctx.status_var.set(tr("ws.recording"))
        ctx.engine.session.set_answer_audio_path(ctx.engine.current_index, path)
        ctx.engine.session.save()

    def _stop_recording_and_transcribe(self) -> None:
        ctx = self.ctx
        if ctx.engine is None or not ctx.recording:
            return
        try:
            path = ctx.recorder.stop()
        except STTError as exc:
            ctx.recording = False
            ctx.recording_path = None
            self.record_button.setEnabled(True)
            self.stop_record_button.setEnabled(False)
            ctx.set_state(SessionState.ERROR)
            ctx.runtime_badge_var.set(tr("badge.session_error"))
            ctx.warning_var.set(str(exc))
            messages.error(self.window, tr("ws.record_stop_failed_title"), str(exc))
            return

        ctx.recording = False
        ctx.set_state(SessionState.TRANSCRIBING)
        ctx.runtime_badge_var.set(tr("badge.session_stt"))
        ctx.warning_var.set(tr("ws.transcribing_hint"))
        ctx.recording_path = path
        self.record_button.setEnabled(True)
        self.stop_record_button.setEnabled(False)
        ctx.engine.session.set_answer_audio_path(ctx.engine.current_index, path)
        ctx.engine.finish_current_answer()
        ctx.status_var.set(tr("ws.transcribing"))
        index = ctx.engine.current_index
        question = ctx.engine.current_record.clean_question
        language = detect_language(question)

        run_bg(
            self,
            lambda: ctx.transcriber.transcribe(path, language=language),
            on_done=lambda result: self._on_transcript_done(index, result.text),
            on_error=self._on_transcript_error,
            name="stt-transcribe",
        )

    def _on_transcript_done(self, index: int, transcript: str) -> None:
        ctx = self.ctx
        if ctx.engine is None:
            return
        ctx.engine.session.set_transcript(index, transcript)
        ctx.engine.session.save()
        if index == ctx.engine.current_index:
            set_text_content(self.transcript_text, transcript)
        ctx.status_var.set(tr("ws.transcript_done"))
        ctx.runtime_badge_var.set(tr("badge.session_answering"))
        ctx.warning_var.set(tr("ws.transcript_hint"))
        ctx.set_state(SessionState.ANSWERING)
        if ctx.config_model.enable_live_scoring and transcript.strip():
            self._evaluate_answer()

    def _on_transcript_error(self, exc: Exception) -> None:
        ctx = self.ctx
        ctx.status_var.set(tr("ws.transcript_failed"))
        ctx.set_state(SessionState.ERROR)
        ctx.runtime_badge_var.set(tr("badge.session_error"))
        ctx.warning_var.set(str(exc))
        messages.error(self.window, tr("ws.stt_error_title"), str(exc))

    # -- analysis --------------------------------------------------------------

    def _evaluate_answer(self) -> None:
        """Score the current answer and work out whether to probe."""
        ctx = self.ctx
        engine = ctx.engine
        if engine is None or self._evaluating:
            return
        ctx.apply_config_from_ui()
        self.save_current_memo()

        record = engine.current_record
        transcript = (self.transcript_text.toPlainText().strip() or record.memo).strip()
        if not transcript:
            self.coach_panel.set_message(tr("ws.coach_empty_answer"), "warning")
            self.detail_tabs.setCurrentIndex(self.coach_tab_index)
            return

        question = record.clean_question
        language = engine.language or detect_language(question)
        index = engine.current_index
        chain = ctx.ai_chain()

        self._evaluating = True
        self.evaluate_button.setEnabled(False)
        self.coach_panel.set_running()
        self.detail_tabs.setCurrentIndex(self.coach_tab_index)
        ctx.status_var.set(tr("ws.coach_running"))
        ctx.runtime_badge_var.set(tr("badge.session_scoring"))

        run_bg(
            self,
            lambda: analyze_answer_turn(
                question,
                transcript,
                language,
                chain=chain,
                competency_key=engine.competency_for(index),
                interview_type=ctx.config_model.interview_type,
                question_index=index + 1,
                duration_seconds=engine.current_answer_seconds(),
                probe_depth=engine.probe_depth(index),
                max_probe_depth=ctx.config_model.max_probe_depth,
                probing_enabled=ctx.config_model.enable_adaptive_probing,
                effort=ctx.ai_effort(),
                role=ctx.config_model.target_role,
            ),
            on_done=lambda insight: self._on_insight(index, insight),
            on_error=self._on_evaluate_error,
            name="answer-analysis",
        )

    def _on_insight(self, index: int, insight: AnswerInsight) -> None:
        ctx = self.ctx
        engine = ctx.engine
        self._evaluating = False
        self.evaluate_button.setEnabled(True)
        if engine is None:
            return

        engine.record_insight(insight, index=index)
        language = engine.language or "English"
        if index == engine.current_index:
            self.coach_panel.show_insight(
                insight,
                language,
                competency_key=engine.competency_for(index),
                stage=engine.current_stage,
            )
            if insight.has_probe:
                set_text_content(self.followup_text, insight.probe.question)
        self.probe_button.setEnabled(insight.has_probe)
        ctx.last_score_var.set(str(insight.evaluation.overall))
        self._refresh_coverage()
        ctx.status_var.set(tr("ws.eval_done", score=insight.evaluation.overall))
        ctx.runtime_badge_var.set(tr("badge.session_answering"))
        ctx.set_state(SessionState.ANSWERING)
        if insight.has_probe and ctx.config_model.auto_speak_probe:
            self._speak_follow_up()

    def _on_evaluate_error(self, exc: Exception) -> None:
        self._evaluating = False
        self.evaluate_button.setEnabled(True)
        logger.exception("Answer analysis failed.", exc_info=exc)
        self.coach_panel.set_message(f"{tr('ws.eval_failed')}\n{exc}", "warning")
        self.ctx.status_var.set(tr("ws.eval_failed"))
        self.ctx.runtime_badge_var.set(tr("badge.session_error"))

    def _ask_probe(self) -> None:
        """Put the suggested follow-up in front of the candidate."""
        probe_text = self.followup_text.toPlainText().strip()
        if not probe_text:
            return
        self.ctx.status_var.set(tr("ws.probe_asked"))
        self._speak_follow_up()

    def _open_report(self) -> None:
        self.window.generate_report()

    # -- follow-up ------------------------------------------------------------

    def _generate_follow_up(self) -> None:
        ctx = self.ctx
        engine = ctx.engine
        if engine is None:
            return
        ctx.apply_config_from_ui()
        self.save_current_memo()
        record = engine.current_record
        transcript = self.transcript_text.toPlainText().strip() or record.memo
        question = record.clean_question
        language = engine.language or detect_language(question)
        index = engine.current_index
        chain = ctx.ai_chain()
        ctx.status_var.set(tr("ws.followup_generating"))
        ctx.set_state(SessionState.FOLLOW_UP_GENERATING)
        ctx.runtime_badge_var.set(tr("badge.session_followup"))
        ctx.warning_var.set(tr("ws.followup_hint"))

        run_bg(
            self,
            lambda: follow_up_for_answer(
                question,
                transcript,
                language,
                chain=chain,
                competency_key=engine.competency_for(index),
                depth=engine.probe_depth(index) + 1,
            ),
            on_done=lambda probe: self._on_follow_up_done(probe.question),
            name="follow-up",
        )

    def _on_follow_up_done(self, follow_up: str) -> None:
        ctx = self.ctx
        if ctx.engine is None:
            return
        ctx.engine.session.set_follow_up_question(ctx.engine.current_index, follow_up)
        ctx.engine.session.save()
        set_text_content(self.followup_text, follow_up)
        ctx.status_var.set(tr("ws.followup_done"))
        ctx.runtime_badge_var.set(tr("badge.session_answering"))
        ctx.warning_var.set(tr("ws.followup_edit_hint"))
        ctx.set_state(SessionState.ANSWERING)

    def _speak_follow_up(self) -> None:
        ctx = self.ctx
        if ctx.engine is None or ctx.tts_running:
            return
        ctx.apply_config_from_ui()
        self.save_current_memo()
        follow_up = self.followup_text.toPlainText().strip()
        if not follow_up:
            messages.warning(self.window, tr("ws.followup_missing_title"), tr("ws.followup_missing_body"))
            return

        provider = self._get_provider()
        token = ctx.tts_token + 1
        ctx.tts_token = token
        ctx.tts_running = True
        ctx.set_state(SessionState.SPEAKING)
        self.repeat_button.setEnabled(False)
        self.video_player.start()
        ctx.status_var.set(tr("ws.followup_playing"))
        session_id = ctx.engine.session.session_id
        current_index = ctx.engine.current_index

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
        ctx = self.ctx
        if token != ctx.tts_token:
            return
        ctx.tts_running = False
        self.repeat_button.setEnabled(True)
        self.video_player.stop()
        ctx.status_var.set(tr("ws.followup_played"))
        ctx.set_state(SessionState.ANSWERING)

    # -- diagnostics / utilities ------------------------------------------------------------

    def _test_system_sound(self) -> None:
        try:
            provider = (
                self._get_provider()
                if self.ctx.engine is not None
                else QwenTTSProvider(self.ctx.config_model, self.ctx.config_model.sessions_root / "_diagnostics")
            )
            provider.play_system_beep()
            self.ctx.status_var.set(tr("ws.beep_done"))
        except Exception as exc:  # noqa: BLE001 - user-facing feedback
            messages.error(self.window, tr("ws.beep_failed_title"), str(exc))

    def _diagnose_tts(self) -> None:
        self.ctx.apply_config_from_ui()
        self.diagnostics_button.setEnabled(False)
        self.ctx.status_var.set(tr("app.diag_checking"))
        run_bg(
            self,
            lambda: collect_runtime_diagnostics(self.ctx.config_model),
            on_done=self._on_diagnose_report,
            on_error=self._on_diagnose_error,
            name="tts-diagnostics",
        )

    def _on_diagnose_error(self, exc: Exception) -> None:
        self.diagnostics_button.setEnabled(True)
        messages.error(self.window, tr("ws.diagnostics_title"), str(exc))

    def _on_diagnose_report(self, report) -> None:
        self.diagnostics_button.setEnabled(True)
        self.ctx.runtime_report = report
        self.ctx.diagnostic_status_var.set(report.summary())
        self.ctx.status_var.set(report.summary())
        if self.ctx.tts_backend_var.get() == QWEN_BACKEND and not self.ctx.selected_model_installed():
            if messages.ask_yes_no(
                self.window,
                tr("ws.diagnostics_title"),
                tr("ws.diagnostics_download_ask", report=diagnostics_text(report)),
            ):
                self.window.open_model_download(self.ctx.model_var.get())
            return
        messages.info(self.window, tr("ws.diagnostics_title"), diagnostics_text(report))

    # -- navigation ------------------------------------------------------------

    def _next_question(self) -> None:
        ctx = self.ctx
        if ctx.engine is None:
            return
        if ctx.recording:
            messages.warning(self.window, tr("ws.recording_title"), tr("ws.stop_before_next"))
            return
        self._stop_tts()
        self.save_current_memo()
        ctx.engine.move_next()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _previous_question(self) -> None:
        ctx = self.ctx
        if ctx.engine is None:
            return
        if ctx.recording:
            messages.warning(self.window, tr("ws.recording_title"), tr("ws.stop_before_prev"))
            return
        self._stop_tts()
        self.save_current_memo()
        ctx.engine.move_previous()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _restart_session(self) -> None:
        ctx = self.ctx
        if ctx.engine is None:
            return
        if ctx.recording:
            messages.warning(self.window, tr("ws.recording_title"), tr("ws.stop_before_restart"))
            return
        self._stop_tts()
        self.save_current_memo()
        ctx.engine.restart()
        ctx.provider = QwenTTSProvider(ctx.config_model, ctx.engine.session.audio_cache_dir)
        self._render_current_question()
        ctx.status_var.set(tr("ws.session_restarted"))
        self._speak_current(repeat=False)

    def _open_session_folder(self) -> None:
        if self.ctx.engine is None:
            return
        self.save_current_memo()
        path = self.ctx.engine.session.session_dir
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        else:
            messages.info(self.window, tr("ws.session_folder_title"), str(path))

    def _open_session_browser(self) -> None:
        active_session_id = self.ctx.engine.session.session_id if self.ctx.engine is not None else None
        dialog = SessionBrowserDialog(self.window, self.ctx.config_model.sessions_root, active_session_id=active_session_id)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()

    # -- teardown ------------------------------------------------------------

    def shutdown_widgets(self) -> None:
        self.video_player.shutdown()
