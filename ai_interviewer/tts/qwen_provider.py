from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ai_interviewer.config import AppConfig, QWEN_BACKEND, WINDOWS_SAPI_BACKEND
from ai_interviewer.question_parser import detect_language
from ai_interviewer.tts.base import SpeechResult


class TTSProviderError(RuntimeError):
    pass


class QwenTTSProvider:
    def __init__(self, config: AppConfig, cache_dir: Path):
        self.config = config
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model: Any | None = None
        self._last_backend = "qwen3-tts"
        self._last_warning = ""

    def resolve_voice(self, text: str) -> tuple[str, str]:
        language = self.config.default_language
        if language == "Auto":
            language = detect_language(text)

        if language == "Korean":
            speaker = self.config.korean_speaker
        else:
            language = "English"
            speaker = self.config.english_speaker
        return language, speaker

    def speak(
        self,
        text: str,
        cache_key: str,
        language: str | None = None,
        speaker: str | None = None,
    ) -> SpeechResult:
        language, speaker = (language, speaker) if language and speaker else self.resolve_voice(text)
        wav_path = self.synthesize(text=text, cache_key=cache_key, language=language, speaker=speaker)
        self.play_wav(wav_path)
        return SpeechResult(
            wav_path=wav_path,
            language=language,
            speaker=speaker,
            backend=self._last_backend,
            warning=self._last_warning,
        )

    def synthesize(self, text: str, cache_key: str, language: str, speaker: str) -> Path:
        if self.config.tts_backend == WINDOWS_SAPI_BACKEND:
            fallback_path = self._fallback_cache_path(cache_key, text, language, speaker)
            self._last_backend = "windows-sapi"
            self._last_warning = ""
            return self._synthesize_with_windows_sapi(fallback_path, text, language)

        wav_path = self._cache_path(cache_key, text, language, speaker)
        if wav_path.exists() and wav_path.stat().st_size > 0:
            self._last_backend = "cache"
            self._last_warning = ""
            return wav_path

        if self.config.tts_backend != QWEN_BACKEND:
            raise TTSProviderError(f"Unsupported TTS backend: {self.config.tts_backend}")

        self._last_backend = "qwen3-tts"
        self._last_warning = ""
        try:
            return self._synthesize_with_qwen(wav_path, text, language, speaker)
        except Exception as exc:
            if not self.config.enable_windows_sapi_fallback:
                if isinstance(exc, TTSProviderError):
                    raise
                raise TTSProviderError(str(exc)) from exc

            fallback_path = self._fallback_cache_path(cache_key, text, language, speaker)
            self._last_backend = "windows-sapi"
            self._last_warning = f"Qwen3-TTS failed, so Windows TTS fallback was used: {exc}"
            return self._synthesize_with_windows_sapi(fallback_path, text, language)

    def _synthesize_with_qwen(self, wav_path: Path, text: str, language: str, speaker: str) -> Path:
        model = self._load_model()
        try:
            wavs, sample_rate = model.generate_custom_voice(
                text=text,
                language=language,
                speaker=speaker,
                instruct=self.config.default_instruct,
                max_new_tokens=self.config.max_new_tokens,
            )
        except Exception as exc:  # pragma: no cover - depends on external model runtime
            raise TTSProviderError(f"Qwen3-TTS generation failed: {exc}") from exc

        try:
            import soundfile as sf
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise TTSProviderError("Missing dependency: install soundfile to save generated audio.") from exc

        sf.write(str(wav_path), wavs[0], sample_rate, subtype="PCM_16")
        if not wav_path.exists() or wav_path.stat().st_size == 0:
            raise TTSProviderError(f"Generated audio file is empty: {wav_path}")
        return wav_path

    def play_wav(self, wav_path: Path) -> None:
        if not wav_path.exists() or wav_path.stat().st_size == 0:
            raise TTSProviderError(f"Audio file does not exist or is empty: {wav_path}")
        if sys.platform != "win32":
            raise TTSProviderError("WAV playback is currently implemented for Windows only.")

        try:
            import winsound
        except ImportError as exc:  # pragma: no cover - Windows-only module
            raise TTSProviderError("winsound is not available on this Python installation.") from exc

        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_NODEFAULT)

    def stop(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            return

    def play_system_beep(self) -> None:
        if sys.platform != "win32":
            raise TTSProviderError("System beep test is available on Windows only.")
        try:
            import winsound
        except ImportError as exc:
            raise TTSProviderError("winsound is not available on this Python installation.") from exc
        winsound.MessageBeep(winsound.MB_ICONASTERISK)

    def diagnose(self) -> list[str]:
        results: list[str] = []
        model_dir = self.config.local_model_dir()
        tokenizer_dir = self.config.local_tokenizer_dir()
        results.append(f"Python executable: {sys.executable}")
        results.append(f"Model folder: {'OK' if model_dir.exists() else 'MISSING'} - {model_dir}")
        results.append(f"Tokenizer folder: {'OK' if tokenizer_dir.exists() else 'MISSING'} - {tokenizer_dir}")
        results.append(f"qwen_tts package: {'OK' if importlib.util.find_spec('qwen_tts') else 'MISSING'}")
        results.append(f"soundfile package: {'OK' if importlib.util.find_spec('soundfile') else 'MISSING'}")
        torch_spec = importlib.util.find_spec("torch")
        results.append(f"torch package: {'OK' if torch_spec else 'MISSING'}")
        if torch_spec:
            try:
                import torch

                cuda_state = "OK" if torch.cuda.is_available() else "NOT AVAILABLE"
                cuda_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
                results.append(f"CUDA: {cuda_state} {cuda_name}".strip())
            except Exception as exc:
                results.append(f"CUDA check: ERROR - {exc}")
        results.append(f"Selected backend: {self.config.tts_backend}")
        results.append(f"Windows SAPI fallback: {'ON' if self.config.enable_windows_sapi_fallback else 'OFF'}")
        return results

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise TTSProviderError(
                "Missing Qwen3-TTS runtime in this Python environment. "
                "Run: python -m pip install -r requirements-qwen.txt"
            ) from exc

        dtype = getattr(torch, self.config.torch_dtype, torch.bfloat16)
        source = self.config.model_source()
        attention = "flash_attention_2" if self.config.use_flash_attention else "sdpa"

        try:
            self._model = Qwen3TTSModel.from_pretrained(
                source,
                device_map=self.config.device_map,
                dtype=dtype,
                attn_implementation=attention,
            )
        except Exception as first_exc:  # pragma: no cover - depends on external model runtime
            if attention == "flash_attention_2":
                try:
                    self._model = Qwen3TTSModel.from_pretrained(
                        source,
                        device_map=self.config.device_map,
                        dtype=dtype,
                        attn_implementation="sdpa",
                    )
                    return self._model
                except Exception:
                    pass
            raise TTSProviderError(f"Could not load Qwen3-TTS model from {source}: {first_exc}") from first_exc

        return self._model

    def _cache_path(self, cache_key: str, text: str, language: str, speaker: str) -> Path:
        digest = hashlib.sha256(
            f"{self.config.model_id}|{language}|{speaker}|{text}|{cache_key}".encode("utf-8")
        ).hexdigest()[:20]
        safe_speaker = "".join(ch if ch.isalnum() else "_" for ch in speaker)
        return self.cache_dir / f"{digest}_{language}_{safe_speaker}.wav"

    def _fallback_cache_path(self, cache_key: str, text: str, language: str, speaker: str) -> Path:
        digest = hashlib.sha256(
            f"windows-sapi|{language}|{speaker}|{text}|{cache_key}".encode("utf-8")
        ).hexdigest()[:20]
        return self.cache_dir / f"{digest}_{language}_WindowsSAPI.wav"

    def _synthesize_with_windows_sapi(self, wav_path: Path, text: str, language: str) -> Path:
        if wav_path.exists() and wav_path.stat().st_size > 0:
            return wav_path
        if sys.platform != "win32":
            raise TTSProviderError("Windows SAPI fallback is available on Windows only.")

        text_path = wav_path.with_suffix(".txt")
        text_path.write_text(text, encoding="utf-8")
        culture = "ko-KR" if language == "Korean" else "en-US"
        script = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$textPath = $env:AI_INTERVIEW_TTS_TEXT_PATH
$outPath = $env:AI_INTERVIEW_TTS_OUT_PATH
$cultureName = $env:AI_INTERVIEW_TTS_CULTURE
$text = Get-Content -Raw -Encoding UTF8 -LiteralPath $textPath
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $culture = [System.Globalization.CultureInfo]::GetCultureInfo($cultureName)
    $synth.SelectVoiceByHints(
        [System.Speech.Synthesis.VoiceGender]::NotSet,
        [System.Speech.Synthesis.VoiceAge]::NotSet,
        0,
        $culture
    )
} catch {}
$synth.Volume = 100
$synth.Rate = 0
$synth.SetOutputToWaveFile($outPath)
$synth.Speak($text)
$synth.Dispose()
"""
        env = os.environ.copy()
        env["AI_INTERVIEW_TTS_TEXT_PATH"] = str(text_path)
        env["AI_INTERVIEW_TTS_OUT_PATH"] = str(wav_path)
        env["AI_INTERVIEW_TTS_CULTURE"] = culture
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown PowerShell error"
            raise TTSProviderError(f"Windows SAPI fallback failed: {detail}")
        if not wav_path.exists() or wav_path.stat().st_size == 0:
            raise TTSProviderError(f"Windows SAPI fallback produced no audio: {wav_path}")
        return wav_path
