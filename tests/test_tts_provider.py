from types import SimpleNamespace

from ai_interviewer.config import AppConfig
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
