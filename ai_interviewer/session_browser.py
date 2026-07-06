"""Session listing and deletion (pure filesystem logic).

The browser dialog lives in ai_interviewer.ui.dialogs.session_browser; this
module stays Qt-free so core tooling and tests can use it headlessly.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)

# Matches ids from session_store.new_session_id(): YYYYMMDD-HHMMSS-<8 hex>.
SESSION_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    path: Path
    created_at: str
    question_count: int
    answered_count: int
    size_bytes: int


def _directory_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def list_sessions(sessions_root: Path) -> list[SessionSummary]:
    """List saved sessions, newest first; tolerates missing/corrupt session.json."""
    sessions_root = Path(sessions_root)
    if not sessions_root.exists():
        return []
    summaries: list[SessionSummary] = []
    for child in sessions_root.iterdir():
        if not child.is_dir() or not SESSION_ID_PATTERN.match(child.name):
            continue
        created_at = ""
        question_count = 0
        answered_count = 0
        try:
            payload = json.loads((child / "session.json").read_text(encoding="utf-8"))
            created_at = str(payload.get("created_at", ""))
            records = payload.get("records", []) or []
            question_count = int(payload.get("question_count", len(records)))
            answered_count = sum(
                1
                for record in records
                if isinstance(record, dict)
                and (record.get("answer_seconds") not in ("", None) or str(record.get("transcript", "")).strip())
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Could not parse session.json for %s", child)
        summaries.append(
            SessionSummary(
                session_id=child.name,
                path=child,
                created_at=created_at,
                question_count=question_count,
                answered_count=answered_count,
                size_bytes=_directory_bytes(child),
            )
        )
    return sorted(summaries, key=lambda summary: summary.session_id, reverse=True)


def delete_session(sessions_root: Path, session_id: str) -> None:
    """Delete one session folder. Refuses anything that is not a direct,
    id-shaped child of sessions_root."""
    if not SESSION_ID_PATTERN.match(session_id):
        raise ValueError(f"Not a session id: {session_id!r}")
    sessions_root = Path(sessions_root).resolve()
    target = (sessions_root / session_id).resolve()
    if target.parent != sessions_root:
        raise ValueError(f"Session path escapes the sessions root: {target}")
    shutil.rmtree(target)
