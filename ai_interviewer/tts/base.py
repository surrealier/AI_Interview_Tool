from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SpeechResult:
    wav_path: Path
    language: str
    speaker: str
    backend: str = "qwen3-tts"
    warning: str = ""
