"""Interview blueprints: the plan behind the question list.

A flat list of questions cannot tell you whether an interview actually covered
what it set out to measure. A blueprint tags every question with a competency
and a stage, which is what lets the workspace show coverage live and lets the
report weight the score. Built offline from a question pack, or authored by a
provider from a role and a job description.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.llm.base import (
    EFFORT_HIGH,
    PROVIDER_OFFLINE,
    PURPOSE_BLUEPRINT,
    LLMRequest,
    coerce_text,
)
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.rubric import (
    COMPETENCY_KEYS,
    DEFAULT_COMPETENCY,
    KOREAN,
    competencies_for_interview_type,
    competency,
)


SOURCE_PACK = "pack"
SOURCE_LLM = "llm"
SOURCE_CUSTOM = "custom"

SENIORITY_LEVELS: tuple[str, ...] = ("junior", "mid", "senior", "lead")
DEFAULT_SENIORITY = "mid"

_STAGE_BUDGETS: dict[str, int] = {
    phrasebook.STAGE_OPENING: 60,
    phrasebook.STAGE_CORE: 90,
    phrasebook.STAGE_DEEP_DIVE: 120,
    phrasebook.STAGE_CLOSING: 45,
}

DEFAULT_QUESTION_COUNT = 8
MAX_QUESTION_COUNT = 20


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_seniority(value: str) -> str:
    candidate = (value or "").strip().lower()
    return candidate if candidate in SENIORITY_LEVELS else DEFAULT_SENIORITY


@dataclass(frozen=True, slots=True)
class PlannedQuestion:
    text: str
    competency: str = DEFAULT_COMPETENCY.key
    stage: str = phrasebook.STAGE_CORE
    intent: str = ""
    time_budget_seconds: int = 90
    source: str = SOURCE_PACK

    def competency_label(self, language: str) -> str:
        return competency(self.competency).label(language)

    def stage_label(self, language: str) -> str:
        return phrasebook.stage_label(self.stage, language)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "competency": self.competency,
            "stage": self.stage,
            "intent": self.intent,
            "time_budget_seconds": self.time_budget_seconds,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannedQuestion":
        stage = str(payload.get("stage", phrasebook.STAGE_CORE))
        return cls(
            text=str(payload.get("text", "")),
            competency=_valid_competency(payload.get("competency")),
            stage=stage if stage in phrasebook.STAGE_KEYS else phrasebook.STAGE_CORE,
            intent=str(payload.get("intent", "")),
            time_budget_seconds=int(payload.get("time_budget_seconds", 90) or 90),
            source=str(payload.get("source", SOURCE_PACK)),
        )


@dataclass(frozen=True, slots=True)
class InterviewBlueprint:
    language: str = "English"
    interview_type: str = "hr"
    role: str = ""
    seniority: str = DEFAULT_SENIORITY
    questions: tuple[PlannedQuestion, ...] = field(default_factory=tuple)
    focus: tuple[str, ...] = field(default_factory=tuple)
    engine: str = PROVIDER_OFFLINE
    notes: str = ""
    generated_at: str = ""

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def total_budget_seconds(self) -> int:
        return sum(item.time_budget_seconds for item in self.questions)

    def question_at(self, index: int) -> PlannedQuestion | None:
        if 0 <= index < len(self.questions):
            return self.questions[index]
        return None

    def question_texts(self) -> tuple[str, ...]:
        return tuple(item.text for item in self.questions)

    def coverage(self) -> dict[str, int]:
        """How many questions target each competency, focus areas included at 0."""
        counts = {key: 0 for key in self.focus}
        for item in self.questions:
            counts[item.competency] = counts.get(item.competency, 0) + 1
        return counts

    def stage_counts(self) -> dict[str, int]:
        counts = {stage: 0 for stage in phrasebook.STAGE_KEYS}
        for item in self.questions:
            counts[item.stage] = counts.get(item.stage, 0) + 1
        return counts

    def uncovered_focus(self) -> tuple[str, ...]:
        covered = {item.competency for item in self.questions}
        return tuple(key for key in self.focus if key not in covered)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "interview_type": self.interview_type,
            "role": self.role,
            "seniority": self.seniority,
            "questions": [item.to_dict() for item in self.questions],
            "focus": list(self.focus),
            "engine": self.engine,
            "notes": self.notes,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "InterviewBlueprint":
        if not payload:
            return cls()
        questions = tuple(
            PlannedQuestion.from_dict(item)
            for item in payload.get("questions", []) or ()
            if isinstance(item, dict)
        )
        return cls(
            language=str(payload.get("language", "English")),
            interview_type=str(payload.get("interview_type", "hr")),
            role=str(payload.get("role", "")),
            seniority=normalize_seniority(str(payload.get("seniority", DEFAULT_SENIORITY))),
            questions=questions,
            focus=tuple(str(item) for item in payload.get("focus", []) or ()),
            engine=str(payload.get("engine", PROVIDER_OFFLINE)),
            notes=str(payload.get("notes", "")),
            generated_at=str(payload.get("generated_at", "")),
        )


# -- offline tagging ---------------------------------------------------------


def tag_competency(question: str, language: str, interview_type: str = "hr") -> str:
    """Best-effort competency for a question, from its wording."""
    text = question if language == KOREAN else question.lower()
    table = phrasebook.competency_keywords(language)
    for key in phrasebook.COMPETENCY_TAG_ORDER:
        markers = table.get(key, ())
        if markers and phrasebook.contains_any(text, markers):
            return key
    focus = competencies_for_interview_type(interview_type)
    return focus[0] if focus else DEFAULT_COMPETENCY.key


def tag_stage(question: str, language: str, index: int, total: int) -> str:
    text = question if language == KOREAN else question.lower()
    if phrasebook.contains_any(text, phrasebook.opening_markers(language)):
        return phrasebook.STAGE_OPENING
    if phrasebook.contains_any(text, phrasebook.closing_markers(language)):
        return phrasebook.STAGE_CLOSING
    if total <= 2:
        return phrasebook.STAGE_CORE
    if index == 0:
        return phrasebook.STAGE_OPENING
    if index >= total - 1:
        return phrasebook.STAGE_CLOSING
    # The back half of the core block is where a panel goes deeper.
    return phrasebook.STAGE_DEEP_DIVE if index >= max(2, int(total * 0.6)) else phrasebook.STAGE_CORE


def build_blueprint(
    questions: Sequence[str],
    language: str,
    interview_type: str = "hr",
    *,
    role: str = "",
    seniority: str = DEFAULT_SENIORITY,
    source: str = SOURCE_PACK,
) -> InterviewBlueprint:
    """Tag an existing question list; never reorders or rewrites it."""
    cleaned = [text.strip() for text in questions if text and text.strip()]
    total = len(cleaned)
    planned: list[PlannedQuestion] = []
    for index, text in enumerate(cleaned):
        stage = tag_stage(text, language, index, total)
        planned.append(
            PlannedQuestion(
                text=text,
                competency=tag_competency(text, language, interview_type),
                stage=stage,
                time_budget_seconds=_STAGE_BUDGETS.get(stage, 90),
                source=source,
            )
        )
    return InterviewBlueprint(
        language=language,
        interview_type=interview_type,
        role=role.strip(),
        seniority=normalize_seniority(seniority),
        questions=tuple(planned),
        focus=competencies_for_interview_type(interview_type),
        engine=PROVIDER_OFFLINE,
        generated_at=_now_iso(),
    )


# -- provider-authored plan --------------------------------------------------

_BLUEPRINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "notes": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "competency": {"type": "string", "enum": list(COMPETENCY_KEYS)},
                    "stage": {"type": "string", "enum": list(phrasebook.STAGE_KEYS)},
                    "intent": {"type": "string"},
                },
                "required": ["text", "competency", "stage", "intent"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["notes", "questions"],
    "additionalProperties": False,
}


def generate_blueprint(
    *,
    chain: ProviderChain | None,
    language: str,
    interview_type: str = "hr",
    role: str = "",
    seniority: str = DEFAULT_SENIORITY,
    job_description: str = "",
    resume_summary: str = "",
    question_count: int = DEFAULT_QUESTION_COUNT,
    fallback_questions: Sequence[str] = (),
    effort: str = EFFORT_HIGH,
) -> InterviewBlueprint:
    """Ask a provider to author a role-specific plan; fall back to the pack."""
    fallback = build_blueprint(
        fallback_questions,
        language,
        interview_type,
        role=role,
        seniority=seniority,
    )
    if chain is None or not chain.enabled:
        return fallback

    count = max(3, min(int(question_count), MAX_QUESTION_COUNT))
    reply = chain.complete(
        LLMRequest(
            system=_blueprint_system_prompt(language, count),
            user=_blueprint_user_prompt(
                language=language,
                interview_type=interview_type,
                role=role,
                seniority=seniority,
                job_description=job_description,
                resume_summary=resume_summary,
                count=count,
            ),
            purpose=PURPOSE_BLUEPRINT,
            max_tokens=4000,
            effort=effort,
            schema=_BLUEPRINT_SCHEMA,
            timeout=120.0,
        )
    )
    if reply is None or not reply.data:
        return fallback

    raw = reply.data.get("questions")
    if not isinstance(raw, list) or not raw:
        return fallback

    planned: list[PlannedQuestion] = []
    for item in raw[:count]:
        if not isinstance(item, dict):
            continue
        text = coerce_text(item.get("text"), 400)
        if not text:
            continue
        stage = str(item.get("stage", phrasebook.STAGE_CORE))
        if stage not in phrasebook.STAGE_KEYS:
            stage = phrasebook.STAGE_CORE
        planned.append(
            PlannedQuestion(
                text=text,
                competency=_valid_competency(item.get("competency")),
                stage=stage,
                intent=coerce_text(item.get("intent"), 200),
                time_budget_seconds=_STAGE_BUDGETS.get(stage, 90),
                source=SOURCE_LLM,
            )
        )
    if not planned:
        return fallback

    return InterviewBlueprint(
        language=language,
        interview_type=interview_type,
        role=role.strip(),
        seniority=normalize_seniority(seniority),
        questions=tuple(_ordered(planned)),
        focus=competencies_for_interview_type(interview_type),
        engine=reply.describe(),
        notes=coerce_text(reply.data.get("notes"), 600),
        generated_at=_now_iso(),
    )


def _ordered(planned: list[PlannedQuestion]) -> list[PlannedQuestion]:
    """Keep the provider's order inside each stage, but keep stages in order."""
    order = {stage: index for index, stage in enumerate(phrasebook.STAGE_KEYS)}
    return sorted(planned, key=lambda item: order.get(item.stage, 1))


