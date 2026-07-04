from ai_interviewer.config import (
    AppConfig,
    MODEL_INSTALL_MARKER,
    TOKENIZER_MODEL_ID,
    WINDOWS_SAPI_BACKEND,
    model_dir_name,
)
from ai_interviewer.diagnostics import STATUS_FAIL, STATUS_OK, collect_runtime_diagnostics


def _config(tmp_path) -> AppConfig:
    config = AppConfig(config_path=tmp_path / "config.json")
    config.model_root = tmp_path / "models"
    config.sessions_root = tmp_path / "sessions"
    config.video_path = tmp_path / "assets" / "interviewer.mp4"
    return config


def _install_model(config: AppConfig, model_id: str) -> None:
    model_dir = config.model_root / model_dir_name(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / MODEL_INSTALL_MARKER).write_text("{}", encoding="utf-8")


def _item(report, name):
    return next(item for item in report.items if item.name == name)


def test_missing_qwen_model_is_required_failure(tmp_path) -> None:
    config = _config(tmp_path)

    report = collect_runtime_diagnostics(config)

    model_item = _item(report, "Qwen 모델")
    assert model_item.status == STATUS_FAIL
    assert model_item.required is True
    assert report.has_failures


def test_installed_qwen_model_passes(tmp_path) -> None:
    config = _config(tmp_path)
    _install_model(config, config.model_id)
    _install_model(config, TOKENIZER_MODEL_ID)

    report = collect_runtime_diagnostics(config)

    assert _item(report, "Qwen 모델").status == STATUS_OK
    assert _item(report, "Qwen tokenizer").status == STATUS_OK


def test_sapi_backend_skips_model_checks(tmp_path) -> None:
    config = _config(tmp_path)
    config.tts_backend = WINDOWS_SAPI_BACKEND

    report = collect_runtime_diagnostics(config)

    assert all(item.name != "Qwen 모델" for item in report.items)
