from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


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


def default_sessions_root() -> Path:
    return documents_dir() / APP_NAME / "sessions"


def model_dir_name(model_id: str) -> str:
    return model_id.rsplit("/", 1)[-1]


@dataclass(slots=True)
class AppConfig:
    tts_backend: str = QWEN_BACKEND
    model_id: str = DEFAULT_MODEL_ID
    model_root: Path = field(default_factory=lambda: application_base_dir() / "models")
    sessions_root: Path = field(default_factory=default_sessions_root)
    default_language: str = "Auto"
    korean_speaker: str = "Sohee"
    english_speaker: str = "Ryan"
    default_instruct: str = (
        "Use a calm, courteous, professional interviewer voice. "
        "Keep a steady, slightly slower pace with neutral emotion and clear pronunciation."
    )
    device_map: str = "cuda:0"
    torch_dtype: str = "bfloat16"
    use_flash_attention: bool = False
    max_new_tokens: int = 8192
    enable_windows_sapi_fallback: bool = True

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

    def supports_style_instruction(self) -> bool:
        return "1.7B" in self.model_id
