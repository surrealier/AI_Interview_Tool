from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


APP_NAME = "AIInterview"

DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
LARGE_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
TOKENIZER_MODEL_ID = "Qwen/Qwen3-TTS-Tokenizer-12Hz"
WINDOWS_SAPI_BACKEND = "Windows 기본 음성"
QWEN_BACKEND = "Qwen3-TTS"

SUPPORTED_MODEL_IDS = (DEFAULT_MODEL_ID, LARGE_MODEL_ID)
SUPPORTED_TTS_BACKENDS = (QWEN_BACKEND, WINDOWS_SAPI_BACKEND)


def application_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def documents_dir() -> Path:
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / "Documents"
    return Path.home() / "Documents"


def app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def default_config_path() -> Path:
    return app_data_dir() / "config.json"


def default_log_path() -> Path:
    return app_data_dir() / "logs" / "app.log"


def default_sessions_root() -> Path:
    return documents_dir() / APP_NAME / "sessions"


def default_video_path() -> Path:
    return application_base_dir() / "assets" / "interviewer.mp4"


def model_dir_name(model_id: str) -> str:
    return model_id.rsplit("/", 1)[-1]


@dataclass(slots=True)
class AppConfig:
    tts_backend: str = QWEN_BACKEND
    model_id: str = DEFAULT_MODEL_ID
    model_root: Path = field(default_factory=lambda: application_base_dir() / "models")
    sessions_root: Path = field(default_factory=default_sessions_root)
    video_path: Path = field(default_factory=default_video_path)
    default_language: str = "Auto"
    interview_language: str = "Korean"
    question_set_name: str = "기본 인성 면접"
    korean_speaker: str = "Sohee"
    english_speaker: str = "Ryan"
    default_instruct: str = (
        "Act as a calm, courteous, senior professional interviewer. "
        "Speak with a steady pace, neutral confidence, clear pronunciation, and a respectful interview-room tone. "
        "Do not sound playful, theatrical, overly excited, or like a casual assistant."
    )
    device_map: str = "cuda:0"
    torch_dtype: str = "bfloat16"
    use_flash_attention: bool = False
    max_new_tokens: int = 8192
    enable_windows_sapi_fallback: bool = False
    stt_model_size: str = "small"
    stt_device: str = "auto"
    stt_compute_type: str = "auto"
    input_device: str = "Default"
    followup_provider: str = "Auto"
    ollama_model: str = ""
    ollama_host: str = "http://127.0.0.1:11434"
    config_path: Path = field(default_factory=default_config_path, repr=False)

    def local_model_dir(self) -> Path:
        return self.model_root / model_dir_name(self.model_id)

    def local_tokenizer_dir(self) -> Path:
        return self.model_root / model_dir_name(TOKENIZER_MODEL_ID)

    def model_source(self) -> str:
        local_dir = self.local_model_dir()
        if local_dir.exists():
            return str(local_dir)
        return self.model_id

    def ensure_directories(self) -> None:
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def supports_style_instruction(self) -> bool:
        return "1.7B" in self.model_id

    def preferred_model_id(self) -> str:
        large_model_dir = self.model_root / model_dir_name(LARGE_MODEL_ID)
        if large_model_dir.exists():
            return LARGE_MODEL_ID
        return self.model_id

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        config_path = Path(path) if path is not None else default_config_path()
        config = cls(config_path=config_path)
        if not config_path.exists():
            return config

        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return config

        for key, value in payload.items():
            if not hasattr(config, key) or key == "config_path":
                continue
            if key in {"model_root", "sessions_root", "video_path"}:
                setattr(config, key, Path(str(value)).expanduser())
            else:
                setattr(config, key, value)
        return config

    def save(self, path: Path | None = None) -> None:
        target = Path(path) if path is not None else self.config_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_suffix(f"{target.suffix}.tmp")
        temp_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, target)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name in self.__dataclass_fields__:
            if field_name == "config_path":
                continue
            value = getattr(self, field_name)
            result[field_name] = str(value) if isinstance(value, Path) else value
        return result
