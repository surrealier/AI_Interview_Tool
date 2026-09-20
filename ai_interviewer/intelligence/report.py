"""Session report: what the interview actually established, and what to fix.

Aggregates per-answer evaluations into competency scores, a headline band, and
a short practice plan. The numbers are always computed locally from the
evaluations; a provider, when configured, only writes the narrative around
them — so a report never shows a score a model invented.
"""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.delivery import DeliveryMetrics, aggregate
from ai_interviewer.intelligence.evaluation import AnswerEvaluation, DimensionScore
from ai_interviewer.intelligence.llm.base import (
    EFFORT_HIGH,
    PROVIDER_OFFLINE,
    PURPOSE_REPORT,
    LLMRequest,
    coerce_text,
    coerce_text_list,
)
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.rubric import (
    DIMENSIONS,
    KOREAN,
    band_key_for_score,
    band_label,
    clamp_score,
    competencies_for_interview_type,
    competency_label,
    dimension_label,
)


# Focus competencies for the interview type count for more than incidental ones.
_FOCUS_WEIGHT = 1.3
_OTHER_WEIGHT = 1.0

_EXCERPT_CHARS = 180


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class ReportItem:
    """One question's line in the report."""

    question_index: int
    question: str
    competency: str = ""
    stage: str = phrasebook.STAGE_CORE
    transcript: str = ""
    evaluation: AnswerEvaluation = field(default_factory=AnswerEvaluation)
    delivery: DeliveryMetrics = field(default_factory=DeliveryMetrics)
    probe_count: int = 0
    repeat_count: int = 0
    answer_seconds: float = 0.0

    @property
    def answered(self) -> bool:
        return bool(self.transcript.strip()) and self.evaluation.scored

    @property
    def overall(self) -> int:
        return self.evaluation.overall

    def excerpt(self) -> str:
        text = " ".join(self.transcript.split())
        if len(text) <= _EXCERPT_CHARS:
            return text
        return text[: _EXCERPT_CHARS - 1].rstrip() + "…"

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_index": self.question_index,
            "question": self.question,
            "competency": self.competency,
            "stage": self.stage,
            "excerpt": self.excerpt(),
            "probe_count": self.probe_count,
            "repeat_count": self.repeat_count,
            "answer_seconds": round(self.answer_seconds, 2),
            "evaluation": self.evaluation.to_dict(),
            "delivery": self.delivery.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReportItem":
        """Rehydrate a stored row. Only the excerpt survives, not the full
        transcript, so a saved report stays small — `answered` is recovered
        from the excerpt plus the evaluation."""
        return cls(
            question_index=int(payload.get("question_index", 0) or 0),
            question=str(payload.get("question", "")),
            competency=str(payload.get("competency", "")),
            stage=str(payload.get("stage", phrasebook.STAGE_CORE)),
            transcript=str(payload.get("excerpt", "")),
            evaluation=AnswerEvaluation.from_dict(payload.get("evaluation")),
            delivery=DeliveryMetrics.from_dict(payload.get("delivery")),
            probe_count=int(payload.get("probe_count", 0) or 0),
            repeat_count=int(payload.get("repeat_count", 0) or 0),
            answer_seconds=float(payload.get("answer_seconds", 0.0) or 0.0),
        )


@dataclass(frozen=True, slots=True)
class CompetencyScore:
    key: str
    score: int
    band: str
    answered: int

    def label(self, language: str) -> str:
        return competency_label(self.key, language)

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "score": self.score, "band": self.band, "answered": self.answered}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CompetencyScore":
        score = int(payload.get("score", 0) or 0)
        return cls(
            key=str(payload.get("key", "")),
            score=score,
            band=str(payload.get("band") or band_key_for_score(score)),
            answered=int(payload.get("answered", 0) or 0),
        )


