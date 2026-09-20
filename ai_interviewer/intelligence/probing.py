"""Adaptive probing: decide whether to dig, then ask the one question that digs.

A real interviewer does not read the next scripted question when an answer left
the most important thing out. This module turns the gaps found during
evaluation into a single follow-up, bounded by a depth cap so the interview
cannot get stuck circling one story.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.evaluation import AnswerEvaluation
from ai_interviewer.intelligence.llm.base import (
    EFFORT_LOW,
    PROVIDER_OFFLINE,
    PURPOSE_PROBE,
    LLMRequest,
    coerce_text,
    normalize_question,
)
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.rubric import KOREAN, competency


DEFAULT_MAX_DEPTH = 2
MAX_SUPPORTED_DEPTH = 4

# At or above this score an answer has already earned its point; another probe
# would just burn interview time.
STRONG_ENOUGH = 80

REASON_GAP = "gap"
REASON_DEPTH = "depth"
REASON_MAX_DEPTH = "max_depth"
REASON_STRONG = "strong_answer"
REASON_EMPTY = "empty"
REASON_DISABLED = "disabled"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class ProbeDecision:
    should_probe: bool
    gap: str = ""
    reason: str = REASON_STRONG
    depth: int = 0

    def explain(self, language: str) -> str:
        if not self.should_probe:
            return ""
        if self.gap:
            return phrasebook.gap_label(self.gap, language)
        return phrasebook.report_text("focus", language)


@dataclass(frozen=True, slots=True)
class Probe:
    question: str = ""
    gap: str = ""
    depth: int = 1
    engine: str = PROVIDER_OFFLINE
    rationale: str = ""
    degraded: bool = False
    generated_at: str = ""

    @property
    def exists(self) -> bool:
        return bool(self.question)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "gap": self.gap,
            "depth": self.depth,
            "engine": self.engine,
            "rationale": self.rationale,
            "degraded": self.degraded,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Probe":
        if not payload:
            return cls()
        return cls(
            question=str(payload.get("question", "")),
            gap=str(payload.get("gap", "")),
            depth=int(payload.get("depth", 1) or 1),
            engine=str(payload.get("engine", PROVIDER_OFFLINE)),
            rationale=str(payload.get("rationale", "")),
            degraded=bool(payload.get("degraded", False)),
            generated_at=str(payload.get("generated_at", "")),
        )


def decide_probe(
    evaluation: AnswerEvaluation | None,
    *,
    depth: int = 0,
    max_depth: int = DEFAULT_MAX_DEPTH,
    enabled: bool = True,
) -> ProbeDecision:
    """Whether the answer earns another question, and which gap to aim at."""
    if not enabled:
        return ProbeDecision(False, reason=REASON_DISABLED, depth=depth)
    if evaluation is None or not evaluation.scored:
        return ProbeDecision(False, reason=REASON_EMPTY, depth=depth)
    cap = max(0, min(int(max_depth), MAX_SUPPORTED_DEPTH))
    if depth >= cap:
        return ProbeDecision(False, reason=REASON_MAX_DEPTH, depth=depth)

    gaps = tuple(gap for gap in evaluation.gaps if gap != phrasebook.GAP_OFF_TOPIC) or evaluation.gaps
    if gaps:
        return ProbeDecision(True, gap=gaps[0], reason=REASON_GAP, depth=depth + 1)
    if evaluation.overall < STRONG_ENOUGH:
        return ProbeDecision(True, gap="", reason=REASON_DEPTH, depth=depth + 1)
    return ProbeDecision(False, reason=REASON_STRONG, depth=depth)


def generate_probe(
    question: str,
    transcript: str,
    language: str,
    *,
    decision: ProbeDecision | None = None,
    evaluation: AnswerEvaluation | None = None,
    chain: ProviderChain | None = None,
    competency_key: str = "",
    depth: int = 1,
    effort: str = EFFORT_LOW,
) -> Probe:
    """Produce the follow-up question for a decision (LLM first, rules always)."""
    answer = (transcript or "").strip()
    if not answer:
        return Probe(
            question=phrasebook.empty_answer_prompt(language),
            gap=phrasebook.GAP_TOO_SHORT,
            depth=depth,
            engine=PROVIDER_OFFLINE,
            generated_at=_now_iso(),
        )

    target = decision or ProbeDecision(True, gap="", reason=REASON_DEPTH, depth=depth)
    level = max(1, target.depth or depth)
    offline = _offline_probe(target.gap, language, level)

    if chain is None or not chain.enabled:
        return offline

    reply = chain.complete(
        LLMRequest(
            system=_probe_system_prompt(language),
            user=_probe_user_prompt(
                question=question,
                transcript=answer,
                language=language,
                gap=target.gap,
                competency_key=competency_key,
                depth=level,
                evaluation=evaluation,
            ),
            purpose=PURPOSE_PROBE,
            max_tokens=700,
            effort=effort,
            schema=_PROBE_SCHEMA,
            timeout=35.0,
        )
    )
    if reply is None:
        return Probe(
            question=offline.question,
            gap=offline.gap,
            depth=level,
            engine=PROVIDER_OFFLINE,
            rationale=offline.rationale,
            degraded=True,
            generated_at=_now_iso(),
        )

    data = reply.data or {}
    text = normalize_question(str(data.get("question", "")) or reply.text)
    if not text:
        return Probe(
            question=offline.question,
            gap=offline.gap,
            depth=level,
            engine=PROVIDER_OFFLINE,
            degraded=True,
            generated_at=_now_iso(),
        )
    gap = str(data.get("gap", "")).strip()
    return Probe(
        question=text,
        gap=gap if gap in phrasebook.GAP_KEYS else target.gap,
        depth=level,
        engine=reply.describe(),
        rationale=coerce_text(data.get("rationale", ""), 240),
        generated_at=_now_iso(),
    )


def follow_up_for_answer(
    question: str,
    transcript: str,
    language: str,
    *,
    chain: ProviderChain | None = None,
    competency_key: str = "",
    depth: int = 1,
) -> Probe:
    """Single-shot follow-up without a prior evaluation (the manual button)."""
    from ai_interviewer.intelligence.evaluation import analyze_answer, detect_gaps

    answer = (transcript or "").strip()
    if not answer:
        return generate_probe(question, "", language, chain=None, depth=depth)
    signals = analyze_answer(question, answer, language)
    gaps = detect_gaps(signals)
    decision = ProbeDecision(True, gap=gaps[0] if gaps else "", reason=REASON_GAP, depth=depth)
    return generate_probe(
        question,
        answer,
        language,
        decision=decision,
        chain=chain,
        competency_key=competency_key,
        depth=depth,
    )


# -- offline path ------------------------------------------------------------


def _offline_probe(gap: str, language: str, depth: int) -> Probe:
    variant = max(0, depth - 1)
    if gap:
        text = phrasebook.probe_question(gap, language, variant)
    else:
        text = phrasebook.depth_probe(language, variant)
    return Probe(
        question=text,
        gap=gap,
        depth=depth,
        engine=PROVIDER_OFFLINE,
        rationale=phrasebook.gap_label(gap, language) if gap else "",
        generated_at=_now_iso(),
    )


# -- LLM path ----------------------------------------------------------------

_PROBE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "gap": {"type": "string", "enum": list(phrasebook.GAP_KEYS)},
        "rationale": {"type": "string"},
    },
    "required": ["question", "gap", "rationale"],
    "additionalProperties": False,
}


def _probe_system_prompt(language: str) -> str:
    response_language = "Korean" if language == KOREAN else "English"
    return (
        "You are a senior interviewer mid-conversation with a candidate. "
        "You ask exactly one follow-up question, out loud, and it will be spoken by a "
        "text-to-speech voice, so it must be one natural sentence a person would actually say.\n\n"
        "Rules:\n"
        "- One question only. No preamble, no numbering, no commentary.\n"
        "- Aim it at the single most important thing the answer left out.\n"
        "- Ask for evidence, the candidate's own actions, a measurable outcome, or the reasoning "
        "behind a decision — never for an opinion.\n"
        "- Do not repeat the original question, and do not summarise the answer back.\n"
        "- Stay courteous and neutral; never evaluate the answer out loud.\n"
        f"- Write the question in {response_language}.\n"
        "`rationale` is an internal note for the coach panel and is never spoken."
    )


def _probe_user_prompt(
    *,
    question: str,
    transcript: str,
    language: str,
    gap: str,
    competency_key: str,
    depth: int,
    evaluation: AnswerEvaluation | None,
) -> str:
    target = competency(competency_key)
    lines = [
        f"Target competency: {target.key} — {target.focus('English')}",
        f"Follow-up depth: {depth} (1 is the first follow-up on this answer)",
    ]
    if gap:
        lines.append(f"Gap to close: {gap} — {phrasebook.gap_label(gap, 'English')}")
    else:
        lines.append("No single gap dominates; go one level deeper on judgement or learning.")
    if evaluation is not None and evaluation.scored:
        lines.append(f"Rubric score so far: {evaluation.overall}/100 ({evaluation.band})")
        if evaluation.gaps:
            lines.append(f"All detected gaps: {', '.join(evaluation.gaps)}")
    lines.extend(
        [
            "",
            f"Original question:\n{question}",
            "",
            f"Candidate answer:\n{transcript}",
        ]
    )
    return "\n".join(lines)
