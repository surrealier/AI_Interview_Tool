from __future__ import annotations

import json

import pytest

from ai_interviewer.config import (
    AI_PROVIDER_AUTO,
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_OFFLINE,
    AI_PROVIDER_OLLAMA,
    DEFAULT_CLAUDE_MODEL,
    MAX_PROBE_DEPTH,
    AppConfig,
    normalize_ai_provider,
)


def _config(tmp_path, **payload) -> AppConfig:
    path = tmp_path / "config.json"
    if payload:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return AppConfig.load(path)


def test_analysis_is_offline_by_default(tmp_path) -> None:
    config = _config(tmp_path)
    assert config.ai_provider == AI_PROVIDER_OFFLINE
    assert config.enable_cloud_ai is False
    assert config.analysis_is_local_only() is True
    assert config.enable_live_scoring is True
    assert config.enable_adaptive_probing is True
    assert config.claude_model == DEFAULT_CLAUDE_MODEL


def test_cloud_provider_without_consent_falls_back_to_offline(tmp_path) -> None:
    """A config edited by hand must not start sending data off the machine."""
    config = _config(tmp_path, ai_provider="Claude", enable_cloud_ai=False)
    assert config.ai_provider == AI_PROVIDER_OFFLINE
    assert config.analysis_is_local_only() is True


def test_cloud_provider_with_consent_is_kept(tmp_path) -> None:
    config = _config(tmp_path, ai_provider="Claude", enable_cloud_ai=True)
    assert config.ai_provider == AI_PROVIDER_CLAUDE
    assert config.analysis_is_local_only() is False


def test_auto_without_consent_stays_local_only(tmp_path) -> None:
    config = _config(tmp_path, ai_provider="Auto", enable_cloud_ai=False)
    assert config.ai_provider == AI_PROVIDER_AUTO
    assert config.analysis_is_local_only() is True


def test_legacy_ollama_followup_setting_is_carried_forward(tmp_path) -> None:
    """Before the analysis layer, followup_provider was the only local switch."""
    config = _config(tmp_path, followup_provider="Ollama", ollama_model="llama3")
    assert config.ai_provider == AI_PROVIDER_OLLAMA


def test_legacy_auto_followup_does_not_silently_enable_a_model(tmp_path) -> None:
    config = _config(tmp_path, followup_provider="Auto")
    assert config.ai_provider == AI_PROVIDER_OFFLINE


@pytest.mark.parametrize(
    "value,expected",
    [("Offline", "Offline"), ("claude", "Claude"), ("OLLAMA", "Ollama"), ("nonsense", "Offline"), (None, "Offline")],
)
def test_provider_names_are_normalized(value, expected) -> None:
    assert normalize_ai_provider(value) == expected


@pytest.mark.parametrize("depth,expected", [(-3, 0), (0, 0), (2, 2), (99, MAX_PROBE_DEPTH), ("x", 2)])
def test_probe_depth_is_clamped(tmp_path, depth, expected) -> None:
    assert _config(tmp_path, max_probe_depth=depth).max_probe_depth == expected


def test_unknown_effort_and_seniority_fall_back(tmp_path) -> None:
    config = _config(tmp_path, ai_effort="turbo", target_seniority="wizard")
    assert config.ai_effort == "medium"
    assert config.target_seniority == "mid"


def test_blank_claude_model_falls_back_to_the_default(tmp_path) -> None:
    assert _config(tmp_path, claude_model="  ").claude_model == DEFAULT_CLAUDE_MODEL


def test_analysis_settings_survive_a_save_and_reload(tmp_path) -> None:
    config = _config(tmp_path)
    config.ai_provider = AI_PROVIDER_CLAUDE
    config.enable_cloud_ai = True
    config.ai_effort = "high"
    config.target_role = "Staff Engineer"
    config.job_description = "Own payments."
    config.max_probe_depth = 3
    config.save()

    reloaded = AppConfig.load(tmp_path / "config.json")
    assert reloaded.ai_provider == AI_PROVIDER_CLAUDE
    assert reloaded.enable_cloud_ai is True
    assert reloaded.ai_effort == "high"
    assert reloaded.target_role == "Staff Engineer"
    assert reloaded.job_description == "Own payments."
    assert reloaded.max_probe_depth == 3
