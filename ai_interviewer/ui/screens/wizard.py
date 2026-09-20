from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCheckBox,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ai_interviewer import __version__
from ai_interviewer.config import (
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_OFFLINE,
    AI_PROVIDER_OLLAMA,
    QWEN_BACKEND,
)
from ai_interviewer.default_questions import (
    default_questions_text,
    interview_type_label,
    interview_type_options,
    question_set_for_interview_type,
)
from ai_interviewer.i18n import SUPPORTED_UI_LANGUAGES, tr, ui_language_label
from ai_interviewer.model_downloader import approx_download_bytes, format_bytes
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.tts_catalog import (
    default_speaker_for_language,
    model_option_by_id,
    native_language_label,
    speaker_by_id,
    speaker_description,
    speaker_label,
    speaker_options,
    tts_model_options,
)
from ai_interviewer.ui.context import AppContext
from ai_interviewer.ui.dialogs import messages
from ai_interviewer.ui.dialogs.model_download import ModelDownloadDialog
from ai_interviewer.ui.state import Prop, bind_label
from ai_interviewer.ui.theme import manager as theme_manager
from ai_interviewer.ui.widgets import cards
from ai_interviewer.ui.widgets.binding import bind_line_edit
from ai_interviewer.ui.widgets.buttons import IconButton, SegButton
from ai_interviewer.ui.widgets.choice_card import ChoiceCard
from ai_interviewer.ui.widgets.signal_widget import SignalWidget
from ai_interviewer.ui.widgets.step_rail import StepRail
from ai_interviewer.ui.widgets.text_edit import make_text_edit, set_text_content
from ai_interviewer.ui.workers import run_bg

if TYPE_CHECKING:
    from ai_interviewer.ui.main_window import MainWindow


logger = logging.getLogger(__name__)

SETUP_STEPS = (
    "language",
    "model",
    "speaker",
    "type",
    "coach",
    "questions",
    "sound",
    "preferences",
    "review",
)