@dataclass(frozen=True, slots=True)
class SessionReport:
    session_id: str = ""
    language: str = "English"
    interview_type: str = "hr"
    role: str = ""
    seniority: str = ""
    overall: int = 0
    band: str = "insufficient"
    question_count: int = 0
    answered_count: int = 0
    competencies: tuple[CompetencyScore, ...] = field(default_factory=tuple)
    dimensions: tuple[DimensionScore, ...] = field(default_factory=tuple)
    items: tuple[ReportItem, ...] = field(default_factory=tuple)
    delivery: DeliveryMetrics = field(default_factory=DeliveryMetrics)
    strengths: tuple[str, ...] = field(default_factory=tuple)
    focus_areas: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    summary: str = ""
    engine: str = PROVIDER_OFFLINE
    degraded: bool = False
    generated_at: str = ""

    @property
    def has_data(self) -> bool:
        return self.answered_count > 0

    def band_text(self) -> str:
        return band_label(self.band, self.language)

    def dimension_score(self, key: str) -> int:
        for item in self.dimensions:
            if item.key == key:
                return item.score
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "language": self.language,
            "interview_type": self.interview_type,
            "role": self.role,
            "seniority": self.seniority,
            "overall": self.overall,
            "band": self.band,
            "question_count": self.question_count,
            "answered_count": self.answered_count,
            "competencies": [item.to_dict() for item in self.competencies],
            "dimensions": [item.to_dict() for item in self.dimensions],
            "delivery": self.delivery.to_dict(),
            "strengths": list(self.strengths),
            "focus_areas": list(self.focus_areas),
            "next_actions": list(self.next_actions),
            "summary": self.summary,
            "engine": self.engine,
            "degraded": self.degraded,
            "generated_at": self.generated_at,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SessionReport":
        if not payload:
            return cls()
        return cls(
            session_id=str(payload.get("session_id", "")),
            language=str(payload.get("language", "English")),
            interview_type=str(payload.get("interview_type", "hr")),
            role=str(payload.get("role", "")),
            seniority=str(payload.get("seniority", "")),
            overall=int(payload.get("overall", 0) or 0),
            band=str(payload.get("band", "insufficient")),
            question_count=int(payload.get("question_count", 0) or 0),
            answered_count=int(payload.get("answered_count", 0) or 0),
            competencies=tuple(
                CompetencyScore.from_dict(item)
                for item in payload.get("competencies", []) or ()
                if isinstance(item, dict)
            ),
            dimensions=tuple(
                DimensionScore.from_dict(item)
                for item in payload.get("dimensions", []) or ()
                if isinstance(item, dict)
            ),
            delivery=DeliveryMetrics.from_dict(payload.get("delivery")),
            strengths=tuple(str(item) for item in payload.get("strengths", []) or ()),
            focus_areas=tuple(str(item) for item in payload.get("focus_areas", []) or ()),
            next_actions=tuple(str(item) for item in payload.get("next_actions", []) or ()),
            items=tuple(
                ReportItem.from_dict(item)
                for item in payload.get("items", []) or ()
                if isinstance(item, dict)
            ),
            summary=str(payload.get("summary", "")),
            engine=str(payload.get("engine", PROVIDER_OFFLINE)),
            degraded=bool(payload.get("degraded", False)),
            generated_at=str(payload.get("generated_at", "")),
        )


# -- building ----------------------------------------------------------------


def build_report(
    items: Sequence[ReportItem],
    *,
    session_id: str = "",
    language: str = "English",
    interview_type: str = "hr",
    role: str = "",
    seniority: str = "",
    chain: ProviderChain | None = None,
    effort: str = EFFORT_HIGH,
) -> SessionReport:
    answered = [item for item in items if item.answered]
    focus_keys = competencies_for_interview_type(interview_type)

    if not answered:
        return SessionReport(
            session_id=session_id,
            language=language,
            interview_type=interview_type,
            role=role,
            seniority=seniority,
            question_count=len(items),
            summary=phrasebook.report_text("no_data", language),
            items=tuple(items),
            generated_at=_now_iso(),
        )

    dimensions = _session_dimensions(answered)
    competencies = _competency_scores(answered, focus_keys)
    overall = _weighted_overall(competencies, focus_keys)
    delivery = aggregate([item.delivery for item in answered])

    strengths = _offline_strengths(dimensions, competencies, language)
    focus_areas = _offline_focus_areas(dimensions, competencies, answered, language)
    next_actions = _offline_next_actions(dimensions, language)
    summary = _offline_summary(overall, len(answered), len(items), language)
    engine = PROVIDER_OFFLINE
    degraded = False

    report = SessionReport(
        session_id=session_id,
        language=language,
        interview_type=interview_type,
        role=role,
        seniority=seniority,
        overall=overall,
        band=band_key_for_score(overall),
        question_count=len(items),
        answered_count=len(answered),
        competencies=competencies,
        dimensions=dimensions,
        items=tuple(items),
        delivery=delivery,
        strengths=strengths,
        focus_areas=focus_areas,
        next_actions=next_actions,
        summary=summary,
        engine=engine,
        degraded=degraded,
        generated_at=_now_iso(),
    )

    if chain is None or not chain.enabled:
        return report
    return _with_narrative(report, chain, effort)


