from __future__ import annotations

import pytest

from ai_interviewer.intelligence.delivery import (
    PACE_FAST,
    PACE_SLOW,
    PACE_STEADY,
    PACE_UNKNOWN,
    DeliveryMetrics,
    aggregate,
    analyze_delivery,
)


def test_empty_transcript_is_not_measured() -> None:
    metrics = analyze_delivery("", 30, "English")
    assert metrics.measured is False
    assert metrics.pace == PACE_UNKNOWN
    assert metrics.words_per_minute == 0


def test_pace_bands_follow_the_language() -> None:
    words = " ".join(["word"] * 150)
    english = analyze_delivery(words, 60, "English")
    korean = analyze_delivery(" ".join(["단어"] * 150), 60, "Korean")
    # 150 per minute is comfortable English but fast for Korean word chunks.
    assert english.pace == PACE_STEADY
    assert korean.pace == PACE_FAST


def test_slow_and_fast_are_both_detected() -> None:
    slow = analyze_delivery(" ".join(["word"] * 40), 60, "English")
    fast = analyze_delivery(" ".join(["word"] * 300), 60, "English")
    assert slow.pace == PACE_SLOW
    assert fast.pace == PACE_FAST
    assert slow.score < 92 and fast.score < 92


def test_pace_is_not_guessed_from_a_tiny_sample() -> None:
    """Two words in three seconds is noise, not a 40-wpm reading."""
    metrics = analyze_delivery("Yes exactly", 3, "English")
    assert metrics.pace == PACE_UNKNOWN
    assert metrics.words_per_minute == 0


def test_korean_fillers_match_whole_tokens_only() -> None:
    # "그래서" and "그러므로" contain "그", which must not count as a filler.
    clean = analyze_delivery("그래서 그러므로 결론을 정리했습니다.", 30, "Korean")
    filled = analyze_delivery("음 어 그 저기 결론을 정리했습니다.", 30, "Korean")
    assert clean.filler_count == 0
    assert filled.filler_count >= 4


def test_english_filler_phrases_are_counted() -> None:
    metrics = analyze_delivery("So, um, you know, I sort of handled it, like, basically.", 20, "English")
    assert metrics.filler_count >= 5
    assert metrics.filler_rate > 0
    assert "filler" in metrics.notes


def test_measurements_need_a_figure() -> None:
    no_numbers = analyze_delivery("먼저 원인을 분류하고 초기 단계에서 명확히 했습니다.", 30, "Korean")
    with_numbers = analyze_delivery("장애율을 20% 낮추고 롤백을 3건에서 0건으로 줄였습니다.", 30, "Korean")
    assert no_numbers.numeric_evidence == 0
    assert with_numbers.numeric_evidence >= 4


def test_unpunctuated_transcript_is_not_penalised_for_long_sentences() -> None:
    """STT often returns no punctuation; that is not the speaker's fault."""
    words = " ".join(["word"] * 80)
    metrics = analyze_delivery(words, 40, "English")
    assert "long_sentence" not in metrics.notes


def test_long_sentences_are_flagged_when_punctuation_exists() -> None:
    long_sentence = " ".join(["word"] * 70) + "."
    metrics = analyze_delivery(long_sentence, 40, "English")
    assert "long_sentence" in metrics.notes


def test_aggregate_ignores_unmeasured_answers() -> None:
    measured = analyze_delivery(" ".join(["word"] * 100), 45, "English")
    blank = analyze_delivery("", 0, "English")
    rolled = aggregate([measured, blank, measured])
    assert rolled.word_count == measured.word_count * 2
    assert rolled.duration_seconds == pytest.approx(measured.duration_seconds * 2)
    assert rolled.pace == measured.pace


def test_aggregate_of_nothing_is_empty() -> None:
    assert aggregate([]).measured is False
    assert aggregate([analyze_delivery("", 0, "English")]).measured is False


def test_metrics_round_trip_through_json() -> None:
    original = analyze_delivery("I cut latency by 30% in 2 weeks.", 25, "English")
    restored = DeliveryMetrics.from_dict(original.to_dict())
    assert restored.pace == original.pace
    assert restored.score == original.score
    assert restored.numeric_evidence == original.numeric_evidence
    assert restored.notes == original.notes
