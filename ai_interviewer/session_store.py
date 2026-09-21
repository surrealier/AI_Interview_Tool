from __future__ import annotations

import csv
import json
import os
import threading
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
    "tts_backend",
    "tts_warning",
    "quality_degraded",
    "tts_started_at",
    "tts_finished_at",
    "answer_started_at",
    "answer_finished_at",
    "answer_seconds",
    "answer_audio_path",
    "transcript",
    "follow_up_question",
    "follow_up_generated_at",
    "repeat_count",
    "memo",
    # Schema 3: the analysis columns. Flattened here on purpose so the CSV
    # stays openable in a spreadsheet; session.json keeps the full objects.
    "competency",
    "stage",
    "answer_score",
    "answer_band",
    "star_coverage",
    "probe_count",
    "words_per_minute",
    "filler_rate",
    "analysis_engine",
]

# 3 added per-answer evaluation, delivery metrics, probe chains, and the
# session blueprint/report. Readers of older files still work: every new field
# has a default.
SESSION_SCHEMA_VERSION = 3


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
    tts_backend: str = ""
    tts_warning: str = ""
    quality_degraded: bool = False
    tts_started_at: str = ""
    tts_finished_at: str = ""
    answer_started_at: str = ""
    answer_finished_at: str = ""
    answer_seconds: float | None = None
    answer_audio_path: str = ""
    transcript: str = ""
    follow_up_question: str = ""
    follow_up_generated_at: str = ""
    repeat_count: int = 0
    memo: str = ""
    competency: str = ""
    stage: str = ""
    evaluation: dict[str, Any] | None = None
    delivery: dict[str, Any] | None = None
    probes: list[dict[str, Any]] = field(default_factory=list)
    _answer_start_monotonic: float | None = field(default=None, repr=False)

    @property
    def probe_depth(self) -> int:
        return len(self.probes)

    @property
    def answer_score(self) -> int | None:
        if not self.evaluation:
            return None
        value = self.evaluation.get("overall")
        return None if value is None else int(value)

    @property
    def answer_band(self) -> str:
        if not self.evaluation:
            return ""
        return str(self.evaluation.get("band", ""))

    @property
    def analysis_engine(self) -> str:
        if not self.evaluation:
            return ""
        return str(self.evaluation.get("engine", ""))

    def export_row(self, session_id: str) -> dict[str, Any]:
        score = self.answer_score
        evaluation = self.evaluation or {}
        delivery = self.delivery or {}
        return {
            "session_id": session_id,
            "question_index": self.question_index,
            "raw_question": self.raw_question,
            "clean_question": self.clean_question,
            "language": self.language,
            "speaker": self.speaker,
            "tts_backend": self.tts_backend,
            "tts_warning": self.tts_warning,
            "quality_degraded": self.quality_degraded,
            "tts_started_at": self.tts_started_at,
            "tts_finished_at": self.tts_finished_at,
            "answer_started_at": self.answer_started_at,
            "answer_finished_at": self.answer_finished_at,
            "answer_seconds": "" if self.answer_seconds is None else round(self.answer_seconds, 3),
            "answer_audio_path": self.answer_audio_path,
            "transcript": self.transcript,
            "follow_up_question": self.follow_up_question,
            "follow_up_generated_at": self.follow_up_generated_at,
            "repeat_count": self.repeat_count,
            "memo": self.memo,
            "competency": self.competency,
            "stage": self.stage,
            "answer_score": "" if score is None else score,
            "answer_band": self.answer_band,
            "star_coverage": len(evaluation.get("star_parts", []) or []),
            "probe_count": self.probe_depth,
            "words_per_minute": round(float(delivery.get("words_per_minute", 0.0) or 0.0), 1),
            "filler_rate": round(float(delivery.get("filler_rate", 0.0) or 0.0), 2),
            "analysis_engine": self.analysis_engine,
        }

    def json_payload(self, session_id: str) -> dict[str, Any]:
        """The CSV columns plus the objects a spreadsheet cannot hold."""
        payload = self.export_row(session_id)
        payload["evaluation"] = self.evaluation
        payload["delivery"] = self.delivery
        payload["probes"] = list(self.probes)
        return payload


