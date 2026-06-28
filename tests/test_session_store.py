import csv
import json

from ai_interviewer.question_parser import parse_questions
from ai_interviewer.session_store import InterviewSession


def test_session_saves_csv_and_json(tmp_path) -> None:
    questions = parse_questions("1. 자기소개\n2. Strength?")
    session = InterviewSession.create(questions, tmp_path)

    session.mark_tts_started(0, language="Korean", speaker="Sohee")
    session.mark_tts_result(0, backend="windows-sapi", warning="fallback")
    session.mark_tts_finished(0)
    session.start_answer(0)
    session.finish_answer(0)
    audio_path = session.answers_dir / "answer_001.wav"
    session.set_answer_audio_path(0, audio_path)
    session.set_transcript(0, "프로젝트에서 일정 리스크를 줄였습니다.")
    session.set_follow_up_question(0, "그 결과를 어떻게 측정했나요?")
    session.set_memo(0, "메모")
    session.save()

    json_path = session.session_dir / "session.json"
    csv_path = session.session_dir / "session.csv"

    assert json_path.exists()
    assert csv_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["session_id"] == session.session_id
    assert payload["records"][0]["memo"] == "메모"
    assert payload["records"][0]["tts_backend"] == "windows-sapi"
    assert payload["records"][0]["tts_warning"] == "fallback"
    assert payload["records"][0]["quality_degraded"] is True
    assert payload["records"][0]["answer_audio_path"] == str(audio_path)
    assert payload["records"][0]["transcript"] == "프로젝트에서 일정 리스크를 줄였습니다."
    assert payload["records"][0]["follow_up_question"] == "그 결과를 어떻게 측정했나요?"
    assert payload["records"][0]["follow_up_generated_at"]

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["clean_question"] == "자기소개"
    assert rows[0]["language"] == "Korean"
    assert rows[0]["speaker"] == "Sohee"
    assert rows[0]["tts_backend"] == "windows-sapi"
    assert rows[0]["quality_degraded"] == "True"
    assert rows[0]["transcript"] == "프로젝트에서 일정 리스크를 줄였습니다."
