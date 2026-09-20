from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ai_interviewer.intelligence.blueprint import InterviewBlueprint, build_blueprint
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.pipeline import AnswerInsight, build_session_report
from ai_interviewer.intelligence.report import SessionReport
from ai_interviewer.question_parser import ParsedQuestion
from ai_interviewer.session_store import InterviewSession, QuestionRecord
from ai_interviewer.tts.base import SpeechResult


class SpeechProvider(Protocol):
    def resolve_voice(self, text: str) -> tuple[str, str]:
        ...

    def speak(
        self,
        text: str,
        cache_key: str,
        language: str | None = None,
        speaker: str | None = None,
    ) -> SpeechResult:
        ...


class InterviewEngine:
    """Drives one interview: question order, timing, and the analysis record.

    The engine owns the blueprint so every screen can ask what the current
    question is *for* — which competency, which stage — instead of treating the
    interview as an undifferentiated list of strings.
    """

    def __init__(
        self,
        questions: list[ParsedQuestion],
        sessions_root: Path,
        *,
        blueprint: InterviewBlueprint | None = None,
        interview_type: str = "",
        language: str = "",
        role: str = "",
    ):
        if not questions:
            raise ValueError("At least one question is required.")
        self.questions = questions
        self.sessions_root = Path(sessions_root)
        self.current_index = 0
        self.interview_type = interview_type
        self.language = language
        self.role = role
        self.session = InterviewSession.create(
            questions=questions,
            sessions_root=self.sessions_root,
            interview_type=interview_type,
            language=language,
            role=role,
        )
        self.blueprint = blueprint or self._default_blueprint()
        self._apply_blueprint()

    # -- blueprint ----------------------------------------------------------

    def _default_blueprint(self) -> InterviewBlueprint:
        return build_blueprint(
            [question.clean for question in self.questions],
            self.language or "English",
            self.interview_type or "hr",
            role=self.role,
        )

    def _apply_blueprint(self) -> None:
        self.session.set_blueprint(self.blueprint.to_dict())
        self.session.save()

    def attach_blueprint(self, blueprint: InterviewBlueprint) -> None:
        """Replace the plan without restarting; question text is unchanged."""
        self.blueprint = blueprint
        self._apply_blueprint()

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def current_record(self) -> QuestionRecord:
        return self.session.record_at(self.current_index)

    @property
    def current_competency(self) -> str:
        planned = self.blueprint.question_at(self.current_index)
        if planned is not None:
            return planned.competency
        return self.current_record.competency

    @property
    def current_stage(self) -> str:
        planned = self.blueprint.question_at(self.current_index)
        if planned is not None:
            return planned.stage
        return self.current_record.stage

    def competency_for(self, index: int) -> str:
        planned = self.blueprint.question_at(index)
        if planned is not None:
            return planned.competency
        return self.session.record_at(index).competency

    def coverage(self) -> dict[str, int]:
        """Competencies with at least one scored answer, and how many."""
        counts: dict[str, int] = {key: 0 for key in self.blueprint.focus}
        for index in range(self.question_count):
            record = self.session.record_at(index)
            if not record.evaluation:
                continue
            key = record.competency or self.competency_for(index)
            if key:
                counts[key] = counts.get(key, 0) + 1
        return counts

    def answered_count(self) -> int:
        return sum(1 for record in self.session.records if record.transcript.strip())

    def scored_count(self) -> int:
        return sum(1 for record in self.session.records if record.evaluation)

    # -- answer bookkeeping --------------------------------------------------

    def set_current_memo(self, memo: str) -> None:
        self.session.set_memo(self.current_index, memo)

    def finish_current_answer(self) -> None:
        self.session.finish_answer(self.current_index)
        self.session.save()

    def current_answer_seconds(self) -> float:
        record = self.current_record
        if record.answer_seconds is not None:
            return float(record.answer_seconds)
        return 0.0

    def probe_depth(self, index: int | None = None) -> int:
        target = self.current_index if index is None else index
        return self.session.probe_depth(target)

    def record_insight(self, insight: AnswerInsight, index: int | None = None) -> None:
        """Persist one analysis pass: score, delivery, and any probe asked."""
        target = self.current_index if index is None else index
        self.session.set_evaluation(target, insight.evaluation.to_dict())
        self.session.set_delivery(target, insight.delivery.to_dict())
        if insight.has_probe:
            self.session.append_probe(target, insight.probe.to_dict())
        self.session.save()

    # -- navigation ---------------------------------------------------------

    def move_next(self) -> QuestionRecord:
        self.finish_current_answer()
        if self.current_index < self.question_count - 1:
            self.current_index += 1
        return self.current_record

    def move_previous(self) -> QuestionRecord:
        self.finish_current_answer()
        if self.current_index > 0:
            self.current_index -= 1
        return self.current_record

    def restart(self) -> None:
        self.finish_current_answer()
        self.session.save()
        self.session = InterviewSession.create(
            questions=self.questions,
            sessions_root=self.sessions_root,
            interview_type=self.interview_type,
            language=self.language,
            role=self.role,
        )
        self.current_index = 0
        self._apply_blueprint()

    # -- speech -------------------------------------------------------------

    def speak_current(self, provider: SpeechProvider, repeat: bool = False) -> SpeechResult:
        index = self.current_index
        if repeat:
            self.session.increment_repeat(index)

        record = self.session.record_at(index)
        language, speaker = provider.resolve_voice(record.clean_question)
        self.session.mark_tts_started(index, language=language, speaker=speaker)
        self.session.save()
        try:
            result = provider.speak(
                text=record.clean_question,
                cache_key=self._cache_key(record),
                language=language,
                speaker=speaker,
            )
        except Exception:
            self.session.mark_tts_finished(index)
            self.session.save()
            raise

        self.session.mark_tts_result(index, backend=result.backend, warning=result.warning)
        self.session.mark_tts_finished(index)
        self.session.start_answer(index)
        self.session.save()
        return result

    def _cache_key(self, record: QuestionRecord) -> str:
        return f"{self.session.session_id}-{record.question_index}"

    # -- reporting ----------------------------------------------------------

    def build_report(self, chain: ProviderChain | None = None, effort: str = "high") -> SessionReport:
        """Score the session as a whole and persist it beside the transcripts."""
        report = build_session_report(
            self.session.records,
            session_id=self.session.session_id,
            language=self.language or self.blueprint.language,
            interview_type=self.interview_type or self.blueprint.interview_type,
            blueprint=self.blueprint,
            role=self.role,
            seniority=self.blueprint.seniority,
            chain=chain,
            effort=effort,
        )
        self.session.set_report(report.to_dict())
        self.session.save()
        return report
