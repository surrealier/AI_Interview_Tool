from pathlib import Path

from ai_interviewer.config import AppConfig


def test_config_save_and_load_round_trip(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config = AppConfig(config_path=config_path)
    config.model_root = tmp_path / "models"
    config.sessions_root = tmp_path / "sessions"
    config.video_path = tmp_path / "assets" / "interviewer.mp4"
    config.enable_windows_sapi_fallback = True
    config.stt_device = "cpu"
    config.stt_compute_type = "int8"
    config.input_device = "3: USB Mic"
    config.followup_provider = "Ollama"
    config.ollama_model = "qwen2.5:7b"
    config.save()

    loaded = AppConfig.load(config_path)

    assert loaded.model_root == Path(tmp_path / "models")
    assert loaded.sessions_root == Path(tmp_path / "sessions")
    assert loaded.enable_windows_sapi_fallback is True
    assert loaded.stt_device == "cpu"
    assert loaded.stt_compute_type == "int8"
    assert loaded.input_device == "3: USB Mic"
    assert loaded.followup_provider == "Ollama"
    assert loaded.ollama_model == "qwen2.5:7b"