def _session_dimensions(answered: Sequence[ReportItem]) -> tuple[DimensionScore, ...]:
    result: list[DimensionScore] = []
    for spec in DIMENSIONS:
        values = [
            item.evaluation.score_for(spec.key)
            for item in answered
            if any(entry.key == spec.key for entry in item.evaluation.dimensions)
        ]
        if not values:
            continue
        result.append(DimensionScore(key=spec.key, score=int(round(sum(values) / len(values)))))
    return tuple(result)


def _competency_scores(
    answered: Sequence[ReportItem],
    focus_keys: Sequence[str],
) -> tuple[CompetencyScore, ...]:
    buckets: dict[str, list[int]] = {}
    for item in answered:
        key = item.competency or item.evaluation.competency
        if not key:
            continue
        buckets.setdefault(key, []).append(item.overall)

    ordered_keys = list(focus_keys) + [key for key in buckets if key not in focus_keys]
    result: list[CompetencyScore] = []
    for key in ordered_keys:
        values = buckets.get(key, [])
        if not values:
            continue
        score = int(round(sum(values) / len(values)))
        result.append(
            CompetencyScore(key=key, score=score, band=band_key_for_score(score), answered=len(values))
        )
    return tuple(result)


def _weighted_overall(competencies: Sequence[CompetencyScore], focus_keys: Sequence[str]) -> int:
    if not competencies:
        return 0
    focus = set(focus_keys)
    total = 0.0
    weight_sum = 0.0
    for item in competencies:
        weight = (_FOCUS_WEIGHT if item.key in focus else _OTHER_WEIGHT) * max(1, item.answered)
        total += item.score * weight
        weight_sum += weight
    if weight_sum <= 0:
        return 0
    return int(round(clamp_score(total / weight_sum)))


def _offline_strengths(
    dimensions: Sequence[DimensionScore],
    competencies: Sequence[CompetencyScore],
    language: str,
) -> tuple[str, ...]:
    result: list[str] = []
    for item in sorted(dimensions, key=lambda entry: entry.score, reverse=True):
        if item.score < 65:
            break
        result.append(f"{dimension_label(item.key, language)} {item.score} — {phrasebook.strength_note(item.key, language)}")
        if len(result) >= 2:
            break
    best = max(competencies, key=lambda entry: entry.score, default=None)
    if best is not None and best.score >= 65:
        result.append(
            f"{competency_label(best.key, language)} {best.score} ({band_label(best.band, language)})"
        )
    return tuple(result[:3])


def _offline_focus_areas(
    dimensions: Sequence[DimensionScore],
    competencies: Sequence[CompetencyScore],
    answered: Sequence[ReportItem],
    language: str,
) -> tuple[str, ...]:
    result: list[str] = []
    for item in sorted(dimensions, key=lambda entry: entry.score):
        if item.score >= 70 and result:
            break
        result.append(f"{dimension_label(item.key, language)} {item.score}")
        if len(result) >= 2:
            break

    counts: dict[str, int] = {}
    for item in answered:
        for gap in item.evaluation.gaps:
            counts[gap] = counts.get(gap, 0) + 1
    for gap, count in sorted(counts.items(), key=lambda entry: entry[1], reverse=True)[:2]:
        result.append(f"{phrasebook.gap_label(gap, language)} ×{count}")

    worst = min(competencies, key=lambda entry: entry.score, default=None)
    if worst is not None and worst.score < 60:
        result.append(f"{competency_label(worst.key, language)} {worst.score}")
    return tuple(result[:4])


def _offline_next_actions(dimensions: Sequence[DimensionScore], language: str) -> tuple[str, ...]:
    weakest = sorted(dimensions, key=lambda entry: entry.score)[:2]
    actions = [phrasebook.next_action(item.key, language) for item in weakest]
    if not actions:
        actions = [phrasebook.next_action("structure", language)]
    return tuple(dict.fromkeys(actions))


def _offline_summary(overall: int, answered: int, total: int, language: str) -> str:
    band = band_label(band_key_for_score(overall), language)
    return phrasebook.session_summary(answered, total, overall, band, language)


