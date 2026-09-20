"""Local credential store for the optional cloud provider.

API keys are deliberately kept out of `config.json`: that file is written on
every settings change, is copied into support bundles, and is the first thing a
user pastes into an issue. Keys live in their own file, are never logged, and an
environment variable always wins so a user can avoid on-disk storage entirely.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ai_interviewer.config import app_data_dir


logger = logging.getLogger(__name__)

CREDENTIALS_FILE = "credentials.json"
ANTHROPIC_ENV_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

SOURCE_NONE = "none"
SOURCE_ENV = "env"
SOURCE_FILE = "file"


def credentials_path() -> Path:
    return app_data_dir() / CREDENTIALS_FILE


def anthropic_api_key() -> str:
    """Resolve a key: environment first, then the local store."""
    for name in ANTHROPIC_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return _read().get("anthropic_api_key", "").strip()


def anthropic_key_source() -> str:
    for name in ANTHROPIC_ENV_VARS:
        if (os.environ.get(name) or "").strip():
            return SOURCE_ENV
    if _read().get("anthropic_api_key", "").strip():
        return SOURCE_FILE
    return SOURCE_NONE


def has_anthropic_key() -> bool:
    return bool(anthropic_api_key())


def store_anthropic_api_key(key: str) -> None:
    """Save (or, given an empty value, remove) the key in the local store."""
    value = (key or "").strip()
    payload = _read()
    if value:
        payload["anthropic_api_key"] = value
    else:
        payload.pop("anthropic_api_key", None)
    _write(payload)


def clear_anthropic_api_key() -> None:
    store_anthropic_api_key("")


def masked(key: str) -> str:
    """A form safe to show in the UI and in diagnostics."""
    value = (key or "").strip()
    if not value:
        return ""
    if len(value) <= 10:
        return "•" * len(value)
    return f"{value[:6]}…{value[-4:]}"


# -- file I/O ----------------------------------------------------------------


def _read() -> dict[str, str]:
    path = credentials_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read the credential store; treating it as empty.")
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def _write(payload: dict[str, str]) -> None:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not payload:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove the credential store.")
        return

    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)
    _restrict_permissions(path)


def _restrict_permissions(path: Path) -> None:
    """Narrow the file to its owner where the platform has POSIX modes.

    On Windows the store lives under %APPDATA%, which already inherits a
    user-only ACL from the profile directory; rewriting the ACL here (icacls
    /inheritance:r) risks stripping the owner's own access, so it is left alone.
    """
    if os.name == "nt":
        return
    try:
        path.chmod(0o600)
    except OSError:
        logger.debug("Could not restrict permissions on the credential store.", exc_info=True)
