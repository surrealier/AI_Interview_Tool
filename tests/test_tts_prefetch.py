from __future__ import annotations

from pathlib import Path

from ai_interviewer.engine import InterviewEngine
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.tts.base import SpeechResult


QUESTIONS = "1. First question?\n2. Second question?\n3. Third question?"


class RecordingProvider:
    """Records what was spoken versus what was only warmed into the cache."""

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.prefetched: list[tuple[str, str]] = []

    def resolve_voice(self, text: str) -> tuple[str, str]:
        return ("English", "Ryan")

    def speak(self, text, cache_key, language=None, speaker=None) -> SpeechResult:
        self.spoken.append(text)
        return SpeechResult(wav_path=Path("x.wav"), language=language or "English", speaker=speaker or "Ryan")

    def prefetch(self, text, cache_key, language, speaker) -> bool:
        self.prefetched.append((text, cache_key))
        return True


class NoPrefetchProvider(RecordingProvider):
    """An older provider without prefetch support."""

    prefetch = None  # type: ignore[assignment]


def _engine(tmp_path) -> InterviewEngine:
    return InterviewEngine(parse_questions(QUESTIONS), tmp_path, language="English")


def test_next_question_audio_points_at_the_upcoming_question(tmp_path) -> None:
    engine = _engine(tmp_path)
    upcoming = engine.next_question_audio()
    assert upcoming is not None
    text, cache_key = upcoming
    assert text == "Second question?"
    assert cache_key.endswith("-2")


def test_there_is_nothing_to_prefetch_on_the_last_question(tmp_path) -> None:
    engine = _engine(tmp_path)
    engine.current_index = engine.question_count - 1
    assert engine.next_question_audio() is None
    assert engine.prefetch_next_question(RecordingProvider()) is False


def test_prefetch_warms_the_next_question_without_speaking_it(tmp_path) -> None:
    engine = _engine(tmp_path)
    provider = RecordingProvider()

    engine.speak_current(provider)
    assert provider.spoken == ["First question?"]

    assert engine.prefetch_next_question(provider) is True
    assert provider.prefetched == [("Second question?", f"{engine.session.session_id}-2")]
    # Prefetching must never play audio at the candidate.
    assert provider.spoken == ["First question?"]


def test_prefetch_uses_the_same_cache_key_the_next_speak_will_ask_for(tmp_path) -> None:
    """The warm cache is only useful if the keys line up exactly."""
    engine = _engine(tmp_path)
    provider = RecordingProvider()
    engine.speak_current(provider)
    engine.prefetch_next_question(provider)
    prefetched_key = provider.prefetched[0][1]

    engine.move_next()
    record = engine.current_record
    assert engine._cache_key(record) == prefetched_key


def test_a_provider_without_prefetch_is_tolerated(tmp_path) -> None:
    engine = _engine(tmp_path)
    assert engine.prefetch_next_question(NoPrefetchProvider()) is False


def test_prefetch_failure_never_breaks_the_interview(tmp_path) -> None:
    class FailingProvider(RecordingProvider):
        def prefetch(self, text, cache_key, language, speaker) -> bool:
            return False

    engine = _engine(tmp_path)
    assert engine.prefetch_next_question(FailingProvider()) is False
    # The interview can still advance and speak.
    provider = RecordingProvider()
    engine.move_next()
    engine.speak_current(provider)
    assert provider.spoken == ["Second question?"]