# -- narrative ---------------------------------------------------------------

_REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "focus_areas": {"type": "array", "items": {"type": "string"}},
        "next_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "strengths", "focus_areas", "next_actions"],
    "additionalProperties": False,
}


def _with_narrative(report: SessionReport, chain: ProviderChain, effort: str) -> SessionReport:
    reply = chain.complete(
        LLMRequest(
            system=_report_system_prompt(report.language),
            user=_report_user_prompt(report),
            purpose=PURPOSE_REPORT,
            max_tokens=3000,
            effort=effort,
            schema=_REPORT_SCHEMA,
            timeout=120.0,
        )
    )
    if reply is None or not reply.data:
        return _replace(report, degraded=True)

    data = reply.data
    return _replace(
        report,
        summary=coerce_text(data.get("summary"), 800) or report.summary,
        strengths=tuple(coerce_text_list(data.get("strengths"), 4, 300)) or report.strengths,
        focus_areas=tuple(coerce_text_list(data.get("focus_areas"), 4, 300)) or report.focus_areas,
        next_actions=tuple(coerce_text_list(data.get("next_actions"), 4, 300)) or report.next_actions,
        engine=reply.describe(),
        degraded=False,
    )


def _replace(report: SessionReport, **changes: Any) -> SessionReport:
    payload: dict[str, Any] = {
        "session_id": report.session_id,
        "language": report.language,
        "interview_type": report.interview_type,
        "role": report.role,
        "seniority": report.seniority,
        "overall": report.overall,
        "band": report.band,
        "question_count": report.question_count,
        "answered_count": report.answered_count,
        "competencies": report.competencies,
        "dimensions": report.dimensions,
        "items": report.items,
        "delivery": report.delivery,
        "strengths": report.strengths,
        "focus_areas": report.focus_areas,
        "next_actions": report.next_actions,
        "summary": report.summary,
        "engine": report.engine,
        "degraded": report.degraded,
        "generated_at": report.generated_at,
    }
    payload.update(changes)
    return SessionReport(**payload)


def _report_system_prompt(language: str) -> str:
    response_language = "Korean" if language == KOREAN else "English"
    return (
        "You write the debrief a hiring panel reads after an interview practice session. "
        "The scores are already computed and are not yours to change.\n\n"
        "Rules:\n"
        "- Explain what the scores mean, citing the specific answers they came from.\n"
        "- Be direct. If the evidence is thin, say so plainly; do not soften it into praise.\n"
        "- `strengths` and `focus_areas` are short phrases, not paragraphs.\n"
        "- `next_actions` are concrete drills the candidate can run before the next interview, "
        "each naming what to practise and how to check it worked.\n"
        "- Never invent facts that are not in the transcripts.\n"
        f"- Write everything in {response_language}.\n"
        "- `summary` is at most four sentences."
    )


def _report_user_prompt(report: SessionReport) -> str:
    lines = [
        f"Interview type: {report.interview_type}",
        f"Role: {report.role or 'not specified'}",
        f"Overall score (computed): {report.overall} ({report.band})",
        f"Answers scored: {report.answered_count} of {report.question_count}",
        "",
        "Dimension averages:",
    ]
    lines.extend(f"- {item.key}: {item.score}" for item in report.dimensions)
    lines.append("")
    lines.append("Competency averages:")
    lines.extend(f"- {item.key}: {item.score} ({item.answered} answer(s))" for item in report.competencies)
    delivery = report.delivery
    lines.extend(
        [
            "",
            "Delivery, measured locally:",
            f"- pace: {delivery.pace} ({delivery.words_per_minute:.0f} units per minute)",
            f"- filler rate: {delivery.filler_rate:.1f} per 100 units",
            f"- total answer time: {delivery.duration_seconds:.0f}s over {delivery.word_count} units",
            "",
            "Per-answer detail:",
        ]
    )
    for item in report.items:
        if not item.answered:
            lines.append(f"[{item.question_index}] {item.question} — not answered")
            continue
        gaps = ", ".join(item.evaluation.gaps) or "none"
        lines.append(
            f"[{item.question_index}] ({item.competency}, score {item.overall}) {item.question}\n"
            f"    answer: {item.excerpt()}\n"
            f"    gaps: {gaps}"
        )
    return "\n".join(lines)


# -- rendering ---------------------------------------------------------------


