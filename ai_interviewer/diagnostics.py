from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from ai_interviewer.config import AppConfig, QWEN_BACKEND, WINDOWS_SAPI_BACKEND, default_log_path


STATUS_OK = "OK"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class DiagnosticItem:
    name: str
    status: str
    detail: str
    required: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticReport:
    items: list[DiagnosticItem]

    @property
    def has_failures(self) -> bool:
        return any(item.status == STATUS_FAIL and item.required for item in self.items)

    @property
    def has_warnings(self) -> bool:
        return any(item.status in {STATUS_WARN, STATUS_FAIL} for item in self.items)

    def summary_ko(self) -> str:
        if self.has_failures:
            return "런타임 상태: 실패"
        if self.has_warnings:
            return "런타임 상태: 경고"
        return "런타임 상태: 준비됨"

    def as_lines(self) -> list[str]:
        return [f"[{item.status}] {item.name}: {item.detail}" for item in self.items]


def collect_runtime_diagnostics(config: AppConfig) -> RuntimeDiagnosticReport:
    items: list[DiagnosticItem] = []
    items.extend(_storage_checks(config))
    items.extend(_tts_checks(config))
    items.extend(_stt_checks(config))
    items.extend(_video_checks(config))
    items.extend(_followup_checks(config))
    return RuntimeDiagnosticReport(items)


def _storage_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for name, path in (
        ("세션 저장 폴더", config.sessions_root),
        ("모델 폴더", config.model_root),
        ("설정 폴더", config.config_path.parent),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".ai_interview_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            items.append(DiagnosticItem(name, STATUS_OK, str(path), required=True))
        except OSError as exc:
            items.append(DiagnosticItem(name, STATUS_FAIL, f"{path} ({exc})", required=True))
    items.append(DiagnosticItem("설정 파일", STATUS_OK, str(config.config_path), required=False))
    items.append(DiagnosticItem("로그 파일", STATUS_OK, str(default_log_path()), required=False))
    return items


def _tts_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = [
        DiagnosticItem("선택된 TTS 엔진", STATUS_OK, config.tts_backend, required=True),
    ]

    if config.tts_backend == WINDOWS_SAPI_BACKEND:
        items.append(DiagnosticItem("Windows SAPI", STATUS_OK if os.name == "nt" else STATUS_FAIL, "Windows 전용", required=True))
        return items

    model_dir = config.local_model_dir()
    tokenizer_dir = config.local_tokenizer_dir()
    items.append(
        DiagnosticItem(
            "Qwen 모델",
            STATUS_OK if model_dir.exists() else STATUS_WARN,
            str(model_dir) if model_dir.exists() else f"로컬 모델 없음, Hub/model id 사용 예정: {config.model_id}",
            required=False,
        )
    )
    items.append(
        DiagnosticItem(
            "Qwen tokenizer",
            STATUS_OK if tokenizer_dir.exists() else STATUS_WARN,
            str(tokenizer_dir) if tokenizer_dir.exists() else "로컬 tokenizer 없음",
            required=False,
        )
    )
    for package in ("qwen_tts", "soundfile", "torch"):
        items.append(
            DiagnosticItem(
                package,
                STATUS_OK if importlib.util.find_spec(package) else STATUS_FAIL,
                "installed" if importlib.util.find_spec(package) else "missing",
                required=config.tts_backend == QWEN_BACKEND,
            )
        )

    torch_spec = importlib.util.find_spec("torch")
    if torch_spec:
        try:
            import torch

            cuda_ok = torch.cuda.is_available()
            detail = torch.cuda.get_device_name(0) if cuda_ok else "CUDA 사용 불가"
            items.append(DiagnosticItem("CUDA", STATUS_OK if cuda_ok else STATUS_WARN, detail, required=False))
        except Exception as exc:
            items.append(DiagnosticItem("CUDA", STATUS_WARN, str(exc), required=False))

    fallback_status = STATUS_WARN if config.enable_windows_sapi_fallback else STATUS_OK
    fallback_detail = "Qwen 실패 시 Windows 음성 사용" if config.enable_windows_sapi_fallback else "fallback 꺼짐"
    items.append(DiagnosticItem("Windows fallback", fallback_status, fallback_detail, required=False))
    return items


def _stt_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for package in ("sounddevice", "soundfile", "numpy", "faster_whisper"):
        items.append(
            DiagnosticItem(
                f"STT dependency: {package}",
                STATUS_OK if importlib.util.find_spec(package) else STATUS_WARN,
                "installed" if importlib.util.find_spec(package) else "missing; STT 사용 시 requirements-interactive.txt 필요",
                required=False,
            )
        )

    if importlib.util.find_spec("sounddevice"):
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="input")
            items.append(DiagnosticItem("마이크 입력", STATUS_OK, str(device.get("name", "default")), required=False))
        except Exception as exc:
            items.append(DiagnosticItem("마이크 입력", STATUS_WARN, str(exc), required=False))
    return items


def _video_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    if config.video_path.exists():
        items.append(DiagnosticItem("면접관 영상 파일", STATUS_OK, str(config.video_path), required=False))
    else:
        items.append(DiagnosticItem("면접관 영상 파일", STATUS_WARN, "파일 없음; 내장 애니메이션 사용", required=False))
    for package in ("cv2", "PIL"):
        items.append(
            DiagnosticItem(
                f"영상 dependency: {package}",
                STATUS_OK if importlib.util.find_spec(package) else STATUS_WARN,
                "installed" if importlib.util.find_spec(package) else "missing; 영상 파일 재생 제한",
                required=False,
            )
        )
    return items


def _followup_checks(config: AppConfig) -> list[DiagnosticItem]:
    provider = config.followup_provider
    if provider == "Rules":
        return [DiagnosticItem("꼬리질문 provider", STATUS_OK, "내장 규칙 기반", required=False)]

    model = config.ollama_model or os.environ.get("AI_INTERVIEW_OLLAMA_MODEL", "").strip()
    if provider == "Ollama" and not model:
        return [DiagnosticItem("꼬리질문 provider", STATUS_WARN, "Ollama 모델 미설정; 규칙 기반 fallback", required=False)]
    if model:
        return [DiagnosticItem("꼬리질문 provider", STATUS_OK, f"Ollama: {model}", required=False)]
    return [DiagnosticItem("꼬리질문 provider", STATUS_OK, "Auto; 모델 없으면 규칙 기반", required=False)]


def diagnostics_text(report: RuntimeDiagnosticReport) -> str:
    return "\n".join([report.summary_ko(), "", *report.as_lines()])
