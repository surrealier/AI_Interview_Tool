from __future__ import annotations

import numpy as np
import pytest

from ai_interviewer.config import AppConfig, DEFAULT_MODEL_ID, LARGE_MODEL_ID
from ai_interviewer.tts.qwen_provider import (
    _EDGE_PAD_MS,
    _MAX_INTERNAL_GAP_MS,
    QwenTTSProvider,
)


RATE = 24000


def tone(seconds: float, freq: float = 200.0, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype("float32")


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(RATE * seconds), dtype="float32")


def edges(audio: np.ndarray) -> tuple[float, float]:
    """Leading and trailing silence, in seconds."""
    frame = RATE // 100
    usable = audio.size // frame * frame
    energy = np.sqrt((audio[:usable].reshape(-1, frame) ** 2).mean(axis=1))
    voiced = np.flatnonzero(energy >= max(energy.max() * 0.06, 1e-4))
    if voiced.size == 0:
        return 0.0, 0.0
    return voiced[0] / 100, (energy.size - 1 - voiced[-1]) / 100


def longest_internal_gap(audio: np.ndarray) -> float:
    frame = RATE // 100
    usable = audio.size // frame * frame
    energy = np.sqrt((audio[:usable].reshape(-1, frame) ** 2).mean(axis=1))
    quiet = energy < max(energy.max() * 0.06, 1e-4)
    voiced = np.flatnonzero(~quiet)
    if voiced.size == 0:
        return 0.0
    inner = quiet[voiced[0] : voiced[-1] + 1]
    runs, run = [], 0
    for is_quiet in inner:
        if is_quiet:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)
    return (max(runs) / 100) if runs else 0.0


# -- the actual defect -------------------------------------------------------


def test_long_leading_and_trailing_silence_is_cut() -> None:
    """Qwen3-TTS pads each utterance with 0.5-1.0s of silence. Played one
    question at a time, that padding is most of what sits between questions."""
    padded = np.concatenate([silence(1.0), tone(2.0), silence(1.2)])
    tightened = QwenTTSProvider.tighten_speech(padded, RATE)

    lead, trail = edges(tightened)
    assert lead <= _EDGE_PAD_MS / 1000 + 0.02
    assert trail <= _EDGE_PAD_MS / 1000 + 0.02
    assert tightened.size < padded.size


def test_a_breath_is_left_at_the_edges() -> None:
    """Cutting to exactly zero clips the onset and sounds abrupt."""
    padded = np.concatenate([silence(0.8), tone(1.5), silence(0.8)])
    lead, trail = edges(QwenTTSProvider.tighten_speech(padded, RATE))
    assert lead > 0
    assert trail > 0


def test_an_over_long_internal_gap_is_shortened_not_removed() -> None:
    """A clause pause is real speech; a half-second stop mid-question is not."""
    audio = np.concatenate([tone(1.0), silence(0.5), tone(1.0)])
    tightened = QwenTTSProvider.tighten_speech(audio, RATE)

    gap = longest_internal_gap(tightened)
    assert gap > 0, "the pause was deleted entirely"
    assert gap <= _MAX_INTERNAL_GAP_MS / 1000 + 0.03


def test_a_natural_short_pause_is_left_alone() -> None:
    audio = np.concatenate([tone(1.0), silence(0.15), tone(1.0)])
    tightened = QwenTTSProvider.tighten_speech(audio, RATE)
    assert longest_internal_gap(tightened) == pytest.approx(0.15, abs=0.04)


def test_speech_content_is_preserved() -> None:
    """Total voiced duration must survive: trimming silence, not speech."""
    speech = tone(2.0)
    padded = np.concatenate([silence(1.0), speech, silence(1.0)])
    tightened = QwenTTSProvider.tighten_speech(padded, RATE)

    voiced_before = float((np.abs(padded) > 0.05).sum())
    voiced_after = float((np.abs(tightened) > 0.05).sum())
    assert voiced_after >= voiced_before * 0.99


# -- safety ------------------------------------------------------------------


def test_empty_audio_is_returned_unchanged() -> None:
    assert QwenTTSProvider.tighten_speech(np.zeros(0, dtype="float32"), RATE).size == 0


def test_all_silent_audio_is_not_emptied() -> None:
    """A silent clip is a synthesis failure to surface, not something to delete."""
    quiet = silence(1.0)
    assert QwenTTSProvider.tighten_speech(quiet, RATE).size == quiet.size


def test_very_short_audio_survives() -> None:
    tiny = tone(0.01)
    assert QwenTTSProvider.tighten_speech(tiny, RATE).size > 0


def test_speech_with_no_padding_is_barely_touched() -> None:
    speech = tone(2.0)
    tightened = QwenTTSProvider.tighten_speech(speech, RATE)
    assert tightened.size == pytest.approx(speech.size, rel=0.05)


# -- the tone instruction ----------------------------------------------------


def test_the_tone_instruction_is_sent_on_every_model_size(tmp_path) -> None:
    """It used to be withheld from 0.6B on the belief that the small model
    ignored it; the model's output demonstrably changes with it applied, and it
    is the only prosody control Qwen3-TTS exposes."""
    for model_id in (DEFAULT_MODEL_ID, LARGE_MODEL_ID):
        config = AppConfig(config_path=tmp_path / "c.json", model_id=model_id)
        provider = QwenTTSProvider(config, tmp_path)
        assert provider._style_instruction() == config.default_instruct


def test_an_empty_instruction_is_sent_as_none(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "c.json", default_instruct="")
    assert QwenTTSProvider(config, tmp_path)._style_instruction() is None


def test_the_instruction_asks_for_connected_delivery(tmp_path) -> None:
    """The failure mode this wording exists to prevent is word-by-word
    recitation, so that has to be what it actually says."""
    instruct = AppConfig(config_path=tmp_path / "c.json").default_instruct.lower()
    assert "word by word" in instruct
    assert any(word in instruct for word in ("connected", "flowing"))


def test_changing_the_tightening_retires_old_cached_audio(tmp_path, monkeypatch) -> None:
    """Post-processing changes the stored waveform, so clips made under the old
    settings must not keep being served."""
    from ai_interviewer.tts import qwen_provider

    config = AppConfig(config_path=tmp_path / "c.json")
    provider = QwenTTSProvider(config, tmp_path)
    before = provider._cache_path("k", "Question?", "Korean", "Sohee")

    monkeypatch.setattr(qwen_provider, "_MAX_INTERNAL_GAP_MS", 400)
    after = provider._cache_path("k", "Question?", "Korean", "Sohee")

    assert before != after
