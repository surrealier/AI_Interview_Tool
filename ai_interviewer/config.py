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
WINDOWS_SAPI_BACKEND = "windows-sapi"
QWEN_BACKEND = "Qwen3-TTS"
# config.json values written before the backend became a stable id.
LEGACY_TTS_BACKEND_VALUES = {"Windows 기본 음성": WINDOWS_SAPI_BACKEND}

SUPPORTED_MODEL_IDS = (DEFAULT_MODEL_ID, LARGE_MODEL_ID)
SUPPORTED_TTS_BACKENDS = (QWEN_BACKEND, WINDOWS_SAPI_BACKEND)

# Analysis providers. Mirrors intelligence.llm.registry.AI_PROVIDERS, kept
# literal here so importing the config never pulls the analysis stack in;
# tests/test_intelligence_config.py fails if the two ever drift apart.
AI_PROVIDER_OFFLINE = "Offline"
AI_PROVIDER_AUTO = "Auto"
AI_PROVIDER_OLLAMA = "Ollama"
AI_PROVIDER_CLAUDE = "Claude"
SUPPORTED_AI_PROVIDERS = (
    AI_PROVIDER_OFFLINE,
    AI_PROVIDER_AUTO,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_CLAUDE,
)
CLOUD_AI_PROVIDERS = (AI_PROVIDER_CLAUDE,)

DEFAULT_CLAUDE_MODEL = "claude-opus-5"
SUPPORTED_AI_EFFORTS = ("low", "medium", "high")
SUPPORTED_SENIORITY_LEVELS = ("junior", "mid", "senior", "lead")
MAX_PROBE_DEPTH = 4


def application_base_dir() -> Path:
    """Folder next to the EXE (frozen) or the project root: external files
    like models/, docs, and the user-provided interviewer video live here."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_base_dir() -> Path:
    """Folder holding bundled resources (PyInstaller 6 onedir: _internal)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
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


MODEL_INSTALL_MARKER = ".download_complete"


class ModelNotInstalledError(RuntimeError):
    def __init__(self, model_id: str, local_dir: Path):
        super().__init__(
            f"Model is not installed locally: {model_id} (expected at {local_dir})"
        )
        self.model_id = model_id
        self.local_dir = local_dir


def normalize_ai_provider(value: Any) -> str:
    candidate = str(value or "").strip()
    for name in SUPPORTED_AI_PROVIDERS:
        if candidate.lower() == name.lower():
            return name
    return AI_PROVIDER_OFFLINE


def is_model_installed(model_root: Path, model_id: str) -> bool:
    model_dir = Path(model_root) / model_dir_name(model_id)
    if (model_dir / MODEL_INSTALL_MARKER).exists():
        return True
    # Manual installs predate the marker file.
    if (model_dir / "config.json").exists() and any(model_dir.glob("*.safetensors")):
        return True
    return False


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
    device_map: str = "auto"
    torch_dtype: str = "auto"
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
    # -- interview intelligence -------------------------------------------
    # Offline by default: scoring, probing, and reports all work with no
    # network and no model. A cloud provider is opt-in per install.
    ai_provider: str = AI_PROVIDER_OFFLINE
    claude_model: str = DEFAULT_CLAUDE_MODEL
    ai_effort: str = "medium"
    enable_cloud_ai: bool = False
    enable_live_scoring: bool = True
    enable_adaptive_probing: bool = True
    auto_speak_probe: bool = False
    max_probe_depth: int = 2
    target_role: str = ""
    target_seniority: str = "mid"
    job_description: str = ""
    resume_summary: str = ""
    use_generated_blueprint: bool = False
    # "system" | "light" | "dark". Replaces the legacy `ui_theme` key, whose
    # only ever-written value ("light") described a dark palette; old configs
    # simply fall back to the default here.
    ui_theme_mode: str = "system"
    ui_language: str = ""
    setup_completed: bool = False
    interview_type: str = "hr"
    selected_speaker: str = "Sohee"
    sound_test_required: bool = True
    enable_stt: bool = True
    config_path: Path = field(default_factory=default_config_path, repr=False)

    def local_model_dir(self) -> Path:
        return self.model_root / model_dir_name(self.model_id)

    def local_tokenizer_dir(self) -> Path:
        return self.model_root / model_dir_name(TOKENIZER_MODEL_ID)

    def model_source(self) -> str:
        local_dir = self.local_model_dir()
        if is_model_installed(self.model_root, self.model_id):
            return str(local_dir)
        if os.environ.get("AI_INTERVIEW_ALLOW_HUB") == "1":
            return self.model_id
        raise ModelNotInstalledError(self.model_id, local_dir)

    def ensure_directories(self) -> None:
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def supports_style_instruction(self) -> bool:
        return "1.7B" in self.model_id

    def preferred_model_id(self) -> str:
        if is_model_installed(self.model_root, LARGE_MODEL_ID):
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

        # Configs saved before device auto-detection pinned the old defaults;
        # "auto" resolves back to cuda:0/bfloat16 on CUDA machines.
        if config.device_map == "cuda:0":
            config.device_map = "auto"
        if config.torch_dtype == "bfloat16":
            config.torch_dtype = "auto"
        config.tts_backend = LEGACY_TTS_BACKEND_VALUES.get(config.tts_backend, config.tts_backend)
        if config.ui_theme_mode not in {"system", "light", "dark"}:
            config.ui_theme_mode = "system"
        config.normalize_ai_settings(payload)
        return config

    def normalize_ai_settings(self, payload: dict[str, Any] | None = None) -> None:
        """Clamp the analysis settings and carry the pre-1.1 config forward."""
        source = payload or {}
        if "ai_provider" not in source and source.get("followup_provider") == AI_PROVIDER_OLLAMA:
            # Before the analysis layer existed, this was the only local-model
            # switch a user could have flipped; honour it.
            self.ai_provider = AI_PROVIDER_OLLAMA
        self.ai_provider = normalize_ai_provider(self.ai_provider)
        if self.ai_provider in CLOUD_AI_PROVIDERS and not self.enable_cloud_ai:
            # A cloud provider without consent falls back rather than failing
            # every call; the setup step is what turns it on.
            self.ai_provider = AI_PROVIDER_OFFLINE
        if not str(self.claude_model or "").strip():
            self.claude_model = DEFAULT_CLAUDE_MODEL
        if self.ai_effort not in SUPPORTED_AI_EFFORTS:
            self.ai_effort = "medium"
        if self.target_seniority not in SUPPORTED_SENIORITY_LEVELS:
            self.target_seniority = "mid"
        try:
            depth = int(self.max_probe_depth)
        except (TypeError, ValueError):
            depth = 2
        self.max_probe_depth = max(0, min(depth, MAX_PROBE_DEPTH))

    def analysis_is_local_only(self) -> bool:
        """True when nothing in the analysis path can send data off the machine."""
        return not (self.enable_cloud_ai and self.ai_provider in {AI_PROVIDER_AUTO, AI_PROVIDER_CLAUDE})

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
