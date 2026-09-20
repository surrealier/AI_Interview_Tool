from __future__ import annotations

import json

import pytest

from ai_interviewer import config as config_module
from ai_interviewer import credentials


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(config_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(credentials, "app_data_dir", lambda: tmp_path)
    for name in credentials.ANTHROPIC_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_no_key_by_default() -> None:
    assert credentials.anthropic_api_key() == ""
    assert credentials.has_anthropic_key() is False
    assert credentials.anthropic_key_source() == credentials.SOURCE_NONE


def test_environment_key_is_used_without_touching_disk(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    assert credentials.anthropic_api_key() == "sk-env"
    assert credentials.anthropic_key_source() == credentials.SOURCE_ENV
    assert not (tmp_path / credentials.CREDENTIALS_FILE).exists()


def test_environment_wins_over_the_saved_key(monkeypatch: pytest.MonkeyPatch) -> None:
    credentials.store_anthropic_api_key("sk-file")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    assert credentials.anthropic_api_key() == "sk-env"


def test_auth_token_also_counts_as_a_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-token")
    assert credentials.has_anthropic_key() is True


def test_key_round_trips_through_the_store(tmp_path) -> None:
    credentials.store_anthropic_api_key("sk-saved")
    assert credentials.anthropic_api_key() == "sk-saved"
    assert credentials.anthropic_key_source() == credentials.SOURCE_FILE
    payload = json.loads((tmp_path / credentials.CREDENTIALS_FILE).read_text(encoding="utf-8"))
    assert payload == {"anthropic_api_key": "sk-saved"}


def test_clearing_removes_the_file(tmp_path) -> None:
    credentials.store_anthropic_api_key("sk-saved")
    credentials.clear_anthropic_api_key()
    assert credentials.anthropic_api_key() == ""
    assert not (tmp_path / credentials.CREDENTIALS_FILE).exists()


def test_keys_are_never_stored_in_the_app_config(tmp_path) -> None:
    """config.json ends up in support bundles; a key must not ride along."""
    credentials.store_anthropic_api_key("sk-saved")
    config = config_module.AppConfig(config_path=tmp_path / "config.json")
    config.save()
    written = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert "sk-saved" not in json.dumps(written)
    assert not any("api_key" in key for key in written)


def test_corrupt_store_is_treated_as_empty(tmp_path) -> None:
    (tmp_path / credentials.CREDENTIALS_FILE).write_text("{not json", encoding="utf-8")
    assert credentials.anthropic_api_key() == ""


@pytest.mark.parametrize(
    "key,expected",
    [
        ("", ""),
        ("short", "•••••"),
        ("sk-ant-abcdefghijklmnop", "sk-ant…mnop"),
    ],
)
def test_masking_never_shows_the_whole_key(key: str, expected: str) -> None:
    assert credentials.masked(key) == expected
