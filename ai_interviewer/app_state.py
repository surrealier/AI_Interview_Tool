from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    IDLE = "idle"
    PRELOADING = "preloading"
    READY = "ready"
    SPEAKING = "speaking"
    ANSWERING = "answering"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    FOLLOW_UP_GENERATING = "follow_up_generating"
    ERROR = "error"
