"""Live coach panel: the rubric verdict on the answer just given.

Display only — it renders an `AnswerInsight` and nothing else. Deciding when to
score, and whether to ask the suggested follow-up, stays with the workspace.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ai_interviewer.i18n import tr
from ai_interviewer.intelligence import AnswerInsight, band_label, competency_label, dimension_label
from ai_interviewer.intelligence.phrasebook import gap_label, stage_label
from ai_interviewer.ui.widgets import cards
from ai_interviewer.ui.widgets.scoring import ScoreBar, ScoreDial, chip


class CoachPanel(QScrollArea):
    """Scrollable verdict: score, dimensions, delivery, gaps, and next probe."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._body = QWidget()
        self._layout = cards.vbox(self._body, 0, 10)
        self.setWidget(self._body)
        self.set_message(tr("ws.coach_idle"))

    # -- states --------------------------------------------------------------

    def set_message(self, text: str, role: str = "subtitle") -> None:
        self._clear()
        self._layout.addWidget(cards.label(text, role, wrap=True))
        self._layout.addStretch(1)

    def set_running(self) -> None:
        self.set_message(tr("ws.coach_running"), "status")

    def show_insight(
        self,
        insight: AnswerInsight,
        language: str,
        *,
        competency_key: str = "",
        stage: str = "",
    ) -> None:
        self._clear()
        evaluation = insight.evaluation
        if not evaluation.scored:
            self.set_message(tr("ws.coach_empty_answer"))
            return

        self._layout.addWidget(self._header(evaluation, insight, language, competency_key, stage))

        if evaluation.dimensions:
            block = self._block(tr("ws.coach_dimensions"))
            layout = block.layout()
            for item in evaluation.dimensions:
                bar = ScoreBar(dimension_label(item.key, language), label_width=76)
                bar.set_score(item.score)
                layout.addWidget(bar)
            self._layout.addWidget(block)

        delivery = insight.delivery
        if delivery.measured:
            block = self._block(tr("ws.coach_delivery"))
            layout = block.layout()
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(chip(f"{delivery.words_per_minute:.0f} · {delivery.pace_label(language)}"))
            row.addWidget(chip(f"{tr('report.filler')} {delivery.filler_rate:.1f}%"))
            row.addWidget(chip(f"{int(delivery.duration_seconds)}s"))
            row.addStretch(1)
            layout.addLayout(row)
            for note in delivery.note_texts(language):
                layout.addWidget(cards.label(f"• {note}", "coachNote", wrap=True))
            self._layout.addWidget(block)

        if evaluation.gaps:
            block = self._block(tr("ws.coach_gaps"))
            layout = block.layout()
            row = QHBoxLayout()
            row.setSpacing(6)
            for gap in evaluation.gaps[:4]:
                row.addWidget(chip(gap_label(gap, language)))
            row.addStretch(1)
            layout.addLayout(row)
            self._layout.addWidget(block)

        self._bullets(tr("ws.coach_strengths"), evaluation.strengths)
        self._bullets(tr("ws.coach_improvements"), evaluation.improvements)
        self._bullets(tr("ws.coach_model_answer"), evaluation.model_answer)

        self._layout.addWidget(self._probe_block(insight, language))
        self._layout.addStretch(1)

    # -- sections ------------------------------------------------------------

    def _header(
        self,
        evaluation,
        insight: AnswerInsight,
        language: str,
        competency_key: str,
        stage: str,
    ) -> QWidget:
        holder = cards.frame("scoreHero")
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        dial = ScoreDial(diameter=92, thickness=8, caption=band_label(evaluation.band, language))
        dial.set_score(evaluation.overall)
        layout.addWidget(dial)

        facts = QVBoxLayout()
        facts.setSpacing(5)
        tags = QHBoxLayout()
        tags.setSpacing(5)
        key = competency_key or evaluation.competency
        if key:
            tags.addWidget(chip(competency_label(key, language), accent=True))
        if stage:
            tags.addWidget(chip(stage_label(stage, language)))
        tags.addStretch(1)
        facts.addLayout(tags)
        facts.addWidget(cards.label(f"{tr('ws.coach_engine')}: {evaluation.engine}", "muted", wrap=True))
        if evaluation.degraded and evaluation.note:
            facts.addWidget(
                cards.label(tr("ws.coach_degraded", reason=evaluation.note), "warning", wrap=True)
            )
        if evaluation.summary:
            facts.addWidget(cards.label(evaluation.summary, "coachNote", wrap=True))
        facts.addStretch(1)
        layout.addLayout(facts, 1)
        return holder

    def _probe_block(self, insight: AnswerInsight, language: str) -> QWidget:
        block = self._block(tr("ws.coach_probe"))
        layout = block.layout()
        if insight.has_probe:
            probe = insight.probe
            layout.addWidget(cards.label(probe.question, "question", wrap=True))
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(chip(tr("ws.coach_probe_depth", depth=probe.depth)))
            if probe.gap:
                row.addWidget(chip(gap_label(probe.gap, language)))
            row.addStretch(1)
            layout.addLayout(row)
            if probe.rationale:
                layout.addWidget(cards.label(probe.rationale, "muted", wrap=True))
        else:
            layout.addWidget(cards.label(tr("ws.coach_no_probe"), "success", wrap=True))
        return block

    def _bullets(self, title: str, values: tuple[str, ...]) -> None:
        if not values:
            return
        block = self._block(title)
        layout = block.layout()
        for value in values:
            layout.addWidget(cards.label(f"• {value}", "coachNote", wrap=True))
        self._layout.addWidget(block)

    def _block(self, title: str) -> QFrame:
        holder = cards.frame("insight")
        layout = cards.vbox(holder, (12, 10, 12, 10), 6)
        layout.addWidget(cards.label(title, "section"))
        return holder

    # -- helpers -------------------------------------------------------------

    def _clear(self) -> None:
        _drop_layout(self._layout)


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
