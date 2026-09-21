from types import SimpleNamespace

from ai_interviewer.config import AppConfig
from ai_interviewer.tts.base import SpeechResult
from ai_interviewer.tts import qwen_provider
from ai_interviewer.tts.qwen_provider import QwenTTSProvider


def test_windows_sapi_sidecar_text_is_deleted(tmp_path, monkeypatch) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    provider = QwenTTSProvider(config, tmp_path)
    wav_path = tmp_path / "fallback.wav"

    def fake_run(args, env, capture_output, text, timeout, check):
        output_path = env["AI_INTERVIEW_TTS_OUT_PATH"]
        with open(output_path, "wb") as file:
            file.write(b"RIFFfake")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(qwen_provider.sys, "platform", "win32")
    monkeypatch.setattr(qwen_provider.subprocess, "run", fake_run)

    result = provider._synthesize_with_windows_sapi(wav_path, "private question text", "Korean")

    assert result == wav_path
    assert wav_path.exists()
    assert not wav_path.with_suffix(".txt").exists()


def test_resolve_voice_prefers_selected_speaker(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    config.selected_speaker = "Aiden"
    provider = QwenTTSProvider(config, tmp_path)

    assert provider.resolve_voice("Please introduce yourself.") == ("English", "Aiden")
    assert provider.resolve_voice("자기소개를 해주세요.") == ("Korean", "Aiden")


def test_sound_test_uses_selected_language_and_speaker(tmp_path, monkeypatch) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    provider = QwenTTSProvider(config, tmp_path)
    calls = {}

    def fake_speak(text, cache_key, language=None, speaker=None):
        calls["text"] = text
        calls["cache_key"] = cache_key
        calls["language"] = language
        calls["speaker"] = speaker
        return SpeechResult(wav_path=tmp_path / "fake.wav", language=language, speaker=speaker)

    monkeypatch.setattr(provider, "speak", fake_speak)

    result = provider.sound_test("Korean", "Sohee")

    assert result.language == "Korean"
    assert result.speaker == "Sohee"
    assert calls["cache_key"] == "sound-test-Korean-Sohee"
    assert "안녕하세요" in calls["text"]


# -- voice cache -------------------------------------------------------------


def _provider(tmp_path, **overrides) -> QwenTTSProvider:
    config = AppConfig(config_path=tmp_path / "config.json", **overrides)
    return QwenTTSProvider(config, tmp_path / "voice_cache")


def test_same_question_and_voice_reuse_one_file_across_sessions(tmp_path) -> None:
    """The cache is content-addressed on purpose: synthesis costs 13-27s, and
    the session that asked has no bearing on how the sentence sounds."""
    provider = _provider(tmp_path)
    setup = provider._cache_path("setup-first-question", "Tell me about yourself.", "English", "Ryan")
    first_run = provider._cache_path("20260921-aaaa-1", "Tell me about yourself.", "English", "Ryan")
    later_run = provider._cache_path("20260922-bbbb-7", "Tell me about yourself.", "English", "Ryan")

    assert setup == first_run == later_run


def test_cache_splits_on_anything_that_changes_the_audio(tmp_path) -> None:
    provider = _provider(tmp_path)
    base = provider._cache_path("k", "Tell me about yourself.", "English", "Ryan")

    assert provider._cache_path("k", "A different question?", "English", "Ryan") != base
    assert provider._cache_path("k", "Tell me about yourself.", "Korean", "Ryan") != base
    assert provider._cache_path("k", "Tell me about yourself.", "English", "Aiden") != base

    other_model = _provider(tmp_path, model_id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
    assert other_model._cache_path("k", "Tell me about yourself.", "English", "Ryan").name != base.name


def test_sapi_and_qwen_audio_never_collide(tmp_path) -> None:
    provider = _provider(tmp_path)
    assert provider._cache_path("k", "Question?", "Korean", "Sohee") != provider._fallback_cache_path(
        "k", "Question?", "Korean", "Sohee"
    )


def test_prefetch_restores_the_reported_backend(tmp_path, monkeypatch) -> None:
    """A background prefetch must not relabel the question on screen."""
    provider = _provider(tmp_path)
    provider._last_backend = "qwen3-tts"
    provider._last_warning = "an earlier warning"
    monkeypatch.setattr(provider, "synthesize", lambda **kwargs: tmp_path / "x.wav")

    assert provider.prefetch(text="Next question?", cache_key="k", language="English", speaker="Ryan")
    assert provider._last_backend == "qwen3-tts"
    assert provider._last_warning == "an earlier warning"


def test_prefetch_failure_is_swallowed_and_state_still_restored(tmp_path, monkeypatch) -> None:
    provider = _provider(tmp_path)
    provider._last_backend = "cache"
    provider._last_warning = ""

    def boom(**kwargs):
        raise RuntimeError("synthesis exploded")

    monkeypatch.setattr(provider, "synthesize", boom)

    assert provider.prefetch(text="Next?", cache_key="k", language="English", speaker="Ryan") is False
    assert provider._last_backend == "cache"


def test_prefetch_ignores_blank_text(tmp_path) -> None:
    assert _provider(tmp_path).prefetch(text="   ", cache_key="k", language="English", speaker="Ryan") is False
