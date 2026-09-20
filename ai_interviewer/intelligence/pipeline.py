"""One call per interview turn, and one call per report.

The UI runs these on a worker thread. Keeping the orchestration here means the
screens never have to know which provider answered, whether a probe was earned,
or how a session record turns into a report row.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.blueprint import InterviewBlueprint
from ai_interviewer.intelligence.delivery import DeliveryMetrics, analyze_delivery
from ai_interviewer.intelligence.evaluation import AnswerEvaluation, evaluate_answer
from ai_interviewer.intelligence.llm.base import EFFORT_HIGH, EFFORT_LOW, EFFORT_MEDIUM, PROVIDER_OFFLINE
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.probing import (
    DEFAULT_MAX_DEPTH,
    Probe,
    ProbeDecision,
    decide_probe,
    generate_probe,
)
from ai_interviewer.intelligence.report import ReportItem, SessionReport, build_report


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_interviewer.session_store import QuestionRecord


@dataclass(frozen=True, slots=True)
class AnswerInsight:
    """Everything the coach panel needs about one answer."""

    evaluation: AnswerEvaluation = field(default_factory=AnswerEvaluation)
    delivery: DeliveryMetrics = field(default_factory=DeliveryMetrics)
    decision: ProbeDecision = field(default_factory=lambda: ProbeDecision(False))
    probe: Probe = field(default_factory=Probe)

    @property
    def engine(self) -> str:
        return self.evaluation.engine

    @property
    def degraded(self) -> bool:
        return self.evaluation.degraded or self.probe.degraded

    @property
    def has_probe(self) -> bool:
        return self.probe.exists


def analyze_answer_turn(
    question: str,
    transcript: str,
    language: str,
    *,
    chain: ProviderChain | None = None,
    competency_key: str = "",
    interview_type: str = "hr",
    question_index: int = 0,
    duration_seconds: float = 0.0,
    probe_depth: int = 0,
    max_probe_depth: int = DEFAULT_MAX_DEPTH,
    probing_enabled: bool = True,
    scoring_enabled: bool = True,
    effort: str = EFFORT_MEDIUM,
    role: str = "",
) -> AnswerInsight:
    """Score the answer, then decide and generate a follow-up if one is earned."""
    delivery = analyze_delivery(transcript, duration_seconds, language)
    if not scoring_enabled:
        return AnswerInsight(delivery=delivery, decision=ProbeDecision(False, reason="disabled"))

    evaluation = evaluate_answer(
        question,
        transcript,
        language,
        chain=chain,
        competency_key=competency_key,
        interview_type=interview_type,
        question_index=question_index,
        duration_seconds=duration_seconds,
        delivery=delivery,
        effort=effort,
        role=role,
    )
    decision = decide_probe(
        evaluation,
        depth=probe_depth,
        max_depth=max_probe_depth,
        enabled=probing_enabled,
    )
    probe = Probe()
    if decision.should_probe:
        probe = generate_probe(
            question,
            transcript,
            language,
            decision=decision,
            evaluation=evaluation,
            chain=chain,
            competency_key=competency_key,
            depth=decision.depth,
            effort=EFFORT_LOW,
        )
    return AnswerInsight(evaluation=evaluation, delivery=delivery, decision=decision, probe=probe)


# -- session rollup ----------------------------------------------------------


def report_items(
    records: Sequence["QuestionRecord"],
    blueprint: InterviewBlueprint | None = None,
    language: str = "English",
) -> list[ReportItem]:
    """Turn saved session records into report rows."""
    items: list[ReportItem] = []
    for index, record in enumerate(records):
        planned = blueprint.question_at(index) if blueprint is not None else None
        evaluation = AnswerEvaluation.from_dict(getattr(record, "evaluation", None))
        delivery = DeliveryMetrics.from_dict(getattr(record, "delivery", None))
        transcript = str(getattr(record, "transcript", "") or "")
        if not delivery.measured and transcript.strip():
            delivery = analyze_delivery(
                transcript,
                float(getattr(record, "answer_seconds", 0.0) or 0.0),
                language,
            )
        competency_key = (
            str(getattr(record, "competency", "") or "")
            or (planned.competency if planned is not None else "")
            or evaluation.competency
        )
        stage = str(getattr(record, "stage", "") or "") or (
            planned.stage if planned is not None else phrasebook.STAGE_CORE
        )
        items.append(
            ReportItem(
                question_index=int(getattr(record, "question_index", index + 1)),
                question=str(getattr(record, "clean_question", "") or ""),
                competency=competency_key,
                stage=stage,
                transcript=transcript,
                evaluation=evaluation,
                delivery=delivery,
                probe_count=len(getattr(record, "probes", []) or []),
                repeat_count=int(getattr(record, "repeat_count", 0) or 0),
                answer_seconds=float(getattr(record, "answer_seconds", 0.0) or 0.0),
            )
        )
    return items


def build_session_report(
    records: Sequence["QuestionRecord"],
    *,
    session_id: str = "",
    language: str = "English",
    interview_type: str = "hr",
    blueprint: InterviewBlueprint | None = None,
    role: str = "",
    seniority: str = "",
    chain: ProviderChain | None = None,
    effort: str = EFFORT_HIGH,
) -> SessionReport:
    items = report_items(records, blueprint, language)
    return build_report(
        items,
        session_id=session_id,
        language=language,
        interview_type=interview_type,
        role=role or (blueprint.role if blueprint is not None else ""),
        seniority=seniority or (blueprint.seniority if blueprint is not None else ""),
        chain=chain,
        effort=effort,
    )


def engine_label(chain: ProviderChain | None) -> str:
    """Short description of what will actually run, for status text."""
    if chain is None or not chain.enabled:
        return PROVIDER_OFFLINE
    return chain.describe()


def insight_from_record(record: Any, language: str = "English") -> AnswerInsight:
    """Rehydrate a stored insight so reopening a question shows the same coach panel."""
    return AnswerInsight(
        evaluation=AnswerEvaluation.from_dict(getattr(record, "evaluation", None)),
        delivery=DeliveryMetrics.from_dict(getattr(record, "delivery", None)),
        decision=ProbeDecision(False, reason="restored"),
        probe=Probe.from_dict((getattr(record, "probes", None) or [{}])[-1]),
    )
