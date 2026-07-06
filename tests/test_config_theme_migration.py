from __future__ import annotations

import json

from ai_interviewer.config import AppConfig


def test_legacy_ui_theme_key_falls_back_to_system(tmp_path) -> None:
    # Pre-Qt configs stored `ui_theme: "light"` (which actually rendered a
    # dark palette). The key is gone; loading must land on the new default.
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"ui_theme": "light"}), encoding="utf-8")

    config = AppConfig.load(config_path)

    assert config.ui_theme_mode == "system"
    assert not hasattr(config, "ui_theme")


def test_invalid_theme_mode_falls_back_to_system(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"ui_theme_mode": "neon"}), encoding="utf-8")

    config = AppConfig.load(config_path)

    assert config.ui_theme_mode == "system"


def test_theme_mode_round_trips(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config = AppConfig(config_path=config_path)
    config.ui_theme_mode = "dark"
    config.save()

    reloaded = AppConfig.load(config_path)

    assert reloaded.ui_theme_mode == "dark"
