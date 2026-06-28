from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_interviewer.config import AppConfig


class STTError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    text: str
    audio_path: Path
    model_size: str


@dataclass(frozen=True, slots=True)
class AudioInputDevice:
    index: int
    name: str
    default_samplerate: int

    @property
    def label(self) -> str:
        return f"{self.index}: {self.name}"


def list_input_devices() -> list[AudioInputDevice]:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise STTError("Missing microphone dependency. Run: python -m pip install -r requirements-interactive.txt") from exc

    devices: list[AudioInputDevice] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        devices.append(
            AudioInputDevice(
                index=index,
                name=str(device.get("name", f"Device {index}")),
                default_samplerate=int(device.get("default_samplerate", 16000)),
            )
        )
    return devices


def input_device_id_from_label(label: str) -> int | None:
    value = label.strip()
    if not value or value == "Default":
        return None
    prefix = value.split(":", 1)[0].strip()
    if not prefix.isdigit():
        return None
    return int(prefix)


class MicrophoneRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream: Any | None = None
        self._frames: list[Any] = []
        self._output_path: Path | None = None
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self, output_path: Path, input_device: int | None = None) -> None:
        if self._stream is not None:
            raise STTError("Recording is already in progress.")

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise STTError("Missing STT recorder dependency. Run: python -m pip install -r requirements-interactive.txt") from exc

        self._frames = []
        self._output_path = Path(output_path)
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        def callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            if status:
                return
            with self._lock:
                self._frames.append(indata.copy())

        try:
            self._stream = self._open_stream(sd, callback, self.sample_rate, input_device)
            self._stream.start()
        except Exception as first_exc:
            try:
                default_device = sd.query_devices(device=input_device, kind="input") if input_device is not None else sd.query_devices(kind="input")
                fallback_rate = int(default_device["default_samplerate"])
                self.sample_rate = fallback_rate
                self._stream = self._open_stream(sd, callback, fallback_rate, input_device)
                self._stream.start()
            except Exception as second_exc:
                self._stream = None
                raise STTError(f"Could not open microphone input: {second_exc}") from first_exc

    def stop(self) -> Path:
        if self._stream is None or self._output_path is None:
            raise STTError("Recording has not started.")

        stream = self._stream
        output_path = self._output_path
        self._stream = None
        self._output_path = None

        stream.stop()
        stream.close()

        with self._lock:
            frames = list(self._frames)
            self._frames = []

        if not frames:
            raise STTError("No microphone audio was captured.")

        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise STTError("Missing STT audio dependency. Run: python -m pip install -r requirements-interactive.txt") from exc

        audio = np.concatenate(frames, axis=0)
        sf.write(str(output_path), audio, self.sample_rate, subtype="PCM_16")
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise STTError(f"Recorded audio file is empty: {output_path}")
        return output_path

    def _open_stream(self, sounddevice: Any, callback: Any, sample_rate: int, input_device: int | None) -> Any:
        return sounddevice.InputStream(
            samplerate=sample_rate,
            channels=self.channels,
            dtype="float32",
            device=input_device,
            callback=callback,
        )


class WhisperTranscriber:
    _cache_lock = threading.Lock()
    _model_cache: dict[tuple[str, str, str], Any] = {}

    def __init__(self, config: AppConfig):
        self.config = config

    def transcribe(self, audio_path: Path, language: str) -> TranscriptResult:
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise STTError(f"Audio file does not exist or is empty: {audio_path}")

        model = self._load_model()
        lang_code = "ko" if language == "Korean" else "en" if language == "English" else None
        try:
            segments, _info = model.transcribe(
                str(audio_path),
                language=lang_code,
                vad_filter=True,
                beam_size=5,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        except Exception as exc:  # pragma: no cover - depends on external STT runtime
            raise STTError(f"STT transcription failed: {exc}") from exc

        return TranscriptResult(text=text, audio_path=audio_path, model_size=self.config.stt_model_size)

    def _load_model(self) -> Any:
        device, compute_type = self._resolve_runtime()
        key = (self.config.stt_model_size, device, compute_type)
        with self._cache_lock:
            cached = self._model_cache.get(key)
            if cached is not None:
                return cached

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise STTError("Missing STT runtime. Run: python -m pip install -r requirements-interactive.txt") from exc

        try:
            model = WhisperModel(
                self.config.stt_model_size,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:  # pragma: no cover - depends on external STT runtime
            raise STTError(f"Could not load faster-whisper model: {exc}") from exc

        with self._cache_lock:
            self._model_cache[key] = model
        return model

    def _resolve_runtime(self) -> tuple[str, str]:
        device = self.config.stt_device
        compute_type = self.config.stt_compute_type
        if device == "auto":
            device = "cpu"
            try:
                import torch

                if torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                device = "cpu"
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        return device, compute_type