def render_markdown(report: SessionReport) -> str:
    language = report.language
    text = lambda key: phrasebook.report_text(key, language)  # noqa: E731 - local alias
    lines = [
        f"# {text('title')}",
        "",
        f"- {text('overall')}: **{report.overall} / 100** ({report.band_text()})",
        f"- {text('answered')}: {report.answered_count} / {report.question_count}",
    ]
    if report.role:
        lines.append(f"- Role: {report.role}")
    lines.append(f"- {text('generated_by')}: `{report.engine}`")
    lines.append(f"- {report.generated_at}")
    if report.summary:
        lines.extend(["", report.summary])

    if report.competencies:
        lines.extend(["", f"## {text('competency')}", ""])
        for item in report.competencies:
            bar = _bar(item.score)
            lines.append(
                f"- {item.label(language)}: **{item.score}** {bar} ({band_label(item.band, language)}, n={item.answered})"
            )

    if report.dimensions:
        lines.extend(["", f"## {text('dimensions')}", ""])
        for item in report.dimensions:
            lines.append(f"- {dimension_label(item.key, language)}: {item.score}")

    delivery = report.delivery
    if delivery.measured:
        lines.extend(["", f"## {text('delivery')}", ""])
        lines.append(f"- {text('wpm')}: {delivery.words_per_minute:.0f} ({delivery.pace_label(language)})")
        lines.append(f"- {text('filler')}: {delivery.filler_rate:.1f}%")
        lines.append(f"- {text('duration')}: {int(delivery.duration_seconds)}s")
        lines.extend(f"- {note}" for note in delivery.note_texts(language))

    for heading, values in (
        (text("strengths"), report.strengths),
        (text("focus"), report.focus_areas),
        (text("actions"), report.next_actions),
    ):
        if not values:
            continue
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {value}" for value in values)

    if report.items:
        lines.extend(["", f"## {text('questions')}", ""])
        for item in report.items:
            if not item.answered:
                lines.append(f"### {item.question_index}. {item.question}")
                lines.extend(["", f"_{text('not_answered')}_", ""])
                continue
            lines.append(f"### {item.question_index}. {item.question}")
            lines.append("")
            lines.append(
                f"- {competency_label(item.competency, language)} · "
                f"{phrasebook.stage_label(item.stage, language)} · "
                f"**{item.overall}** ({band_label(item.evaluation.band, language)})"
            )
            if item.evaluation.summary:
                lines.append(f"- {item.evaluation.summary}")
            for entry in item.evaluation.improvements:
                lines.append(f"  - {entry}")
            if item.excerpt():
                lines.extend(["", f"> {item.excerpt()}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _bar(score: int, width: int = 10) -> str:
    filled = int(round(max(0, min(100, score)) / 100 * width))
    return "█" * filled + "·" * (width - filled)


def render_html(report: SessionReport) -> str:
    """A standalone page the user can keep, print, or send to a mentor."""
    language = report.language
    text = lambda key: html.escape(phrasebook.report_text(key, language))  # noqa: E731
    rows = []
    for item in report.competencies:
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{html.escape(item.label(language))}</th>"
            f"<td class=\"num\">{item.score}</td>"
            f"<td><div class=\"meter\"><span style=\"width:{max(0, min(100, item.score))}%\"></span></div></td>"
            f"<td class=\"band band-{html.escape(item.band)}\">{html.escape(band_label(item.band, language))}</td>"
            f"<td class=\"num\">{item.answered}</td>"
            "</tr>"
        )

    details = []
    for item in report.items:
        if not item.answered:
            details.append(
                f"<article class=\"q skipped\"><h3>{item.question_index}. {html.escape(item.question)}</h3>"
                f"<p class=\"muted\">{text('not_answered')}</p></article>"
            )
            continue
        improvements = "".join(f"<li>{html.escape(entry)}</li>" for entry in item.evaluation.improvements)
        details.append(
            f"<article class=\"q\"><h3>{item.question_index}. {html.escape(item.question)}</h3>"
            f"<p class=\"tags\"><span>{html.escape(competency_label(item.competency, language))}</span>"
            f"<span>{html.escape(phrasebook.stage_label(item.stage, language))}</span>"
            f"<span class=\"score band-{html.escape(item.evaluation.band)}\">{item.overall}</span></p>"
            + (f"<p>{html.escape(item.evaluation.summary)}</p>" if item.evaluation.summary else "")
            + (f"<ul>{improvements}</ul>" if improvements else "")
            + (f"<blockquote>{html.escape(item.excerpt())}</blockquote>" if item.excerpt() else "")
            + "</article>"
        )

    def block(heading: str, values: tuple[str, ...]) -> str:
        if not values:
            return ""
        items = "".join(f"<li>{html.escape(value)}</li>" for value in values)
        return f"<section><h2>{heading}</h2><ul>{items}</ul></section>"

    return f"""<!doctype html>
<html lang="{'ko' if language == KOREAN else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{text('title')} · {html.escape(report.session_id)}</title>
<style>
:root {{ color-scheme: light dark; --ink:#17202f; --muted:#5a6a81; --line:#d5dce8;
  --bg:#f3f5f9; --card:#ffffff; --accent:#2f6bdb; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ink:#f6f8fc; --muted:#95a3b8; --line:#263248; --bg:#070a12; --card:#0e1422; --accent:#5ea1ff; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:32px 20px 64px; background:var(--bg); color:var(--ink);
  font:15px/1.6 "Segoe UI","Malgun Gothic",system-ui,sans-serif; }}
main {{ max-width:880px; margin:0 auto; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
h2 {{ font-size:17px; margin:32px 0 10px; }}
h3 {{ font-size:15px; margin:0 0 8px; }}
.headline {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:22px 24px; display:flex; gap:24px; align-items:center; flex-wrap:wrap; }}
.dial {{ font-size:44px; font-weight:700; line-height:1; letter-spacing:-1px; }}
.dial small {{ font-size:15px; font-weight:500; color:var(--muted); }}
.meta {{ color:var(--muted); font-size:13px; margin:2px 0 0; }}
table {{ width:100%; border-collapse:collapse; background:var(--card);
  border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
th, td {{ padding:9px 12px; text-align:left; border-bottom:1px solid var(--line); font-weight:500; }}
tr:last-child th, tr:last-child td {{ border-bottom:0; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; width:56px; }}
.meter {{ background:var(--line); border-radius:999px; height:8px; min-width:120px; overflow:hidden; }}
.meter span {{ display:block; height:100%; background:var(--accent); border-radius:999px; }}
.band {{ font-size:12px; white-space:nowrap; }}
.band-outstanding {{ color:#15803d; }} .band-strong {{ color:#0d9488; }}
.band-solid {{ color:#b45309; }} .band-developing {{ color:#c2410c; }}
.band-insufficient {{ color:#dc2626; }}
section ul {{ margin:0; padding-left:20px; }}
.q {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:16px 18px; margin:0 0 12px; }}
.q.skipped {{ opacity:.6; }}
.tags {{ display:flex; gap:8px; flex-wrap:wrap; margin:0 0 10px; }}
.tags span {{ font-size:12px; border:1px solid var(--line); border-radius:999px; padding:2px 9px; color:var(--muted); }}
.tags .score {{ font-weight:700; color:var(--ink); }}
blockquote {{ margin:10px 0 0; padding:10px 14px; border-left:3px solid var(--accent);
  background:color-mix(in srgb, var(--accent) 7%, transparent); color:var(--muted); font-size:14px; }}
.muted {{ color:var(--muted); }}
code {{ font-family:"Cascadia Mono",Consolas,monospace; font-size:13px; }}
</style>
</head>
<body>
<main>
<h1>{text('title')}</h1>
<p class="meta">{html.escape(report.session_id)} · {html.escape(report.generated_at)} · <code>{html.escape(report.engine)}</code></p>
<div class="headline">
  <div class="dial">{report.overall}<small> / 100</small></div>
  <div>
    <strong class="band band-{html.escape(report.band)}">{html.escape(report.band_text())}</strong>
    <p class="meta">{text('answered')}: {report.answered_count} / {report.question_count}
    {(' · ' + html.escape(report.role)) if report.role else ''}</p>
  </div>
</div>
{f'<p>{html.escape(report.summary)}</p>' if report.summary else ''}
<h2>{text('competency')}</h2>
<table>{''.join(rows)}</table>
{block(text('strengths'), report.strengths)}
{block(text('focus'), report.focus_areas)}
{block(text('actions'), report.next_actions)}
<h2>{text('questions')}</h2>
{''.join(details)}
</main>
</body>
</html>
"""


def render_json(report: SessionReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
