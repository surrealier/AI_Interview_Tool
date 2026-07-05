from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass

from ai_interviewer.config import (
    AppConfig,
    QWEN_BACKEND,
    TOKENIZER_MODEL_ID,
    WINDOWS_SAPI_BACKEND,
    default_log_path,
    is_model_installed,
)
from ai_interviewer.i18n import tr


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

    def summary(self) -> str:
        if self.has_failures:
            return tr("diag.summary_fail")
        if self.has_warnings:
            return tr("diag.summary_warn")
        return tr("diag.summary_ready")

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
        (tr("diag.sessions_dir"), config.sessions_root),
        (tr("diag.model_dir"), config.model_root),
        (tr("diag.config_dir"), config.config_path.parent),
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".ai_interview_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            items.append(DiagnosticItem(name, STATUS_OK, str(path), required=True))
        except OSError as exc:
            items.append(DiagnosticItem(name, STATUS_FAIL, f"{path} ({exc})", required=True))
    items.append(DiagnosticItem(tr("diag.config_file"), STATUS_OK, str(config.config_path), required=False))
    items.append(DiagnosticItem(tr("diag.log_file"), STATUS_OK, str(default_log_path()), required=False))
    return items


def _tts_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = [
        DiagnosticItem(tr("diag.tts_engine"), STATUS_OK, tr(f"backend.{config.tts_backend}"), required=True),
    ]

    if config.tts_backend == WINDOWS_SAPI_BACKEND:
        items.append(
            DiagnosticItem(
                "Windows SAPI",
                STATUS_OK if os.name == "nt" else STATUS_FAIL,
                tr("diag.windows_only"),
                required=True,
            )
        )
        return items

    model_dir = config.local_model_dir()
    tokenizer_dir = config.local_tokenizer_dir()
    model_installed = is_model_installed(config.model_root, config.model_id)
    tokenizer_installed = is_model_installed(config.model_root, TOKENIZER_MODEL_ID)
    items.append(
        DiagnosticItem(
            tr("diag.qwen_model"),
            STATUS_OK if model_installed else STATUS_FAIL,
            str(model_dir) if model_installed else tr("diag.model_missing", model_id=config.model_id),
            required=True,
        )
    )
    items.append(
        DiagnosticItem(
            tr("diag.qwen_tokenizer"),
            STATUS_OK if tokenizer_installed else STATUS_FAIL,
            str(tokenizer_dir) if tokenizer_installed else tr("diag.tokenizer_missing"),
            required=True,
        )
    )
    for package in ("qwen_tts", "soundfile", "torch"):
        items.append(
            DiagnosticItem(
                package,
                STATUS_OK if importlib.util.find_spec(package) else STATUS_FAIL,
                tr("diag.pkg_installed") if importlib.util.find_spec(package) else tr("diag.pkg_missing"),
                required=config.tts_backend == QWEN_BACKEND,
            )
        )

    torch_spec = importlib.util.find_spec("torch")
    if torch_spec:
        try:
            import torch

            cuda_ok = torch.cuda.is_available()
            detail = torch.cuda.get_device_name(0) if cuda_ok else tr("diag.cuda_unavailable")
            items.append(DiagnosticItem("CUDA", STATUS_OK if cuda_ok else STATUS_WARN, detail, required=False))
        except Exception as exc:
            items.append(DiagnosticItem("CUDA", STATUS_WARN, str(exc), required=False))

    fallback_status = STATUS_WARN if config.enable_windows_sapi_fallback else STATUS_OK
    fallback_detail = tr("diag.fallback_on") if config.enable_windows_sapi_fallback else tr("diag.fallback_off")
    items.append(DiagnosticItem("Windows fallback", fallback_status, fallback_detail, required=False))
    return items


def _stt_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    for package in ("sounddevice", "soundfile", "numpy", "faster_whisper"):
        items.append(
            DiagnosticItem(
                tr("diag.stt_dep", package=package),
                STATUS_OK if importlib.util.find_spec(package) else STATUS_WARN,
                tr("diag.pkg_installed") if importlib.util.find_spec(package) else tr("diag.pkg_missing_stt"),
                required=False,
            )
        )

    if importlib.util.find_spec("sounddevice"):
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="input")
            items.append(DiagnosticItem(tr("diag.mic_input"), STATUS_OK, str(device.get("name", "default")), required=False))
        except Exception as exc:
            items.append(DiagnosticItem(tr("diag.mic_input"), STATUS_WARN, str(exc), required=False))
    return items


def _video_checks(config: AppConfig) -> list[DiagnosticItem]:
    items: list[DiagnosticItem] = []
    if config.video_path.exists():
        items.append(DiagnosticItem(tr("diag.video_file"), STATUS_OK, str(config.video_path), required=False))
    else:
        items.append(DiagnosticItem(tr("diag.video_file"), STATUS_WARN, tr("diag.video_missing"), required=False))
    for package in ("cv2", "PIL"):
        items.append(
            DiagnosticItem(
                tr("diag.video_dep", package=package),
                STATUS_OK if importlib.util.find_spec(package) else STATUS_WARN,
                tr("diag.pkg_installed") if importlib.util.find_spec(package) else tr("diag.pkg_missing_video"),
                required=False,
            )
        )
    return items


def _followup_checks(config: AppConfig) -> list[DiagnosticItem]:
    provider = config.followup_provider
    if provider == "Rules":
        return [DiagnosticItem(tr("diag.followup_provider"), STATUS_OK, tr("diag.followup_rules"), required=False)]

    model = config.ollama_model or os.environ.get("AI_INTERVIEW_OLLAMA_MODEL", "").strip()
    if provider == "Ollama" and not model:
        return [DiagnosticItem(tr("diag.followup_provider"), STATUS_WARN, tr("diag.followup_no_model"), required=False)]
    if model:
        return [DiagnosticItem(tr("diag.followup_provider"), STATUS_OK, f"Ollama: {model}", required=False)]
    return [DiagnosticItem(tr("diag.followup_provider"), STATUS_OK, tr("diag.followup_auto"), required=False)]


def diagnostics_text(report: RuntimeDiagnosticReport) -> str:
    return "\n".join([report.summary(), "", *report.as_lines()])
