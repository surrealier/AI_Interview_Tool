"""Delivery analytics: how the answer sounded, measured locally.

Everything here runs offline on the transcript plus the recorded duration, so
pace and filler feedback is available even when no LLM is configured. The
numbers also feed the `delivery` dimension of the rubric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.rubric import ENGLISH, KOREAN, clamp_score


PACE_SLOW = "slow"
PACE_STEADY = "steady"
PACE_FAST = "fast"
PACE_UNKNOWN = "unknown"

# Comfortable interview pace, per language. Korean is counted in word chunks
# (space-separated eojeol), which run longer than English words.
_PACE_BANDS: dict[str, tuple[int, int]] = {
    # A Korean word chunk averages a little over three syllables, so a
    # comfortable 5-6 syllables per second lands near 95-115 chunks a minute.
    KOREAN: (75, 135),
    ENGLISH: (110, 175),
}

# Below this many spoken units the pace reading is noise, not a signal.
_MIN_WORDS_FOR_PACE = 12
_MIN_SECONDS_FOR_PACE = 8.0

# Hangul syllable block, built from code points so this module holds no
# interview content of its own.
_HANGUL_RANGE = f"{chr(0xAC00)}-{chr(0xD7A3)}"

_SENTENCE_SPLIT = re.compile(r"[.!?。！？\n]+")
_PUNCTUATION = re.compile(r"[.!?。！？]")
_NUMBER = re.compile(phrasebook.NUMBER_PATTERN)
_MEASUREMENT = re.compile(phrasebook.MEASUREMENT_PATTERN, re.IGNORECASE)
_TOKEN_STRIP = re.compile(rf"^[^\w{_HANGUL_RANGE}]+|[^\w{_HANGUL_RANGE}]+$")


@dataclass(frozen=True, slots=True)
class DeliveryMetrics:
    language: str = ENGLISH
    duration_seconds: float = 0.0
    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0
    avg_sentence_words: float = 0.0
    longest_sentence_words: int = 0
    words_per_minute: float = 0.0
    filler_count: int = 0
    filler_rate: float = 0.0
    hedge_count: int = 0
    numeric_evidence: int = 0
    distinct_ratio: float = 0.0
    pace: str = PACE_UNKNOWN
    score: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def measured(self) -> bool:
        return self.word_count > 0

    def pace_label(self, language: str | None = None) -> str:
        return phrasebook.pace_label(self.pace, language or self.language)

    def note_texts(self, language: str | None = None) -> tuple[str, ...]:
        target = language or self.language
        return tuple(phrasebook.delivery_note(key, target) for key in self.notes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "duration_seconds": round(self.duration_seconds, 2),
            "word_count": self.word_count,
            "char_count": self.char_count,
            "sentence_count": self.sentence_count,
            "avg_sentence_words": round(self.avg_sentence_words, 2),
            "longest_sentence_words": self.longest_sentence_words,
            "words_per_minute": round(self.words_per_minute, 1),
            "filler_count": self.filler_count,
            "filler_rate": round(self.filler_rate, 2),
            "hedge_count": self.hedge_count,
            "numeric_evidence": self.numeric_evidence,
            "distinct_ratio": round(self.distinct_ratio, 3),
            "pace": self.pace,
            "score": self.score,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "DeliveryMetrics":
        if not payload:
            return cls()
        return cls(
            language=str(payload.get("language", ENGLISH)),
            duration_seconds=float(payload.get("duration_seconds", 0.0) or 0.0),
            word_count=int(payload.get("word_count", 0) or 0),
            char_count=int(payload.get("char_count", 0) or 0),
            sentence_count=int(payload.get("sentence_count", 0) or 0),
            avg_sentence_words=float(payload.get("avg_sentence_words", 0.0) or 0.0),
            longest_sentence_words=int(payload.get("longest_sentence_words", 0) or 0),
            words_per_minute=float(payload.get("words_per_minute", 0.0) or 0.0),
            filler_count=int(payload.get("filler_count", 0) or 0),
            filler_rate=float(payload.get("filler_rate", 0.0) or 0.0),
            hedge_count=int(payload.get("hedge_count", 0) or 0),
            numeric_evidence=int(payload.get("numeric_evidence", 0) or 0),
            distinct_ratio=float(payload.get("distinct_ratio", 0.0) or 0.0),
            pace=str(payload.get("pace", PACE_UNKNOWN)),
            score=int(payload.get("score", 0) or 0),
            notes=tuple(str(item) for item in payload.get("notes", []) or ()),
        )


def analyze_delivery(
    transcript: str,
    duration_seconds: float = 0.0,
    language: str = ENGLISH,
) -> DeliveryMetrics:
    text = (transcript or "").strip()
    if not text:
        return DeliveryMetrics(language=language, duration_seconds=max(0.0, duration_seconds))

    tokens = _tokens(text)
    word_count = len(tokens)
    lowered = text.lower()

    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    has_punctuation = bool(_PUNCTUATION.search(text))
    sentence_lengths = [len(_tokens(sentence)) for sentence in sentences] or [word_count]
    sentence_count = len(sentence_lengths)
    longest = max(sentence_lengths)
    average = sum(sentence_lengths) / sentence_count

    filler_count = _count_fillers(tokens, lowered, language)
    hedge_count = _count_markers(lowered if language != KOREAN else text, phrasebook.hedge_markers(language))
    numeric_evidence = _count_numeric(text)
    distinct_ratio = len({token for token in tokens}) / word_count if word_count else 0.0

    duration = max(0.0, float(duration_seconds or 0.0))
    words_per_minute = 0.0
    pace = PACE_UNKNOWN
    if duration >= _MIN_SECONDS_FOR_PACE and word_count >= _MIN_WORDS_FOR_PACE:
        words_per_minute = word_count / (duration / 60.0)
        pace = _pace_for(words_per_minute, language)

    filler_rate = (filler_count / word_count * 100.0) if word_count else 0.0
    notes = _notes(pace, filler_rate, longest if has_punctuation else 0, hedge_count, word_count)
    score = _delivery_score(pace, filler_rate, longest if has_punctuation else 0, hedge_count, distinct_ratio)

    return DeliveryMetrics(
        language=language,
        duration_seconds=duration,
        word_count=word_count,
        char_count=len(text),
        sentence_count=sentence_count,
        avg_sentence_words=average,
        longest_sentence_words=longest,
        words_per_minute=words_per_minute,
        filler_count=filler_count,
        filler_rate=filler_rate,
        hedge_count=hedge_count,
        numeric_evidence=numeric_evidence,
        distinct_ratio=distinct_ratio,
        pace=pace,
        score=score,
        notes=notes,
    )


def aggregate(metrics: list[DeliveryMetrics]) -> DeliveryMetrics:
    """Roll per-answer metrics into one session-level summary."""
    measured = [item for item in metrics if item.measured]
    if not measured:
        return DeliveryMetrics()

    total_words = sum(item.word_count for item in measured)
    total_duration = sum(item.duration_seconds for item in measured)
    total_fillers = sum(item.filler_count for item in measured)
    paced = [item for item in measured if item.pace != PACE_UNKNOWN]
    words_per_minute = 0.0
    pace = PACE_UNKNOWN
    if paced:
        paced_words = sum(item.word_count for item in paced)
        paced_duration = sum(item.duration_seconds for item in paced)
        if paced_duration > 0:
            words_per_minute = paced_words / (paced_duration / 60.0)
            pace = _pace_for(words_per_minute, measured[0].language)

    filler_rate = (total_fillers / total_words * 100.0) if total_words else 0.0
    longest = max(item.longest_sentence_words for item in measured)
    hedges = sum(item.hedge_count for item in measured)
    distinct = sum(item.distinct_ratio for item in measured) / len(measured)

    return DeliveryMetrics(
        language=measured[0].language,
        duration_seconds=total_duration,
        word_count=total_words,
        char_count=sum(item.char_count for item in measured),
        sentence_count=sum(item.sentence_count for item in measured),
        avg_sentence_words=sum(item.avg_sentence_words for item in measured) / len(measured),
        longest_sentence_words=longest,
        words_per_minute=words_per_minute,
        filler_count=total_fillers,
        filler_rate=filler_rate,
        hedge_count=hedges,
        numeric_evidence=sum(item.numeric_evidence for item in measured),
        distinct_ratio=distinct,
        pace=pace,
        score=int(round(sum(item.score for item in measured) / len(measured))),
        notes=_notes(pace, filler_rate, longest, hedges, total_words),
    )


# -- internals ---------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    result: list[str] = []
    for raw in text.split():
        token = _TOKEN_STRIP.sub("", raw)
        if token:
            result.append(token)
    return result


def _count_fillers(tokens: list[str], lowered: str, language: str) -> int:
    fillers = phrasebook.filler_tokens(language)
    count = 0
    for token in tokens:
        candidate = token if language == KOREAN else token.lower()
        if candidate in fillers:
            count += 1
    for phrase in phrasebook.filler_phrases(language):
        count += lowered.count(phrase.lower())
    return count


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    return sum(text.count(marker) for marker in markers)


def _count_numeric(text: str) -> int:
    """Figures in the answer, counting a figure-with-unit twice.

    "from 3 incidents to 0" is stronger evidence than a bare "3 and 0", so a
    measurement outscores a loose number.
    """
    figures = len(_NUMBER.findall(text))
    measurements = len(_MEASUREMENT.findall(text))
    return figures + measurements


def _pace_for(words_per_minute: float, language: str) -> str:
    slow, fast = _PACE_BANDS.get(language, _PACE_BANDS[ENGLISH])
    if words_per_minute < slow:
        return PACE_SLOW
    if words_per_minute > fast:
        return PACE_FAST
    return PACE_STEADY


def _notes(
    pace: str,
    filler_rate: float,
    longest_sentence_words: int,
    hedge_count: int,
    word_count: int,
) -> tuple[str, ...]:
    notes: list[str] = []
    if pace in (PACE_SLOW, PACE_FAST):
        notes.append(pace)
    if filler_rate >= 4.0:
        notes.append("filler")
    if longest_sentence_words >= 45:
        notes.append("long_sentence")
    if word_count >= 40 and hedge_count >= 3:
        notes.append("hedge")
    return tuple(notes)


def _delivery_score(
    pace: str,
    filler_rate: float,
    longest_sentence_words: int,
    hedge_count: int,
    distinct_ratio: float,
) -> int:
    score = 92.0
    if pace == PACE_UNKNOWN:
        score = 75.0  # not measurable; do not reward or punish
    elif pace in (PACE_SLOW, PACE_FAST):
        score -= 14.0
    score -= min(24.0, filler_rate * 3.0)
    if longest_sentence_words >= 60:
        score -= 12.0
    elif longest_sentence_words >= 45:
        score -= 7.0
    score -= min(9.0, max(0, hedge_count - 1) * 3.0)
    if 0 < distinct_ratio < 0.45:
        score -= 6.0
    return int(round(clamp_score(score)))
