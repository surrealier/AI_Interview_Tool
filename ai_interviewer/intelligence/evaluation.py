"""Answer scoring: rubric-aligned evaluation with an offline fallback.

Two paths produce the same `AnswerEvaluation` shape. The offline path reads
structural signals out of the transcript and always works. The LLM path asks a
provider for a constrained JSON verdict and then has its numbers reconciled
with the locally measured delivery score, so the part of the judgement that can
be measured is never left to a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.delivery import DeliveryMetrics, analyze_delivery
from ai_interviewer.intelligence.llm.base import (
    EFFORT_MEDIUM,
    PROVIDER_OFFLINE,
    PURPOSE_EVALUATION,
    LLMRequest,
    coerce_score,
    coerce_text,
    coerce_text_list,
)
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.rubric import (
    DIMENSION_KEYS,
    KOREAN,
    band_key_for_score,
    clamp_score,
    competency,
    dimension,
    dimension_label,
    weighted_overall,
)


# Dimensions the model is asked to judge; `delivery` is measured, not asked.
_JUDGED_DIMENSIONS: tuple[str, ...] = tuple(key for key in DIMENSION_KEYS if key != "delivery")

_SHORT_ANSWER_TOKENS = {KOREAN: 25, "English": 40}
_VERY_SHORT_ANSWER_TOKENS = {KOREAN: 10, "English": 16}
_LONG_ANSWER_TOKENS = {KOREAN: 240, "English": 380}

# Word characters plus the Hangul syllable block, built from code points so
# this module carries no interview content of its own.
_WORD = re.compile(f"[0-9A-Za-z{chr(0xAC00)}-{chr(0xD7A3)}]+")
_PROPER_NOUN = re.compile(r"\b[A-Z][A-Za-z0-9+#.]{2,}\b")

def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# -- shared textual signals --------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnswerSignals:
    """Structural facts about one answer, derived without any model call."""

    language: str
    token_count: int
    star_parts: tuple[str, ...]
    gaps: tuple[str, ...]
    reasoning_hits: int
    generic_hits: int
    numeric_evidence: int
    proper_nouns: int
    first_person_hits: int
    collective_hits: int
    relevance_overlap: float
    delivery: DeliveryMetrics

    @property
    def is_empty(self) -> bool:
        return self.token_count == 0

    @property
    def star_coverage(self) -> int:
        return len(self.star_parts)


def analyze_answer(
    question: str,
    transcript: str,
    language: str,
    delivery: DeliveryMetrics | None = None,
    duration_seconds: float = 0.0,
) -> AnswerSignals:
    text = (transcript or "").strip()
    metrics = delivery or analyze_delivery(text, duration_seconds, language)
    tokens = _WORD.findall(text)
    token_count = len(tokens)
    haystack = text if language == KOREAN else text.lower()

    star_parts = tuple(
        part
        for part, markers in phrasebook.star_markers(language).items()
        if phrasebook.contains_any(haystack, markers)
    )
    reasoning_hits = _count(haystack, phrasebook.reasoning_markers(language))
    generic_hits = _count(haystack, phrasebook.generic_markers(language))
    first_person_hits = _count(haystack, phrasebook.first_person_markers(language))
    collective_hits = _count(haystack, phrasebook.collective_markers(language))
    proper_nouns = 0 if language == KOREAN else len(set(_PROPER_NOUN.findall(text)))
    relevance_overlap = _relevance_overlap(question, text, language)

    signals = AnswerSignals(
        language=language,
        token_count=token_count,
        star_parts=star_parts,
        gaps=(),
        reasoning_hits=reasoning_hits,
        generic_hits=generic_hits,
        numeric_evidence=metrics.numeric_evidence,
        proper_nouns=proper_nouns,
        first_person_hits=first_person_hits,
        collective_hits=collective_hits,
        relevance_overlap=relevance_overlap,
        delivery=metrics,
    )
    return _with_gaps(signals)


def _with_gaps(signals: AnswerSignals) -> AnswerSignals:
    gaps = detect_gaps(signals)
    return AnswerSignals(
        language=signals.language,
        token_count=signals.token_count,
        star_parts=signals.star_parts,
        gaps=gaps,
        reasoning_hits=signals.reasoning_hits,
        generic_hits=signals.generic_hits,
        numeric_evidence=signals.numeric_evidence,
        proper_nouns=signals.proper_nouns,
        first_person_hits=signals.first_person_hits,
        collective_hits=signals.collective_hits,
        relevance_overlap=signals.relevance_overlap,
        delivery=signals.delivery,
    )


def detect_gaps(signals: AnswerSignals) -> tuple[str, ...]:
    """Which follow-up-worthy things the answer left out, in priority order."""
    if signals.is_empty:
        return (phrasebook.GAP_TOO_SHORT,)

    language = signals.language
    short = _SHORT_ANSWER_TOKENS.get(language, _SHORT_ANSWER_TOKENS["English"])
    long = _LONG_ANSWER_TOKENS.get(language, _LONG_ANSWER_TOKENS["English"])
    found: set[str] = set()

    if signals.token_count < short:
        found.add(phrasebook.GAP_TOO_SHORT)
    if "situation" not in signals.star_parts:
        found.add(phrasebook.GAP_NO_SITUATION)
    if "action" not in signals.star_parts:
        found.add(phrasebook.GAP_NO_ACTION)
    if "result" not in signals.star_parts:
        found.add(phrasebook.GAP_NO_RESULT)
    if signals.numeric_evidence == 0:
        found.add(phrasebook.GAP_NO_METRIC)
    if signals.reasoning_hits == 0:
        found.add(phrasebook.GAP_NO_REASONING)
    if signals.collective_hits >= 2 and signals.first_person_hits == 0:
        found.add(phrasebook.GAP_NO_ROLE)
    if signals.generic_hits >= 2 and signals.numeric_evidence == 0:
        found.add(phrasebook.GAP_TOO_GENERIC)
    if signals.token_count > long and signals.delivery.longest_sentence_words >= 45:
        found.add(phrasebook.GAP_RAMBLING)
    if signals.relevance_overlap < 0.08 and signals.token_count >= short:
        found.add(phrasebook.GAP_OFF_TOPIC)

    return tuple(gap for gap in phrasebook.GAP_PRIORITY if gap in found)


# -- evaluation result -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DimensionScore:
    key: str
    score: int
    comment: str = ""

    def label(self, language: str) -> str:
        return dimension_label(self.key, language)

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "score": self.score, "comment": self.comment}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DimensionScore":
        return cls(
            key=str(payload.get("key", "")),
            score=coerce_score(payload.get("score"), 0),
            comment=coerce_text(payload.get("comment", "")),
        )


@dataclass(frozen=True, slots=True)
class AnswerEvaluation:
    question_index: int = 0
    competency: str = ""
    language: str = "English"
    overall: int = 0
    band: str = "insufficient"
    dimensions: tuple[DimensionScore, ...] = field(default_factory=tuple)
    star_parts: tuple[str, ...] = field(default_factory=tuple)
    gaps: tuple[str, ...] = field(default_factory=tuple)
    strengths: tuple[str, ...] = field(default_factory=tuple)
    improvements: tuple[str, ...] = field(default_factory=tuple)
    model_answer: tuple[str, ...] = field(default_factory=tuple)
    summary: str = ""
    engine: str = PROVIDER_OFFLINE
    degraded: bool = False
    note: str = ""
    generated_at: str = ""

    @property
    def scored(self) -> bool:
        return bool(self.dimensions)

    def score_for(self, dimension_key: str) -> int:
        for item in self.dimensions:
            if item.key == dimension_key:
                return item.score
        return 0

    def score_map(self) -> dict[str, int]:
        return {item.key: item.score for item in self.dimensions}

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_index": self.question_index,
            "competency": self.competency,
            "language": self.language,
            "overall": self.overall,
            "band": self.band,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "star_parts": list(self.star_parts),
            "gaps": list(self.gaps),
            "strengths": list(self.strengths),
            "improvements": list(self.improvements),
            "model_answer": list(self.model_answer),
            "summary": self.summary,
            "engine": self.engine,
            "degraded": self.degraded,
            "note": self.note,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AnswerEvaluation":
        if not payload:
            return cls()
        dimensions = tuple(
            DimensionScore.from_dict(item)
            for item in payload.get("dimensions", []) or ()
            if isinstance(item, dict)
        )
        return cls(
            question_index=int(payload.get("question_index", 0) or 0),
            competency=str(payload.get("competency", "")),
            language=str(payload.get("language", "English")),
            overall=coerce_score(payload.get("overall"), 0),
            band=str(payload.get("band", "insufficient")),
            dimensions=dimensions,
            star_parts=tuple(str(item) for item in payload.get("star_parts", []) or ()),
            gaps=tuple(str(item) for item in payload.get("gaps", []) or ()),
            strengths=tuple(str(item) for item in payload.get("strengths", []) or ()),
            improvements=tuple(str(item) for item in payload.get("improvements", []) or ()),
            model_answer=tuple(str(item) for item in payload.get("model_answer", []) or ()),
            summary=str(payload.get("summary", "")),
            engine=str(payload.get("engine", PROVIDER_OFFLINE)),
            degraded=bool(payload.get("degraded", False)),
            note=str(payload.get("note", "")),
            generated_at=str(payload.get("generated_at", "")),
        )


# -- public entry point ------------------------------------------------------


def evaluate_answer(
    question: str,
    transcript: str,
    language: str,
    *,
    chain: ProviderChain | None = None,
    competency_key: str = "",
    interview_type: str = "hr",
    question_index: int = 0,
    duration_seconds: float = 0.0,
    delivery: DeliveryMetrics | None = None,
    effort: str = EFFORT_MEDIUM,
    role: str = "",
) -> AnswerEvaluation:
    """Score one answer, preferring a configured provider over the rule engine."""
    signals = analyze_answer(question, transcript, language, delivery, duration_seconds)
    offline = heuristic_evaluation(
        signals,
        competency_key=competency_key,
        question_index=question_index,
        language=language,
    )
    if signals.is_empty or chain is None or not chain.enabled:
        return offline

    reply = chain.complete(
        LLMRequest(
            system=_evaluation_system_prompt(language),
            user=_evaluation_user_prompt(
                question=question,
                transcript=transcript,
                language=language,
                competency_key=competency_key,
                interview_type=interview_type,
                role=role,
                signals=signals,
            ),
            purpose=PURPOSE_EVALUATION,
            max_tokens=2400,
            effort=effort,
            schema=_EVALUATION_SCHEMA,
            timeout=60.0,
        )
    )
    if reply is None or not reply.data:
        return _degraded(offline, chain.last_error or "provider returned no usable verdict")
    merged = _merge_llm_verdict(offline, reply.data, signals, reply.describe())
    return merged


def heuristic_evaluation(
    signals: AnswerSignals,
    *,
    competency_key: str = "",
    question_index: int = 0,
    language: str = "English",
) -> AnswerEvaluation:
    """The offline scorer: structural signals mapped onto the rubric."""
    if signals.is_empty:
        return AnswerEvaluation(
            question_index=question_index,
            competency=competency_key,
            language=language,
            overall=0,
            band=band_key_for_score(0),
            gaps=(phrasebook.GAP_TOO_SHORT,),
            improvements=(phrasebook.improvement_note(phrasebook.GAP_TOO_SHORT, language),),
            summary=phrasebook.report_text("not_answered", language),
            engine=PROVIDER_OFFLINE,
            generated_at=_now_iso(),
        )

    scores = {
        "structure": _structure_score(signals),
        "evidence": _evidence_score(signals),
        "impact": _impact_score(signals),
        "reasoning": _reasoning_score(signals),
        "relevance": _relevance_score(signals),
        "delivery": float(signals.delivery.score),
    }
    overall = weighted_overall(scores)
    dimensions = tuple(
        DimensionScore(key=key, score=int(round(clamp_score(value))))
        for key, value in scores.items()
    )
    strengths = tuple(
        phrasebook.strength_note(key, language)
        for key, value in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if value >= 70
    )[:3]
    improvements = tuple(
        phrasebook.improvement_note(gap, language) for gap in signals.gaps[:3]
    )
    return AnswerEvaluation(
        question_index=question_index,
        competency=competency_key,
        language=language,
        overall=overall,
        band=band_key_for_score(overall),
        dimensions=dimensions,
        star_parts=signals.star_parts,
        gaps=signals.gaps,
        strengths=strengths,
        improvements=improvements,
        model_answer=(),
        summary=_heuristic_summary(signals, overall, language),
        engine=PROVIDER_OFFLINE,
        generated_at=_now_iso(),
    )


# -- heuristic scoring -------------------------------------------------------


def _structure_score(signals: AnswerSignals) -> float:
    base = 22.0 * signals.star_coverage
    if {"situation", "action", "result"} <= set(signals.star_parts):
        base += 10.0
    if signals.delivery.sentence_count >= 3:
        base += 4.0
    return clamp_score(base)


def _evidence_score(signals: AnswerSignals) -> float:
    language = signals.language
    short = _SHORT_ANSWER_TOKENS.get(language, _SHORT_ANSWER_TOKENS["English"])
    base = 34.0
    base += min(26.0, signals.token_count / short * 16.0)
    base += min(18.0, signals.numeric_evidence * 4.5)
    base += min(10.0, signals.proper_nouns * 3.0)
    base += min(10.0, signals.first_person_hits * 2.5)
    base -= min(22.0, signals.generic_hits * 7.0)
    return clamp_score(base)


def _impact_score(signals: AnswerSignals) -> float:
    base = 30.0
    if "result" in signals.star_parts:
        base += 28.0
    base += min(28.0, signals.numeric_evidence * 7.0)
    if phrasebook.GAP_NO_ROLE in signals.gaps:
        base -= 12.0
    return clamp_score(base)


def _reasoning_score(signals: AnswerSignals) -> float:
    base = 32.0 + min(40.0, signals.reasoning_hits * 13.0)
    if "task" in signals.star_parts:
        base += 8.0
    base -= min(14.0, signals.generic_hits * 5.0)
    return clamp_score(base)


def _relevance_score(signals: AnswerSignals) -> float:
    if phrasebook.GAP_OFF_TOPIC in signals.gaps:
        return 34.0
    return clamp_score(40.0 + signals.relevance_overlap * 95.0)


def _heuristic_summary(signals: AnswerSignals, overall: int, language: str) -> str:
    gap_text = ", ".join(phrasebook.gap_label(gap, language) for gap in signals.gaps[:2])
    return phrasebook.answer_summary(signals.star_coverage, overall, gap_text, language)


def _relevance_overlap(question: str, answer: str, language: str) -> float:
    stop = phrasebook.question_stopwords(language)
    question_tokens = {
        token if language == KOREAN else token.lower()
        for token in _WORD.findall(question or "")
        if len(token) > 1
    } - stop
    if not question_tokens:
        return 0.5
    answer_text = answer if language == KOREAN else answer.lower()
    hits = 0
    for token in question_tokens:
        probe = token[:2] if language == KOREAN and len(token) > 2 else token
        if probe and probe in answer_text:
            hits += 1
    return hits / len(question_tokens)


def _count(text: str, markers: tuple[str, ...]) -> int:
    return sum(text.count(marker) for marker in markers)


# -- LLM path ----------------------------------------------------------------

_EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "properties": {key: {"type": "integer", "minimum": 0, "maximum": 100} for key in _JUDGED_DIMENSIONS},
            "required": list(_JUDGED_DIMENSIONS),
            "additionalProperties": False,
        },
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string", "enum": list(phrasebook.GAP_KEYS)}},
        "model_answer": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["scores", "summary", "strengths", "improvements", "gaps", "model_answer"],
    "additionalProperties": False,
}


def _evaluation_system_prompt(language: str) -> str:
    response_language = "Korean" if language == KOREAN else "English"
    dimension_lines = "\n".join(
        f"- {key}: {dimension_label(key, 'English')} — {_dimension_question(key, language)}"
        for key in _JUDGED_DIMENSIONS
    )
    return (
        "You are a senior interview assessor calibrating a hiring panel. "
        "You score one answer at a time against a fixed rubric and you justify every number.\n\n"
        f"Score these dimensions from 0 to 100:\n{dimension_lines}\n\n"
        "Calibration: 85+ means a hiring panel would cite this answer as evidence; "
        "70-84 is solid with a named weakness; 55-69 is unremarkable but acceptable; "
        "40-54 lacks the specifics to judge; below 40 means the answer does not support any claim.\n"
        "Do not reward length, confidence, or enthusiasm. Reward verifiable specifics and stated reasoning.\n"
        f"Write every string in {response_language}. Keep each strength, improvement, and outline item to one sentence. "
        "Return at most 3 strengths, 3 improvements, and 4 model_answer outline items."
    )


def _dimension_question(key: str, language: str) -> str:
    return dimension(key).prompt_question(language)


def _evaluation_user_prompt(
    *,
    question: str,
    transcript: str,
    language: str,
    competency_key: str,
    interview_type: str,
    role: str,
    signals: AnswerSignals,
) -> str:
    target = competency(competency_key)
    metrics = signals.delivery
    lines = [
        f"Interview type: {interview_type}",
        f"Target competency: {target.key} — {target.focus('English')}",
    ]
    if role:
        lines.append(f"Role being hired for: {role}")
    lines.extend(
        [
            "",
            f"Question asked:\n{question}",
            "",
            f"Candidate answer (speech transcript, punctuation may be imperfect):\n{transcript}",
            "",
            "Locally measured delivery signals (already scored separately — use as context only):",
            f"- spoken units: {signals.token_count}",
            f"- pace: {metrics.pace} ({metrics.words_per_minute:.0f} per minute)",
            f"- filler rate: {metrics.filler_rate:.1f} per 100 units",
            f"- numeric evidence found: {signals.numeric_evidence}",
            f"- STAR elements detected by rule engine: {', '.join(signals.star_parts) or 'none'}",
            "",
            "Judge the content yourself; the rule engine can be wrong about STAR elements. "
            "In `gaps`, list only the gaps that genuinely apply. "
            "In `model_answer`, outline how a strong candidate would have structured this answer.",
        ]
    )
    return "\n".join(lines)


def _merge_llm_verdict(
    offline: AnswerEvaluation,
    data: dict[str, Any],
    signals: AnswerSignals,
    engine: str,
) -> AnswerEvaluation:
    raw_scores = data.get("scores")
    if not isinstance(raw_scores, dict):
        return _degraded(offline, "provider verdict had no scores")

    scores: dict[str, float] = {}
    for key in _JUDGED_DIMENSIONS:
        if key in raw_scores:
            scores[key] = float(coerce_score(raw_scores.get(key), offline.score_for(key)))
    if not scores:
        return _degraded(offline, "provider verdict had no usable scores")
    # Delivery is measured locally; a model guessing at pace from a transcript
    # would be inventing data.
    scores["delivery"] = float(signals.delivery.score)

    overall = weighted_overall(scores)
    dimensions = tuple(
        DimensionScore(key=key, score=int(round(clamp_score(value)))) for key, value in scores.items()
    )
    gaps = tuple(
        gap for gap in phrasebook.GAP_PRIORITY if gap in set(coerce_text_list(data.get("gaps"), 6, 40))
    )
    language = offline.language
    improvements = tuple(coerce_text_list(data.get("improvements"), 3)) or offline.improvements
    return AnswerEvaluation(
        question_index=offline.question_index,
        competency=offline.competency,
        language=language,
        overall=overall,
        band=band_key_for_score(overall),
        dimensions=dimensions,
        star_parts=signals.star_parts,
        gaps=gaps or offline.gaps,
        strengths=tuple(coerce_text_list(data.get("strengths"), 3)) or offline.strengths,
        improvements=improvements,
        model_answer=tuple(coerce_text_list(data.get("model_answer"), 4, 320)),
        summary=coerce_text(data.get("summary"), 400) or offline.summary,
        engine=engine,
        degraded=False,
        note="",
        generated_at=_now_iso(),
    )


def _degraded(offline: AnswerEvaluation, note: str) -> AnswerEvaluation:
    return AnswerEvaluation(
        question_index=offline.question_index,
        competency=offline.competency,
        language=offline.language,
        overall=offline.overall,
        band=offline.band,
        dimensions=offline.dimensions,
        star_parts=offline.star_parts,
        gaps=offline.gaps,
        strengths=offline.strengths,
        improvements=offline.improvements,
        model_answer=offline.model_answer,
        summary=offline.summary,
        engine=PROVIDER_OFFLINE,
        degraded=True,
        note=note,
        generated_at=offline.generated_at or _now_iso(),
    )
