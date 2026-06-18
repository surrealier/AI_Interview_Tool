from ai_interviewer.followup import generate_follow_up_question


def test_generate_korean_follow_up_for_project_answer(monkeypatch) -> None:
    monkeypatch.delenv("AI_INTERVIEW_OLLAMA_MODEL", raising=False)

    follow_up = generate_follow_up_question(
        "가장 자신 있는 프로젝트를 설명해 주세요.",
        "저는 결제 프로젝트에서 장애율을 낮추고 배포 프로세스를 개선해서 성과를 만들었습니다.",
        "Korean",
    )

    assert "기여" in follow_up
    assert follow_up.endswith("요?")


def test_generate_english_follow_up_for_short_answer(monkeypatch) -> None:
    monkeypatch.delenv("AI_INTERVIEW_OLLAMA_MODEL", raising=False)

    follow_up = generate_follow_up_question(
        "What is your greatest strength?",
        "Problem solving.",
        "English",
    )

    assert "measurable outcome" in follow_up
    assert follow_up.endswith("?")
