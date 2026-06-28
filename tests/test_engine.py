from pathlib import Path

from ai_interviewer.engine import InterviewEngine
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.tts.base import SpeechResult


class FakeTTSProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resolve_voice(self, text: str) -> tuple[str, str]:
        if "자기소개" in text:
            return "Korean", "Sohee"
        return "English", "Ryan"

    def speak(
        self,
        text: str,
        cache_key: str,
        language: str | None = None,
        speaker: str | None = None,
    ) -> SpeechResult:
        self.calls.append(text)
        return SpeechResult(wav_path=Path("fake.wav"), language=language or "English", speaker=speaker or "Ryan")


class FailingTTSProvider(FakeTTSProvider):
    def speak(
        self,
        text: str,
        cache_key: str,
        language: str | None = None,
        speaker: str | None = None,
    ) -> SpeechResult:
        raise RuntimeError("tts failed")


def test_engine_repeat_and_restart_flow(tmp_path) -> None:
    engine = InterviewEngine(parse_questions("1. 자기소개\n2. Strength?"), tmp_path)
    provider = FakeTTSProvider()

    engine.speak_current(provider)
    assert engine.current_record.answer_started_at
    assert engine.current_record.repeat_count == 0

    engine.speak_current(provider, repeat=True)
    assert engine.current_record.repeat_count == 1

    first_session_id = engine.session.session_id
    engine.move_next()
    assert engine.current_record.clean_question == "Strength?"

    engine.restart()
    assert engine.session.session_id != first_session_id
    assert engine.current_index == 0
    assert engine.current_record.clean_question == "자기소개"


def test_engine_tts_failure_does_not_start_answer_timer(tmp_path) -> None:
    engine = InterviewEngine(parse_questions("1. 자기소개"), tmp_path)

    try:
        engine.speak_current(FailingTTSProvider())
    except RuntimeError:
        pass

    record = engine.current_record
    assert record.tts_started_at
    assert record.tts_finished_at
    assert not record.answer_started_at
    assert record.answer_seconds is None
