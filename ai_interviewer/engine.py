from __future__ import annotations

from pathlib import Path
from typing import Protocol

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
    def __init__(self, questions: list[ParsedQuestion], sessions_root: Path):
        if not questions:
            raise ValueError("At least one question is required.")
        self.questions = questions
        self.sessions_root = Path(sessions_root)
        self.current_index = 0
        self.session = InterviewSession.create(questions=questions, sessions_root=self.sessions_root)

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def current_record(self) -> QuestionRecord:
        return self.session.record_at(self.current_index)

    def set_current_memo(self, memo: str) -> None:
        self.session.set_memo(self.current_index, memo)

    def finish_current_answer(self) -> None:
        self.session.finish_answer(self.current_index)
        self.session.save()

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
        self.session = InterviewSession.create(questions=self.questions, sessions_root=self.sessions_root)
        self.current_index = 0

    def speak_current(self, provider: SpeechProvider, repeat: bool = False) -> SpeechResult:
        index = self.current_index
        if repeat:
            self.session.increment_repeat(index)

        record = self.session.record_at(index)
        language, speaker = provider.resolve_voice(record.clean_question)
        self.session.mark_tts_started(index, language=language, speaker=speaker)
        self.session.save()
        try:
            return provider.speak(
                text=record.clean_question,
                cache_key=self._cache_key(record),
                language=language,
                speaker=speaker,
            )
        finally:
            self.session.mark_tts_finished(index)
            self.session.start_answer(index)
            self.session.save()

    def _cache_key(self, record: QuestionRecord) -> str:
        return f"{self.session.session_id}-{record.question_index}"
