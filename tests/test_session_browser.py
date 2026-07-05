import json
from pathlib import Path

import pytest

from ai_interviewer.session_browser import SESSION_ID_PATTERN, delete_session, list_sessions
from ai_interviewer.session_store import new_session_id


def _make_session(root: Path, session_id: str, records: list[dict] | None = None, corrupt: bool = False) -> Path:
    session_dir = root / session_id
    session_dir.mkdir(parents=True)
    if corrupt:
        (session_dir / "session.json").write_text("{not json", encoding="utf-8")
        return session_dir
    payload = {
        "schema_version": 2,
        "session_id": session_id,
        "created_at": "2026-07-04T10:00:00+09:00",
        "question_count": len(records or []),
        "records": records or [],
    }
    (session_dir / "session.json").write_text(json.dumps(payload), encoding="utf-8")
    return session_dir


def test_new_session_id_matches_browser_pattern() -> None:
    assert SESSION_ID_PATTERN.match(new_session_id())


def test_list_sessions_reads_summaries(tmp_path) -> None:
    records = [
        {"answer_seconds": 12.5, "transcript": "answer one"},
        {"answer_seconds": "", "transcript": ""},
    ]
    _make_session(tmp_path, "20260701-090000-aabbccdd", records)
    (tmp_path / "20260701-090000-aabbccdd" / "answers").mkdir()
    (tmp_path / "20260701-090000-aabbccdd" / "answers" / "answer_001.wav").write_bytes(b"x" * 100)

    summaries = list_sessions(tmp_path)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.session_id == "20260701-090000-aabbccdd"
    assert summary.question_count == 2
    assert summary.answered_count == 1
    assert summary.size_bytes > 100


def test_list_sessions_sorted_newest_first_and_skips_foreign_dirs(tmp_path) -> None:
    _make_session(tmp_path, "20260701-090000-aabbccdd", [])
    _make_session(tmp_path, "20260702-090000-aabbccdd", [])
    (tmp_path / "not-a-session").mkdir()
    (tmp_path / "_preload").mkdir()

    summaries = list_sessions(tmp_path)

    assert [summary.session_id for summary in summaries] == [
        "20260702-090000-aabbccdd",
        "20260701-090000-aabbccdd",
    ]


def test_list_sessions_tolerates_corrupt_json(tmp_path) -> None:
    _make_session(tmp_path, "20260701-090000-aabbccdd", corrupt=True)

    summaries = list_sessions(tmp_path)

    assert len(summaries) == 1
    assert summaries[0].question_count == 0


def test_delete_session_removes_folder(tmp_path) -> None:
    _make_session(tmp_path, "20260701-090000-aabbccdd", [])

    delete_session(tmp_path, "20260701-090000-aabbccdd")

    assert not (tmp_path / "20260701-090000-aabbccdd").exists()


def test_delete_session_rejects_non_session_ids(tmp_path) -> None:
    (tmp_path / "important").mkdir()

    with pytest.raises(ValueError):
        delete_session(tmp_path, "important")
    with pytest.raises(ValueError):
        delete_session(tmp_path, "../outside")
    assert (tmp_path / "important").exists()


def test_list_sessions_missing_root(tmp_path) -> None:
    assert list_sessions(tmp_path / "nope") == []
