from __future__ import annotations

import json

from ai_interviewer.engine import InterviewEngine
from ai_interviewer.intelligence import analyze_answer_turn, build_blueprint
from ai_interviewer.intelligence.report import SessionReport
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.session_store import SESSION_SCHEMA_VERSION


QUESTIONS = (
    "1. 자기소개를 해주세요.\n"
    "2. 팀에서 갈등을 겪었던 경험을 말씀해 주세요.\n"
    "3. 시스템 장애를 해결한 경험을 설명해 주세요.\n"
    "4. 마지막으로 하실 말씀 있나요?"
)
ANSWER = (
    "작년에 결제 팀에서 QA와 릴리즈 일정으로 갈등이 있었습니다. 제가 먼저 QA 리드와 미팅을 잡아 "
    "기준을 정리했고, 릴리즈 체크리스트를 도입했습니다. 전면 자동화도 검토했지만 기간이 부족했기 "
    "때문에 단계적으로 접근했습니다. 그 결과 롤백이 월 3건에서 0건으로 줄었습니다."
)


def _engine(tmp_path) -> InterviewEngine:
    return InterviewEngine(
        parse_questions(QUESTIONS),
        tmp_path,
        interview_type="hr",
        language="Korean",
        role="백엔드 엔지니어",
    )


def test_engine_builds_a_blueprint_for_the_questions(tmp_path) -> None:
    engine = _engine(tmp_path)
    assert engine.blueprint.question_count == 4
    assert engine.current_stage == "opening"
    assert engine.current_competency
    assert engine.blueprint.role == "백엔드 엔지니어"


def test_blueprint_is_persisted_with_the_session(tmp_path) -> None:
    engine = _engine(tmp_path)
    payload = json.loads((engine.session.session_dir / "session.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == SESSION_SCHEMA_VERSION
    assert payload["blueprint"]["interview_type"] == "hr"
    assert len(payload["blueprint"]["questions"]) == 4
    assert payload["records"][0]["competency"]
    assert payload["records"][0]["stage"] == "opening"


def test_attaching_a_plan_retags_the_records(tmp_path) -> None:
    engine = _engine(tmp_path)
    technical = build_blueprint(
        [question.clean for question in engine.questions], "Korean", "technical"
    )
    engine.attach_blueprint(technical)
    assert engine.blueprint is technical
    assert engine.session.records[0].competency == technical.questions[0].competency


def test_recorded_insight_lands_in_the_session_files(tmp_path) -> None:
    engine = _engine(tmp_path)
    engine.current_index = 1
    engine.session.set_transcript(1, ANSWER)
    insight = analyze_answer_turn(
        engine.current_record.clean_question,
        ANSWER,
        "Korean",
        competency_key=engine.competency_for(1),
        question_index=2,
        duration_seconds=70,
    )
    engine.record_insight(insight)

    record = engine.session.records[1]
    assert record.evaluation is not None
    assert record.delivery is not None
    assert record.answer_score == insight.evaluation.overall
    assert record.answer_band == insight.evaluation.band

    payload = json.loads((engine.session.session_dir / "session.json").read_text(encoding="utf-8"))
    stored = payload["records"][1]
    assert stored["evaluation"]["overall"] == insight.evaluation.overall
    assert stored["delivery"]["word_count"] > 0
    assert stored["answer_score"] == insight.evaluation.overall


def test_probe_depth_grows_and_caps_the_thread(tmp_path) -> None:
    engine = _engine(tmp_path)
    assert engine.probe_depth() == 0
    engine.session.append_probe(0, {"question": "And the number?", "depth": 1})
    assert engine.probe_depth(0) == 1
    assert engine.session.records[0].follow_up_question == "And the number?"


def test_coverage_counts_scored_competencies(tmp_path) -> None:
    engine = _engine(tmp_path)
    assert all(count == 0 for count in engine.coverage().values())

    engine.session.set_transcript(1, ANSWER)
    insight = analyze_answer_turn(
        engine.session.records[1].clean_question,
        ANSWER,
        "Korean",
        competency_key=engine.competency_for(1),
        duration_seconds=70,
    )
    engine.record_insight(insight, index=1)
    assert sum(engine.coverage().values()) == 1
    assert engine.scored_count() == 1
    assert engine.answered_count() == 1


def test_report_is_built_and_saved_with_the_session(tmp_path) -> None:
    engine = _engine(tmp_path)
    engine.session.set_transcript(1, ANSWER)
    insight = analyze_answer_turn(
        engine.session.records[1].clean_question,
        ANSWER,
        "Korean",
        competency_key=engine.competency_for(1),
        duration_seconds=70,
    )
    engine.record_insight(insight, index=1)

    report = engine.build_report()
    assert report.answered_count == 1
    assert report.question_count == 4
    assert report.overall > 0
    assert report.language == "Korean"

    payload = json.loads((engine.session.session_dir / "session.json").read_text(encoding="utf-8"))
    restored = SessionReport.from_dict(payload["report"])
    assert restored.overall == report.overall
    assert len(restored.items) == 4


def test_report_files_are_written_into_the_session(tmp_path) -> None:
    from ai_interviewer.intelligence import render_html, render_markdown

    engine = _engine(tmp_path)
    report = engine.build_report()
    written = engine.session.write_report_files(
        markdown=render_markdown(report), html=render_html(report)
    )
    assert set(written) == {"report.md", "report.html"}
    assert all(path.exists() for path in written.values())
    assert written["report.md"].parent == engine.session.reports_dir


def test_restart_keeps_the_plan_but_starts_a_new_session(tmp_path) -> None:
    engine = _engine(tmp_path)
    first_id = engine.session.session_id
    engine.session.set_transcript(0, "something")
    engine.restart()
    assert engine.session.session_id != first_id
    assert engine.current_index == 0
    assert engine.session.blueprint is not None
    assert engine.session.records[0].transcript == ""


def test_csv_export_carries_the_analysis_columns(tmp_path) -> None:
    import csv

    engine = _engine(tmp_path)
    engine.session.set_transcript(1, ANSWER)
    insight = analyze_answer_turn(
        engine.session.records[1].clean_question,
        ANSWER,
        "Korean",
        competency_key=engine.competency_for(1),
        duration_seconds=70,
    )
    engine.record_insight(insight, index=1)

    with (engine.session.session_dir / "session.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[1]["answer_score"] == str(insight.evaluation.overall)
    assert rows[1]["competency"]
    assert rows[1]["analysis_engine"] == "offline"
    assert float(rows[1]["words_per_minute"]) > 0