class WizardScreen(QWidget):
    """First-run / setup flow: one decision per step on a left progress rail."""

    def __init__(self, ctx: AppContext, window: "MainWindow") -> None:
        super().__init__()
        self.ctx = ctx
        self.window = window
        self.setup_questions_text = None  # QPlainTextEdit while the custom editor is visible

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)

        hero = cards.frame("hero")
        outer.addWidget(hero)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(26)

        # -- left rail ------------------------------------------------------
        rail = QWidget()
        rail.setFixedWidth(292)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 2, 0, 0)
        rail_layout.setSpacing(0)
        rail_layout.addWidget(cards.label("AI Interviewer", "display"))
        rail_layout.addSpacing(4)
        rail_layout.addWidget(cards.label(tr("wizard.rail_version", version=__version__), "railAccent"))
        rail_layout.addSpacing(16)
        rail_layout.addWidget(cards.label(tr("wizard.rail_tagline"), "railMuted", wrap=True))
        rail_layout.addSpacing(18)
        self.signal = SignalWidget(height=150, animated=True)
        rail_layout.addWidget(self.signal)
        rail_layout.addSpacing(18)
        self.step_rail = StepRail(self._setup_step_labels, self.ctx.setup_step_index)
        rail_layout.addWidget(self.step_rail, 1)
        hero_layout.addWidget(rail)

        # -- right stage ----------------------------------------------------
        stage = QWidget()
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(6, 6, 6, 6)
        stage_layout.setSpacing(0)
        hero_layout.addWidget(stage, 1)

        top = QHBoxLayout()
        badge = cards.bound_label(self.ctx.runtime_badge_var, "kicker")
        diag = cards.bound_label(self.ctx.diagnostic_status_var, "muted")
        top.addWidget(badge)
        top.addStretch(1)
        top.addWidget(diag)
        stage_layout.addLayout(top)
        stage_layout.addSpacing(20)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        stage_layout.addWidget(self.content, 1)

        nav = QHBoxLayout()
        self.back_button = IconButton(tr("common.back"), kind="tool")
        self.next_button = IconButton(tr("common.next"), kind="primary")
        self.back_button.clicked.connect(self._setup_back)
        self.next_button.clicked.connect(self._setup_next)
        nav.addWidget(self.back_button)
        nav.addStretch(1)
        nav.addWidget(self.next_button)
        stage_layout.addSpacing(22)
        stage_layout.addLayout(nav)

        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self._setup_next)

        self._render_setup_step(animated=False)

    # -- steps ---------------------------------------------------------------

    @property
    def _setup_step_labels(self) -> tuple[str, ...]:
        return (
            tr("wizard.step.language"),
            tr("wizard.step.model"),
            tr("wizard.step.speaker"),
            tr("wizard.step.interview"),
            tr("wizard.step_coach"),
            tr("wizard.step.questions"),
            tr("wizard.step.sound"),
            tr("wizard.step.options"),
            tr("wizard.step.review"),
        )

    def _render_setup_step(self, animated: bool = True) -> None:
        self.setup_questions_text = None
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Detach immediately: deleteLater alone leaves the old step
                # painted (still a child) until the event loop runs.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        index = self.ctx.setup_step_index
        self.step_rail.set_current(index)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        progress = QHBoxLayout()
        progress.addWidget(cards.label(tr("wizard.step_prefix", number=f"{index + 1:02d}"), "kicker"))
        progress.addSpacing(10)
        progress.addWidget(cards.label(self._setup_step_labels[index], "muted"))
        progress.addStretch(1)
        progress.addWidget(cards.label(f"{index + 1} / {len(SETUP_STEPS)}", "muted"))
        body_layout.addLayout(progress)
        body_layout.addSpacing(18)

        step_body = QWidget()
        step_layout = QVBoxLayout(step_body)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(0)
        step = SETUP_STEPS[index]
        getattr(self, f"_build_setup_{step}")(step_layout)
        body_layout.addWidget(step_body, 1)

        self.content_layout.addWidget(body)
        self.back_button.setEnabled(index > 0)
        self.next_button.setText(tr("wizard.start_interview") if step == "review" else tr("common.next"))
        if animated:
            self._animate_step_in(body)

    def _animate_step_in(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(150)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _setup_back(self) -> None:
        if self.ctx.setup_step_index > 0:
            self.ctx.setup_step_index -= 1
            self._render_setup_step()

    def _setup_next(self) -> None:
        if not self._validate_setup_step():
            return
        if self.ctx.setup_step_index >= len(SETUP_STEPS) - 1:
            self._begin_interview_from_setup()
            return
        self.ctx.setup_step_index += 1
        self._render_setup_step()

    def _select_and_continue(self, variable: Prop, value: str) -> None:
        variable.set(value)
        if variable is self.ctx.interview_language_var:
            self._sync_language_selection()
        if variable is self.ctx.model_var:
            self.ctx.provider = None
            self.ctx.preload_provider = None
        if variable is self.ctx.interview_type_var:
            self.ctx.question_set_var.set(
                question_set_for_interview_type(self.ctx.interview_language_var.get(), value)
            )
        QTimer.singleShot(80, self._setup_next)

    # -- step bodies -----------------------------------------------------------

    def _build_setup_language(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.language_title"), tr("wizard.language_sub")))
        layout.addSpacing(18)
        choices = QGridLayout()
        choices.setSpacing(10)
        self._choice_button(choices, "한국어", tr("wizard.lang_ko_desc"), 0, 0, self.ctx.interview_language_var, "Korean")
        self._choice_button(choices, "English", tr("wizard.lang_en_desc"), 0, 1, self.ctx.interview_language_var, "English")
        layout.addLayout(choices)

        ui_row = QHBoxLayout()
        ui_row.setSpacing(14)
        ui_row.addWidget(cards.label(tr("wizard.ui_language_title"), "section"))
        group = QButtonGroup(self)
        for language in SUPPORTED_UI_LANGUAGES:
            radio = QRadioButton(ui_language_label(language))
            radio.setChecked(language == self.ctx.ui_language_var.get())
            radio.toggled.connect(
                lambda checked, lang=language: self.ctx.set_ui_language(lang) if checked else None
            )
            group.addButton(radio)
            ui_row.addWidget(radio)
        ui_row.addStretch(1)
        layout.addSpacing(22)
        layout.addLayout(ui_row)
        layout.addStretch(1)

    def _build_setup_model(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.model_title"), tr("wizard.model_sub")))
        layout.addSpacing(18)
        choices = QGridLayout()
        choices.setSpacing(10)
        for index, option in enumerate(tts_model_options(self.ctx.config_model)):
            if option.installed:
                installed = tr("wizard.model_installed")
            else:
                size = approx_download_bytes(self.ctx.config_model.model_root, option.model_id)
                installed = tr("wizard.model_not_installed", size=format_bytes(size))
            tone = tr("wizard.tone_on") if option.supports_tone_control else tr("wizard.tone_limited")
            suffix = tr("wizard.recommended_suffix") if option.recommended else ""
            self._choice_button(
                choices,
                f"{option.display_name}{suffix}",
                f"{installed}\n{tone}\n{option.description}",
                0,
                index,
                self.ctx.model_var,
                option.model_id,
            )
        layout.addLayout(choices)
        if not self.ctx.selected_model_installed():
            download_row = QHBoxLayout()
            download_row.addWidget(cards.label(tr("wizard.model_download_hint"), "muted", wrap=True), 1)
            download_button = IconButton(tr("wizard.download_now"), icon_name="download", kind="secondary")
            download_button.clicked.connect(lambda: self._open_model_download(self.ctx.model_var.get()))
            download_row.addWidget(download_button)
            layout.addSpacing(14)
            layout.addLayout(download_row)
        layout.addStretch(1)

    def _open_model_download(self, model_id: str, on_complete=None) -> None:
        def completed() -> None:
            self.ctx.provider = None
            self.ctx.preload_provider = None
            if SETUP_STEPS[self.ctx.setup_step_index] == "model":
                self._render_setup_step(animated=False)
            self.ctx.status_var.set(tr("wizard.model_download_done"))
            if on_complete is not None:
                on_complete()

        dialog = ModelDownloadDialog(self.window, self.ctx.config_model, model_id, on_complete=completed)
        dialog.open()

    def _build_setup_speaker(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.speaker_title"), tr("wizard.speaker_sub")))
        layout.addSpacing(18)
        choices = QGridLayout()
        choices.setSpacing(10)
        for column in range(3):
            choices.setColumnStretch(column, 1)
        for index, speaker in enumerate(speaker_options(self.ctx.interview_language_var.get())):
            row, column = divmod(index, 3)
            title = speaker.display_name
            if self.ctx.interview_language_var.get() in speaker.recommended_languages:
                title += tr("wizard.recommended_suffix")
            self._choice_button(
                choices,
                title,
                f"{native_language_label(speaker)}\n{speaker_description(speaker)}",
                row,
                column,
                self.ctx.selected_speaker_var,
                speaker.speaker_id,
            )
        layout.addLayout(choices)
        layout.addStretch(1)

    def _build_setup_type(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.type_title"), tr("wizard.type_sub")))
        layout.addSpacing(18)
        choices = QGridLayout()
        choices.setSpacing(10)
        for column in range(2):
            choices.setColumnStretch(column, 1)
        descriptions = {
            "hr": tr("wizard.type_desc_hr"),
            "star": tr("wizard.type_desc_star"),
            "role": tr("wizard.type_desc_role"),
            "technical": tr("wizard.type_desc_technical"),
        }
        for index, (interview_type, label) in enumerate(interview_type_options(self.ctx.interview_language_var.get())):
            row, column = divmod(index, 2)
            self._choice_button(
                choices,
                label,
                descriptions.get(interview_type, ""),
                row,
                column,
                self.ctx.interview_type_var,
                interview_type,
            )
        layout.addLayout(choices)
        layout.addStretch(1)

    def _build_setup_questions(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.questions_title"), tr("wizard.questions_sub")))
        layout.addSpacing(18)
        source_row = QHBoxLayout()
        source_row.setSpacing(18)
        default_radio = QRadioButton(tr("wizard.use_default_questions"))
        custom_radio = QRadioButton(tr("wizard.paste_questions"))
        default_radio.setChecked(self.ctx.question_source_var.get() == "default")
        custom_radio.setChecked(self.ctx.question_source_var.get() == "custom")
        default_radio.toggled.connect(lambda checked: self._on_question_source_changed("default") if checked else None)
        custom_radio.toggled.connect(lambda checked: self._on_question_source_changed("custom") if checked else None)
        source_row.addWidget(default_radio)
        source_row.addWidget(custom_radio)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        selected_set = question_set_for_interview_type(
            self.ctx.interview_language_var.get(), self.ctx.interview_type_var.get()
        )
        layout.addSpacing(12)
        layout.addWidget(cards.label(tr("wizard.default_pack", set_name=selected_set), "subtitle"))
        layout.addSpacing(8)
        if self.ctx.question_source_var.get() == "custom":
            editor = make_text_edit(min_lines=12)
            if self.ctx.setup_custom_questions:
                set_text_content(editor, self.ctx.setup_custom_questions)
            else:
                content = self.window.workspace_question_text().strip()
                if content:
                    set_text_content(editor, content)
            self.setup_questions_text = editor
            layout.addWidget(editor, 1)
        else:
            preview = make_text_edit(read_only=True, min_lines=12)
            set_text_content(
                preview,
                default_questions_text(self.ctx.interview_language_var.get(), selected_set),
            )
            layout.addWidget(preview, 1)

    def _on_question_source_changed(self, source: str) -> None:
        if self.setup_questions_text is not None:
            self.ctx.setup_custom_questions = self.setup_questions_text.toPlainText().strip()
        if source == self.ctx.question_source_var.get():
            return
        self.ctx.question_source_var.set(source)
        self._render_setup_step()

    def _build_setup_sound(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.sound_title"), tr("wizard.sound_sub")))
        layout.addSpacing(18)
        model = model_option_by_id(self.ctx.config_model, self.ctx.model_var.get())
        speaker = speaker_by_id(self.ctx.selected_speaker_var.get())
        layout.addWidget(SignalWidget(height=118, compact=True))

        summary = cards.frame("subtle")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setHorizontalSpacing(14)
        summary_layout.setVerticalSpacing(8)
        summary_layout.setColumnStretch(1, 1)
        summary_layout.addWidget(cards.label(tr("wizard.sound_model_label").upper(), "metricLabel"), 0, 0)
        summary_layout.addWidget(cards.label(model.display_name, "status"), 0, 1)
        summary_layout.addWidget(cards.label(tr("wizard.sound_speaker_label").upper(), "metricLabel"), 1, 0)
        summary_layout.addWidget(cards.label(speaker_label(speaker), "status", wrap=True), 1, 1)
        layout.addSpacing(14)
        layout.addWidget(summary)

        status = cards.bound_label(self.ctx.sound_test_status_var, "warning", wrap=True)
        layout.addSpacing(16)
        layout.addWidget(status)

        test_row = QHBoxLayout()
        test_button = IconButton(tr("wizard.run_sound_test"), icon_name="volume-2", kind="primary")
        test_button.clicked.connect(self._run_setup_sound_test)
        test_row.addWidget(test_button)
        test_row.addStretch(1)
        layout.addSpacing(18)
        layout.addLayout(test_row)

        reminder = QCheckBox(tr("wizard.sound_keep_reminder"))
        reminder.setChecked(self.ctx.sound_test_required_var.get())
        reminder.toggled.connect(self.ctx.sound_test_required_var.set)
        layout.addSpacing(16)
        layout.addWidget(reminder)
        layout.addStretch(1)

    def _build_setup_preferences(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.pref_title"), tr("wizard.pref_sub")))
        layout.addSpacing(18)
        stt = QCheckBox(tr("wizard.pref_stt"))
        stt.setChecked(self.ctx.enable_stt_var.get())
        stt.toggled.connect(self.ctx.enable_stt_var.set)
        layout.addWidget(stt)

        fallback = QCheckBox(tr("wizard.pref_fallback"))
        fallback.setChecked(self.ctx.allow_fallback_var.get())
        fallback.toggled.connect(self.ctx.allow_fallback_var.set)
        layout.addSpacing(12)
        layout.addWidget(fallback)

        followup_row = QHBoxLayout()
        followup_row.setSpacing(10)
        followup_row.addWidget(cards.label(tr("wizard.pref_followup"), "section"))
        combo = QComboBox()
        combo.addItems(("Auto", "Ollama", "Rules"))
        combo.setCurrentText(self.ctx.followup_provider_var.get())
        combo.currentTextChanged.connect(self.ctx.followup_provider_var.set)
        followup_row.addWidget(combo, 1)
        layout.addSpacing(18)
        layout.addLayout(followup_row)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(10)
        theme_row.addWidget(cards.label(tr("ws.set_theme"), "section"))
        theme_row.addWidget(build_theme_selector(self))
        theme_row.addStretch(1)
        layout.addSpacing(18)
        layout.addLayout(theme_row)
        layout.addStretch(1)

    def _build_setup_coach(self, layout: QVBoxLayout) -> None:
        """Pick the analysis engine, and take cloud consent here rather than
        silently at the first scored answer."""
        layout.addWidget(cards.section_header(tr("wizard.coach_title"), tr("wizard.coach_body")))
        layout.addSpacing(18)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        options = (
            (AI_PROVIDER_OFFLINE, tr("wizard.coach_offline"), tr("wizard.coach_offline_body")),
            (AI_PROVIDER_OLLAMA, tr("wizard.coach_local"), tr("wizard.coach_local_body")),
            (AI_PROVIDER_CLAUDE, tr("wizard.coach_cloud"), tr("wizard.coach_cloud_body")),
        )
        for column, (value, title, description) in enumerate(options):
            card = ChoiceCard(title, description, selected=self.ctx.ai_provider_var.get() == value)
            card.clicked.connect(lambda v=value: self._select_coach_provider(v))
            grid.addWidget(card, 0, column)
        layout.addLayout(grid)

        layout.addSpacing(18)
        role_box = cards.frame("subtle")
        role_layout = QGridLayout(role_box)
        role_layout.setContentsMargins(16, 14, 16, 14)
        role_layout.setHorizontalSpacing(12)
        role_layout.setVerticalSpacing(8)
        role_layout.setColumnStretch(1, 1)
        role_layout.addWidget(cards.label(tr("wizard.coach_role"), "metricLabel"), 0, 0)
        role_edit = QLineEdit()
        bind_line_edit(role_edit, self.ctx.target_role_var)
        role_layout.addWidget(role_edit, 0, 1)
        role_layout.addWidget(cards.label(tr("wizard.coach_role_hint"), "muted", wrap=True), 1, 0, 1, 2)
        layout.addWidget(role_box)
        layout.addStretch(1)

    def _select_coach_provider(self, provider: str) -> None:
        if provider == AI_PROVIDER_CLAUDE and not self.ctx.cloud_ai_var.get():
            if not messages.ask_yes_no(
                self.window,
                tr("ws.cloud_consent_title"),
                tr("ws.cloud_consent_body"),
            ):
                self.ctx.status_var.set(tr("ws.cloud_declined"))
                self._select_and_continue(self.ctx.ai_provider_var, AI_PROVIDER_OFFLINE)
                return
            self.ctx.cloud_ai_var.set(True)
        self._select_and_continue(self.ctx.ai_provider_var, provider)

    def _build_setup_review(self, layout: QVBoxLayout) -> None:
        layout.addWidget(cards.section_header(tr("wizard.review_title"), tr("wizard.review_sub")))
        layout.addSpacing(18)
        body = cards.frame("subtle")
        body_layout = QGridLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setHorizontalSpacing(14)
        body_layout.setVerticalSpacing(8)
        body_layout.setColumnStretch(1, 1)
        selected_set = question_set_for_interview_type(
            self.ctx.interview_language_var.get(), self.ctx.interview_type_var.get()
        )
        rows = (
            (tr("wizard.step.language"), self.ctx.interview_language_var.get()),
            (tr("wizard.step.model"), model_option_by_id(self.ctx.config_model, self.ctx.model_var.get()).display_name),
            (tr("wizard.step.speaker"), speaker_label(speaker_by_id(self.ctx.selected_speaker_var.get()))),
            (
                tr("wizard.step.interview"),
                interview_type_label(self.ctx.interview_language_var.get(), self.ctx.interview_type_var.get()),
            ),
            (
                tr("wizard.step.questions"),
                tr("wizard.custom_questions") if self.ctx.question_source_var.get() == "custom" else selected_set,
            ),
            (
                tr("wizard.step_coach"),
                tr(f"ai.provider.{self.ctx.ai_provider_var.get()}"),
            ),
            (tr("wizard.step.sound"), self.ctx.sound_test_status_var.get()),
            (tr("wizard.review_stt"), tr("common.on") if self.ctx.enable_stt_var.get() else tr("common.off")),
            (tr("wizard.review_fallback"), tr("common.on") if self.ctx.allow_fallback_var.get() else tr("common.off")),
        )
        for row, (label, value) in enumerate(rows):
            body_layout.addWidget(cards.label(label, "metricLabel"), row, 0)
            body_layout.addWidget(cards.label(value, "status", wrap=True), row, 1)
        layout.addWidget(body)
        layout.addStretch(1)

    # -- choice helpers -----------------------------------------------------------

    def _choice_button(
        self,
        grid: QGridLayout,
        title: str,
        description: str,
        row: int,
        column: int,
        variable: Prop,
        value: str,
    ) -> None:
        card = ChoiceCard(title, description, selected=variable.get() == value)
        card.clicked.connect(lambda: self._select_and_continue(variable, value))
        grid.addWidget(card, row, column)

    # -- validation / flow -----------------------------------------------------------

    def _validate_setup_step(self) -> bool:
        step = SETUP_STEPS[self.ctx.setup_step_index]
        if step == "model" and self.ctx.tts_backend_var.get() == QWEN_BACKEND and not self.ctx.selected_model_installed():
            if messages.ask_yes_no(self.window, tr("wizard.model_missing_title"), tr("wizard.model_missing_body")):
                self._open_model_download(self.ctx.model_var.get())
            return False
        if step == "questions":
            self._apply_setup_questions()
            questions = parse_questions(self._setup_questions_content())
            if not questions:
                messages.warning(self.window, tr("wizard.no_questions_title"), tr("wizard.no_questions_body"))
                return False
        return True

    def _setup_questions_content(self) -> str:
        if self.ctx.question_source_var.get() == "custom" and self.setup_questions_text is not None:
            self.ctx.setup_custom_questions = self.setup_questions_text.toPlainText().strip()
            return self.ctx.setup_custom_questions
        if self.ctx.question_source_var.get() == "custom":
            return self.ctx.setup_custom_questions
        selected_set = question_set_for_interview_type(
            self.ctx.interview_language_var.get(), self.ctx.interview_type_var.get()
        )
        return default_questions_text(self.ctx.interview_language_var.get(), selected_set)

    def _apply_setup_questions(self) -> None:
        content = self._setup_questions_content()
        if self.window.workspace_screen is not None:
            self.window.workspace_screen.replace_question_text(content)

    def _sync_language_selection(self) -> None:
        language = self.ctx.interview_language_var.get()
        self.ctx.language_var.set(language)
        speaker = default_speaker_for_language(language)
        self.ctx.selected_speaker_var.set(speaker.speaker_id)
        if language == "Korean":
            self.ctx.korean_speaker_var.set(speaker.speaker_id)
        else:
            self.ctx.english_speaker_var.set(speaker.speaker_id)
        selected_set = question_set_for_interview_type(language, self.ctx.interview_type_var.get())
        self.ctx.question_set_var.set(selected_set)

    def _run_setup_sound_test(self) -> None:
        self.ctx.apply_config_from_ui(save=False)
        language = self.ctx.interview_language_var.get()
        speaker = self.ctx.selected_speaker_var.get()
        self.ctx.sound_test_passed = False
        self.ctx.sound_test_status_var.set(tr("wizard.sound_testing"))
        self.ctx.runtime_badge_var.set(tr("badge.sound_test"))
        provider = QwenTTSProvider(self.ctx.config_model, self.ctx.config_model.sessions_root / "_setup_sound_test")
        self.ctx.preload_provider = provider

        run_bg(
            self,
            lambda: provider.sound_test(language, speaker),
            on_done=self._on_setup_sound_test_done,
            on_error=self._on_setup_sound_test_error,
            name="setup-sound-test",
        )

    def _on_setup_sound_test_done(self, result) -> None:
        self.ctx.sound_test_passed = True
        self.ctx.sound_test_status_var.set(tr("wizard.sound_done", backend=result.backend, speaker=result.speaker))
        self.ctx.runtime_badge_var.set(tr("badge.ready"))

    def _on_setup_sound_test_error(self, exc: Exception) -> None:
        self.ctx.sound_test_passed = False
        self.ctx.sound_test_status_var.set(tr("wizard.sound_failed", error=exc))
        self.ctx.runtime_badge_var.set(tr("badge.warning"))
        messages.error(self.window, tr("wizard.sound_failed_title"), str(exc))

    def _begin_interview_from_setup(self) -> None:
        self._apply_setup_questions()
        self.ctx.apply_config_from_ui(save=True)
        if self.ctx.sound_test_required_var.get() and not self.ctx.sound_test_passed:
            if not messages.ask_yes_no(self.window, tr("wizard.sound_not_done_title"), tr("wizard.sound_not_done_ask")):
                return
        self.ctx.config_model.setup_completed = True
        self.ctx.config_model.save()
        workspace = self.window.show_workspace()
        workspace.replace_question_text(self._setup_questions_content())
        workspace.start_session()


def build_theme_selector(parent: QWidget) -> QWidget:
    """Segmented System/Light/Dark control bound to the ThemeManager."""
    holder = QWidget(parent)
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    group = QButtonGroup(holder)
    group.setExclusive(True)
    try:
        current_mode = theme_manager.manager().mode
    except RuntimeError:
        current_mode = "system"
    for mode, key, icon_name in (
        ("system", "theme.system", "monitor"),
        ("light", "theme.light", "sun"),
        ("dark", "theme.dark", "moon"),
    ):
        button = SegButton(tr(key), icon_name=icon_name)
        button.setChecked(mode == current_mode)
        button.clicked.connect(lambda _checked=False, m=mode: theme_manager.manager().set_mode(m))
        group.addButton(button)
        row.addWidget(button)
    return holder
