from __future__ import annotations

import csv
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_interviewer.question_parser import ParsedQuestion


EXPORT_FIELDS = [
    "session_id",
    "question_index",
    "raw_question",
    "clean_question",
    "language",
    "speaker",
    "tts_started_at",
    "tts_finished_at",
    "answer_started_at",
    "answer_finished_at",
    "answer_seconds",
    "repeat_count",
    "memo",
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_session_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


@dataclass(slots=True)
class QuestionRecord:
    question_index: int
    raw_question: str
    clean_question: str
    language: str = ""
    speaker: str = ""
    tts_started_at: str = ""
    tts_finished_at: str = ""
    answer_started_at: str = ""
    answer_finished_at: str = ""
    answer_seconds: float | None = None
    repeat_count: int = 0
    memo: str = ""
    _answer_start_monotonic: float | None = field(default=None, repr=False)

    def export_row(self, session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "question_index": self.question_index,
            "raw_question": self.raw_question,
            "clean_question": self.clean_question,
            "language": self.language,
            "speaker": self.speaker,
            "tts_started_at": self.tts_started_at,
            "tts_finished_at": self.tts_finished_at,
            "answer_started_at": self.answer_started_at,
            "answer_finished_at": self.answer_finished_at,
            "answer_seconds": "" if self.answer_seconds is None else round(self.answer_seconds, 3),
            "repeat_count": self.repeat_count,
            "memo": self.memo,
        }


@dataclass(slots=True)
class InterviewSession:
    session_id: str
    sessions_root: Path
    records: list[QuestionRecord]
    created_at: str = field(default_factory=now_iso)
    _created_monotonic: float = field(default_factory=time.monotonic, repr=False)

    @classmethod
    def create(cls, questions: list[ParsedQuestion], sessions_root: Path) -> "InterviewSession":
        records = [
            QuestionRecord(
                question_index=index,
                raw_question=question.raw,
                clean_question=question.clean,
            )
            for index, question in enumerate(questions, start=1)
        ]
        session = cls(session_id=new_session_id(), sessions_root=Path(sessions_root), records=records)
        session.session_dir.mkdir(parents=True, exist_ok=True)
        session.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        session.save()
        return session

    @property
    def session_dir(self) -> Path:
        return self.sessions_root / self.session_id

    @property
    def audio_cache_dir(self) -> Path:
        return self.session_dir / "audio_cache"

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._created_monotonic

    def record_at(self, zero_based_index: int) -> QuestionRecord:
        return self.records[zero_based_index]

    def mark_tts_started(self, zero_based_index: int, language: str, speaker: str) -> None:
        record = self.record_at(zero_based_index)
        record.language = language
        record.speaker = speaker
        record.tts_started_at = now_iso()

    def mark_tts_finished(self, zero_based_index: int) -> None:
        self.record_at(zero_based_index).tts_finished_at = now_iso()

    def increment_repeat(self, zero_based_index: int) -> None:
        self.record_at(zero_based_index).repeat_count += 1

    def start_answer(self, zero_based_index: int) -> None:
        record = self.record_at(zero_based_index)
        if record.answer_started_at:
            return
        record.answer_started_at = now_iso()
        record._answer_start_monotonic = time.monotonic()

    def finish_answer(self, zero_based_index: int) -> None:
        record = self.record_at(zero_based_index)
        if not record.answer_started_at or record.answer_finished_at:
            return
        record.answer_finished_at = now_iso()
        if record._answer_start_monotonic is not None:
            record.answer_seconds = time.monotonic() - record._answer_start_monotonic

    def set_memo(self, zero_based_index: int, memo: str) -> None:
        self.record_at(zero_based_index).memo = memo.strip()

    def export_rows(self) -> list[dict[str, Any]]:
        return [record.export_row(self.session_id) for record in self.records]

    def save(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        rows = self.export_rows()

        json_path = self.session_dir / "session.json"
        csv_path = self.session_dir / "session.csv"

        payload = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "question_count": len(self.records),
            "records": rows,
        }
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=EXPORT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
