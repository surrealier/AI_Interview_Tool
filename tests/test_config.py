from pathlib import Path

import pytest

from ai_interviewer.config import (
    AppConfig,
    MODEL_INSTALL_MARKER,
    ModelNotInstalledError,
    is_model_installed,
    model_dir_name,
)


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
    config.setup_completed = True
    config.interview_type = "technical"
    config.selected_speaker = "Aiden"
    config.sound_test_required = False
    config.enable_stt = False
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
    assert loaded.setup_completed is True
    assert loaded.interview_type == "technical"
    assert loaded.selected_speaker == "Aiden"
    assert loaded.sound_test_required is False
    assert loaded.enable_stt is False


def test_load_migrates_legacy_device_defaults(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config = AppConfig(config_path=config_path)
    config.device_map = "cuda:0"
    config.torch_dtype = "bfloat16"
    config.save()

    loaded = AppConfig.load(config_path)

    assert loaded.device_map == "auto"
    assert loaded.torch_dtype == "auto"


def test_load_keeps_explicit_device_choices(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config = AppConfig(config_path=config_path)
    config.device_map = "cuda:1"
    config.torch_dtype = "float16"
    config.save()

    loaded = AppConfig.load(config_path)

    assert loaded.device_map == "cuda:1"
    assert loaded.torch_dtype == "float16"


def _make_model_dir(model_root: Path, model_id: str) -> Path:
    model_dir = model_root / model_dir_name(model_id)
    model_dir.mkdir(parents=True)
    return model_dir


def test_is_model_installed_with_marker(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    model_dir = _make_model_dir(tmp_path / "models", config.model_id)
    (model_dir / MODEL_INSTALL_MARKER).write_text("{}", encoding="utf-8")

    assert is_model_installed(tmp_path / "models", config.model_id)


def test_is_model_installed_with_legacy_layout(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    model_dir = _make_model_dir(tmp_path / "models", config.model_id)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"fake")

    assert is_model_installed(tmp_path / "models", config.model_id)


def test_is_model_installed_rejects_partial_download(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    model_dir = _make_model_dir(tmp_path / "models", config.model_id)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    assert not is_model_installed(tmp_path / "models", config.model_id)


def test_model_source_raises_when_not_installed(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AI_INTERVIEW_ALLOW_HUB", raising=False)
    config = AppConfig(config_path=tmp_path / "config.json")
    config.model_root = tmp_path / "models"

    with pytest.raises(ModelNotInstalledError):
        config.model_source()


def test_model_source_allows_hub_with_env_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_INTERVIEW_ALLOW_HUB", "1")
    config = AppConfig(config_path=tmp_path / "config.json")
    config.model_root = tmp_path / "models"

    assert config.model_source() == config.model_id


def test_model_source_returns_local_dir_when_installed(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "config.json")
    config.model_root = tmp_path / "models"
    model_dir = _make_model_dir(config.model_root, config.model_id)
    (model_dir / MODEL_INSTALL_MARKER).write_text("{}", encoding="utf-8")

    assert config.model_source() == str(model_dir)