def _valid_competency(value: Any) -> str:
    candidate = str(value or "").strip()
    return candidate if candidate in COMPETENCY_KEYS else DEFAULT_COMPETENCY.key


def _blueprint_system_prompt(language: str, count: int) -> str:
    response_language = "Korean" if language == KOREAN else "English"
    stage_lines = "\n".join(
        f"- {stage}: {phrasebook.stage_label(stage, 'English')}" for stage in phrasebook.STAGE_KEYS
    )
    competency_lines = "\n".join(
        f"- {item.key}: {item.focus('English')}" for item in (competency(key) for key in COMPETENCY_KEYS)
    )
    return (
        "You design interview loops. Given a role, you produce the question plan a "
        "well-run panel would actually use.\n\n"
        f"Produce exactly {count} questions across these stages, in this order:\n{stage_lines}\n\n"
        f"Tag each question with the competency it is meant to measure:\n{competency_lines}\n\n"
        "Rules:\n"
        "- One opening question, one closing question, the rest split between core and deep dive.\n"
        "- Every question must be answerable from experience the candidate already has. "
        "No puzzles, no trivia, no hypotheticals that invite invention.\n"
        "- Ask for one thing per question. A question with two clauses gets half an answer.\n"
        "- Cover the listed focus competencies before repeating one.\n"
        "- `intent` is a private note to the interviewer on what a strong answer contains.\n"
        f"- Write `text` in {response_language}; write `intent` in {response_language} too.\n"
        "- `notes` is a two-sentence summary of how the loop is structured."
    )


def _blueprint_user_prompt(
    *,
    language: str,
    interview_type: str,
    role: str,
    seniority: str,
    job_description: str,
    resume_summary: str,
    count: int,
) -> str:
    focus = competencies_for_interview_type(interview_type)
    lines = [
        f"Interview type: {interview_type}",
        f"Role: {role or 'not specified'}",
        f"Seniority: {normalize_seniority(seniority)}",
        f"Interview language: {language}",
        f"Questions requested: {count}",
        f"Priority competencies: {', '.join(focus)}",
    ]
    if job_description.strip():
        lines.extend(["", "Job description provided by the user:", job_description.strip()[:4000]])
    if resume_summary.strip():
        lines.extend(["", "Candidate background provided by the user:", resume_summary.strip()[:4000]])
    if not job_description.strip() and not resume_summary.strip():
        lines.append("")
        lines.append("No job description was provided; design the loop from the role and seniority alone.")
    return "\n".join(lines)