@dataclass(slots=True)
class InterviewSession:
    session_id: str
    sessions_root: Path
    records: list[QuestionRecord]
    created_at: str = field(default_factory=now_iso)
    interview_type: str = ""
    language: str = ""
    role: str = ""
    blueprint: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    _created_monotonic: float = field(default_factory=time.monotonic, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @classmethod
    def create(
        cls,
        questions: list[ParsedQuestion],
        sessions_root: Path,
        *,
        interview_type: str = "",
        language: str = "",
        role: str = "",
    ) -> "InterviewSession":
        records = [
            QuestionRecord(
                question_index=index,
                raw_question=question.raw,
                clean_question=question.clean,
            )
            for index, question in enumerate(questions, start=1)
        ]
        session = cls(
            session_id=new_session_id(),
            sessions_root=Path(sessions_root),
            records=records,
            interview_type=interview_type,
            language=language,
            role=role,
        )
        session.session_dir.mkdir(parents=True, exist_ok=True)
        session.save()
        return session

    @property
    def session_dir(self) -> Path:
        return self.sessions_root / self.session_id

    @property
    def audio_cache_dir(self) -> Path:
        """Where sessions written before 1.1 kept their synthesised question audio.

        Question audio now lives in one shared, content-addressed cache
        (`config.default_tts_cache_dir`) so it survives across sessions. The
        path is kept so an old session folder still reads correctly; new
        sessions no longer create it.
        """
        return self.session_dir / "audio_cache"

    @property
    def answers_dir(self) -> Path:
        return self.session_dir / "answers"

    @property
    def reports_dir(self) -> Path:
        return self.session_dir / "report"

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._created_monotonic

    def record_at(self, zero_based_index: int) -> QuestionRecord:
        return self.records[zero_based_index]

    def mark_tts_started(self, zero_based_index: int, language: str, speaker: str) -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            record.language = language
            record.speaker = speaker
            record.tts_started_at = now_iso()

    def mark_tts_finished(self, zero_based_index: int) -> None:
        with self._lock:
            self.record_at(zero_based_index).tts_finished_at = now_iso()

    def mark_tts_result(self, zero_based_index: int, backend: str, warning: str = "") -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            record.tts_backend = backend
            record.tts_warning = warning
            record.quality_degraded = bool(warning or backend == "windows-sapi")

    def increment_repeat(self, zero_based_index: int) -> None:
        with self._lock:
            self.record_at(zero_based_index).repeat_count += 1

    def start_answer(self, zero_based_index: int) -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            if record.answer_started_at:
                return
            record.answer_started_at = now_iso()
            record._answer_start_monotonic = time.monotonic()

    def finish_answer(self, zero_based_index: int) -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            if not record.answer_started_at or record.answer_finished_at:
                return
            record.answer_finished_at = now_iso()
            if record._answer_start_monotonic is not None:
                record.answer_seconds = time.monotonic() - record._answer_start_monotonic

    def set_memo(self, zero_based_index: int, memo: str) -> None:
        with self._lock:
            self.record_at(zero_based_index).memo = memo.strip()

    def set_answer_audio_path(self, zero_based_index: int, path: Path) -> None:
        with self._lock:
            self.record_at(zero_based_index).answer_audio_path = str(path)

    def set_transcript(self, zero_based_index: int, transcript: str) -> None:
        with self._lock:
            self.record_at(zero_based_index).transcript = transcript.strip()

    def set_follow_up_question(self, zero_based_index: int, question: str) -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            value = question.strip()
            if value == record.follow_up_question:
                return
            record.follow_up_question = value
            record.follow_up_generated_at = now_iso() if value else ""

    # -- analysis ------------------------------------------------------------

    def set_question_plan(self, zero_based_index: int, competency: str, stage: str) -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            record.competency = competency
            record.stage = stage

    def set_evaluation(self, zero_based_index: int, payload: dict[str, Any] | None) -> None:
        with self._lock:
            record = self.record_at(zero_based_index)
            record.evaluation = dict(payload) if payload else None
            if payload and not record.competency:
                record.competency = str(payload.get("competency", "") or "")

    def set_delivery(self, zero_based_index: int, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.record_at(zero_based_index).delivery = dict(payload) if payload else None

    def append_probe(self, zero_based_index: int, payload: dict[str, Any]) -> int:
        """Record a follow-up asked about this answer; returns the new depth."""
        with self._lock:
            record = self.record_at(zero_based_index)
            record.probes.append(dict(payload))
            question = str(payload.get("question", "")).strip()
            if question:
                # The latest probe is what the "follow-up" column means.
                record.follow_up_question = question
                record.follow_up_generated_at = now_iso()
            return len(record.probes)

    def probe_depth(self, zero_based_index: int) -> int:
        with self._lock:
            return self.record_at(zero_based_index).probe_depth

    def set_blueprint(self, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.blueprint = dict(payload) if payload else None
            if not payload:
                return
            self.interview_type = str(payload.get("interview_type", self.interview_type) or "")
            self.language = str(payload.get("language", self.language) or "")
            self.role = str(payload.get("role", self.role) or "")
            for index, planned in enumerate(payload.get("questions", []) or []):
                if index >= len(self.records) or not isinstance(planned, dict):
                    break
                record = self.records[index]
                record.competency = str(planned.get("competency", record.competency) or "")
                record.stage = str(planned.get("stage", record.stage) or "")

    def set_report(self, payload: dict[str, Any] | None) -> None:
        with self._lock:
            self.report = dict(payload) if payload else None

    def write_report_files(self, markdown: str = "", html: str = "", json_text: str = "") -> dict[str, Path]:
        """Persist rendered report formats next to the session data."""
        with self._lock:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            written: dict[str, Path] = {}
            for name, content in (
                ("report.md", markdown),
                ("report.html", html),
                ("report.json", json_text),
            ):
                if not content:
                    continue
                path = self.reports_dir / name
                temp_path = path.with_suffix(path.suffix + ".tmp")
                temp_path.write_text(content, encoding="utf-8")
                os.replace(temp_path, path)
                written[name] = path
            return written

    def export_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            return [record.export_row(self.session_id) for record in self.records]

    def save(self) -> None:
        with self._lock:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            self.answers_dir.mkdir(parents=True, exist_ok=True)
            rows = [record.export_row(self.session_id) for record in self.records]

            json_path = self.session_dir / "session.json"
            csv_path = self.session_dir / "session.csv"
            json_temp_path = json_path.with_suffix(".json.tmp")
            csv_temp_path = csv_path.with_suffix(".csv.tmp")

            payload = {
                "schema_version": SESSION_SCHEMA_VERSION,
                "session_id": self.session_id,
                "created_at": self.created_at,
                "interview_type": self.interview_type,
                "language": self.language,
                "role": self.role,
                "question_count": len(self.records),
                "blueprint": self.blueprint,
                "report": self.report,
                "records": [record.json_payload(self.session_id) for record in self.records],
            }
            json_temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(json_temp_path, json_path)

            with csv_temp_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=EXPORT_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(csv_temp_path, csv_path)
