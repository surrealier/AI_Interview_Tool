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
