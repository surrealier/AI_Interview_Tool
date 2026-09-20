"""The report screen: what the interview established, after the interview.

Reads a `SessionReport` and renders it; it never computes a score itself. The
screen is rebuilt from scratch on every render so a regenerated report cannot
leave stale rows behind.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_interviewer.i18n import tr
from ai_interviewer.intelligence import (
    SessionReport,
    band_label,
    competency_label,
    dimension_label,
    render_html,
    render_json,
    render_markdown,
)
from ai_interviewer.intelligence.phrasebook import stage_label
from ai_interviewer.ui.context import AppContext
from ai_interviewer.ui.dialogs import messages
from ai_interviewer.ui.widgets import cards
from ai_interviewer.ui.widgets.buttons import IconButton
from ai_interviewer.ui.widgets.scoring import CompetencyRadar, ScoreBar, ScoreDial, chip


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_interviewer.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


class ReportScreen(QWidget):
    """Scorecard, competency profile, and per-question breakdown."""

    def __init__(self, ctx: AppContext, window: "MainWindow") -> None:
        super().__init__()
        self.ctx = ctx
        self.window = window
        self._report: SessionReport | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        self._build_header(outer)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll, 1)

        self.body = QWidget()
        self.body_layout = cards.vbox(self.body, 0, 12)
        self.scroll.setWidget(self.body)

        self.set_loading()

    # -- header --------------------------------------------------------------

    def _build_header(self, outer: QVBoxLayout) -> None:
        header = cards.frame("hero")
        outer.addWidget(header)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(cards.label(tr("report.title"), "display"))
        self.subtitle_label = cards.label("", "heroSubtitle")
        titles.addWidget(self.subtitle_label)
        layout.addLayout(titles, 1)

        self.regenerate_button = IconButton(tr("report.regenerate"), icon_name="refresh-cw", kind="tool")
        self.back_button = IconButton(tr("report.back"), icon_name="skip-back", kind="secondary")
        self.regenerate_button.clicked.connect(self._regenerate)
        self.back_button.clicked.connect(self._go_back)
        layout.addWidget(self.regenerate_button)
        layout.addWidget(self.back_button)

    # -- states --------------------------------------------------------------

    def set_loading(self) -> None:
        self._clear_body()
        self.subtitle_label.setText(tr("report.generating"))
        holder = cards.frame("card")
        layout = cards.vbox(holder, 24, 8)
        layout.addWidget(cards.label(tr("report.generating"), "title"))
        layout.addWidget(cards.label(tr("ws.coach_running"), "subtitle", wrap=True))
        self.body_layout.addWidget(holder)
        self.body_layout.addStretch(1)

    def set_failed(self, message: str) -> None:
        self._clear_body()
        self.subtitle_label.setText(tr("report.failed"))
        holder = cards.frame("card")
        layout = cards.vbox(holder, 24, 8)
        layout.addWidget(cards.label(tr("report.failed"), "title"))
        layout.addWidget(cards.label(message, "warning", wrap=True))
        self.body_layout.addWidget(holder)
        self.body_layout.addStretch(1)

    def show_report(self, report: SessionReport) -> None:
        self._report = report
        self._clear_body()
        self.subtitle_label.setText(tr("report.subtitle", session_id=report.session_id or "-"))

        if not report.has_data:
            holder = cards.frame("card")
            layout = cards.vbox(holder, 24, 8)
            layout.addWidget(cards.label(tr("report.empty"), "title", wrap=True))
            layout.addWidget(cards.label(report.summary, "subtitle", wrap=True))
            self.body_layout.addWidget(holder)
            self.body_layout.addStretch(1)
            return

        self.body_layout.addWidget(self._build_hero(report))

        columns = QHBoxLayout()
        columns.setSpacing(12)
        columns.addWidget(self._build_profile(report), 5)
        columns.addWidget(self._build_takeaways(report), 4)
        self.body_layout.addLayout(columns)

        self.body_layout.addWidget(self._build_questions(report))
        self.body_layout.addStretch(1)

    # -- sections ------------------------------------------------------------

    def _build_hero(self, report: SessionReport) -> QWidget:
        holder = cards.frame("scoreHero")
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(22)

        dial = ScoreDial(diameter=136, caption=band_label(report.band, report.language))
        dial.set_score(report.overall)
        layout.addWidget(dial)

        facts = QVBoxLayout()
        facts.setSpacing(6)
        facts.addWidget(cards.label(tr("report.overall"), "kicker"))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(
            chip(f"{tr('report.answered')} {report.answered_count}/{report.question_count}")
        )
        if report.role:
            chips.addWidget(chip(report.role, accent=True))
        chips.addWidget(chip(f"{tr('report.engine')}: {report.engine}"))
        if report.degraded:
            chips.addWidget(chip(tr("report.degraded")))
        chips.addStretch(1)
        facts.addLayout(chips)
        if report.summary:
            facts.addWidget(cards.label(report.summary, "subtitle", wrap=True))
        facts.addStretch(1)
        layout.addLayout(facts, 1)

        exports = QVBoxLayout()
        exports.setSpacing(6)
        for label_key, handler in (
            ("report.export_md", self._export_markdown),
            ("report.export_html", self._export_html),
            ("report.export_json", self._export_json),
            ("report.open_folder", self._open_folder),
        ):
            button = IconButton(tr(label_key), icon_name="download", kind="tool")
            button.setProperty("dense", "true")
            button.clicked.connect(handler)
            exports.addWidget(button)
        layout.addLayout(exports)
        return holder

    def _build_profile(self, report: SessionReport) -> QWidget:
        holder = cards.frame("card")
        layout = cards.vbox(holder, 16, 10)
        layout.addWidget(cards.section_header(tr("report.competency"), tr("report.radar")))

        entries = [
            (competency_label(item.key, report.language), float(item.score))
            for item in report.competencies
        ]
        if len(entries) >= CompetencyRadar.MIN_AXES:
            radar = CompetencyRadar(size=280)
            radar.set_entries(entries)
            layout.addWidget(radar, 1)

        for item in report.competencies:
            bar = ScoreBar(competency_label(item.key, report.language), label_width=110)
            bar.set_score(item.score)
            layout.addWidget(bar)

        if report.dimensions:
            layout.addSpacing(8)
            layout.addWidget(cards.label(tr("report.dimensions"), "section"))
            for item in report.dimensions:
                bar = ScoreBar(dimension_label(item.key, report.language), label_width=110)
                bar.set_score(item.score)
                layout.addWidget(bar)
        return holder

    def _build_takeaways(self, report: SessionReport) -> QWidget:
        holder = QWidget()
        layout = cards.vbox(holder, 0, 12)

        for title_key, values in (
            ("report.strengths", report.strengths),
            ("report.focus", report.focus_areas),
            ("report.actions", report.next_actions),
        ):
            if not values:
                continue
            card = cards.frame("card")
            card_layout = cards.vbox(card, 16, 6)
            card_layout.addWidget(cards.label(tr(title_key), "title"))
            for value in values:
                card_layout.addWidget(cards.label(f"• {value}", "coachNote", wrap=True))
            layout.addWidget(card)

        delivery = report.delivery
        if delivery.measured:
            card = cards.frame("card")
            card_layout = cards.vbox(card, 16, 6)
            card_layout.addWidget(cards.label(tr("report.delivery"), "title"))
            rows_host = QWidget()
            rows = cards.grid(rows_host, 0, 6)
            for row, (label_text, value) in enumerate(
                (
                    (tr("report.wpm"), f"{delivery.words_per_minute:.0f}"),
                    (tr("report.pace"), delivery.pace_label(report.language)),
                    (tr("report.filler"), f"{delivery.filler_rate:.1f}%"),
                    (tr("report.duration"), f"{int(delivery.duration_seconds)}s"),
                )
            ):
                rows.addWidget(cards.label(label_text, "dimLabel"), row, 0)
                rows.addWidget(cards.label(value, "dimValue"), row, 1, Qt.AlignmentFlag.AlignRight)
            rows.setColumnStretch(0, 1)
            card_layout.addWidget(rows_host)
            for note in delivery.note_texts(report.language):
                card_layout.addWidget(cards.label(f"• {note}", "coachNote", wrap=True))
            layout.addWidget(card)

        layout.addStretch(1)
        return holder

    def _build_questions(self, report: SessionReport) -> QWidget:
        holder = cards.frame("card")
        layout = cards.vbox(holder, 16, 10)
        layout.addWidget(cards.section_header(tr("report.questions"), tr("report.subtitle", session_id=report.session_id)))

        for item in report.items:
            entry = cards.frame("insight")
            entry_layout = cards.vbox(entry, (14, 12, 14, 12), 6)
            entry_layout.addWidget(
                cards.label(f"{item.question_index}. {item.question}", "section", wrap=True)
            )

            chips = QHBoxLayout()
            chips.setSpacing(6)
            if item.competency:
                chips.addWidget(chip(competency_label(item.competency, report.language)))
            chips.addWidget(chip(stage_label(item.stage, report.language)))
            if item.probe_count:
                chips.addWidget(chip(tr("report.probe_count", count=item.probe_count)))
            if item.answered:
                chips.addWidget(chip(band_label(item.evaluation.band, report.language), accent=True))
            else:
                chips.addWidget(chip(tr("report.not_answered")))
            chips.addStretch(1)
            entry_layout.addLayout(chips)

            if item.answered:
                bar = ScoreBar(tr("report.overall"), label_width=88)
                bar.set_score(item.overall)
                entry_layout.addWidget(bar)
                if item.evaluation.summary:
                    entry_layout.addWidget(cards.label(item.evaluation.summary, "coachNote", wrap=True))
                for note in item.evaluation.improvements:
                    entry_layout.addWidget(cards.label(f"• {note}", "coachNote", wrap=True))
                if item.excerpt():
                    entry_layout.addWidget(cards.label(item.excerpt(), "muted", wrap=True))
            layout.addWidget(entry)
        return holder

    # -- exports -------------------------------------------------------------

    def _export_markdown(self) -> None:
        self._write("report.md", render_markdown)

    def _export_html(self) -> None:
        self._write("report.html", render_html)

    def _export_json(self) -> None:
        self._write("report.json", render_json)

    def _write(self, filename: str, renderer) -> None:
        report = self._report
        engine = self.ctx.engine
        if report is None or engine is None:
            return
        try:
            content = renderer(report)
            kwargs = {
                "report.md": {"markdown": content},
                "report.html": {"html": content},
                "report.json": {"json_text": content},
            }[filename]
            written = engine.session.write_report_files(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            logger.exception("Could not export the report.")
            messages.error(self.window, tr("report.export_failed"), str(exc))
            return
        path = written.get(filename)
        if path is not None:
            self.ctx.status_var.set(tr("report.saved", path=str(path)))
            messages.info(self.window, tr("report.title"), tr("report.saved", path=str(path)))

    def _open_folder(self) -> None:
        engine = self.ctx.engine
        if engine is None:
            return
        path = engine.session.reports_dir
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        else:
            messages.info(self.window, tr("report.title"), str(path))

    # -- navigation ----------------------------------------------------------

    def _regenerate(self) -> None:
        self.window.generate_report(force=True)

    def _go_back(self) -> None:
        self.window.show_workspace()

    # -- helpers -------------------------------------------------------------

    def _clear_body(self) -> None:
        while self.body_layout.count():
            entry = self.body_layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
                continue
            child = entry.layout()
            if child is not None:
                _drop_layout(child)


def _drop_layout(layout) -> None:
    while layout.count():
        entry = layout.takeAt(0)
        widget = entry.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
            continue
        child = entry.layout()
        if child is not None:
            _drop_layout(child)
