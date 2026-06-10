import csv
import json

from ai_interviewer.question_parser import parse_questions
from ai_interviewer.session_store import InterviewSession


def test_session_saves_csv_and_json(tmp_path) -> None:
    questions = parse_questions("1. 자기소개\n2. Strength?")
    session = InterviewSession.create(questions, tmp_path)

    session.mark_tts_started(0, language="Korean", speaker="Sohee")
    session.mark_tts_finished(0)
    session.start_answer(0)
    session.finish_answer(0)
    session.set_memo(0, "메모")
    session.save()

    json_path = session.session_dir / "session.json"
    csv_path = session.session_dir / "session.csv"

    assert json_path.exists()
    assert csv_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["session_id"] == session.session_id
    assert payload["records"][0]["memo"] == "메모"

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["clean_question"] == "자기소개"
    assert rows[0]["language"] == "Korean"
    assert rows[0]["speaker"] == "Sohee"
