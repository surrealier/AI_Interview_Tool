from ai_interviewer.followup import generate_follow_up_question


def test_korean_follow_up_targets_the_missing_metric(monkeypatch) -> None:
    """A complete story with no number gets asked for the number."""
    monkeypatch.delenv("AI_INTERVIEW_OLLAMA_MODEL", raising=False)

    follow_up = generate_follow_up_question(
        "가장 자신 있는 프로젝트를 설명해 주세요.",
        "작년에 결제 팀에서 배포 프로세스를 개선하는 일을 맡았습니다. 당시 릴리즈마다 수동 확인 "
        "단계가 많아서 실패가 반복됐고, 저는 먼저 실패 사례를 모아 원인을 정리했습니다. 그다음 "
        "재현 가능성을 기준으로 체크리스트를 만들었고, QA 리드와 합의해서 릴리즈 전 필수 항목으로 "
        "넣었습니다. 대안으로 전면 자동화도 검토했지만 기간이 부족했기 때문에 단계적으로 "
        "접근했습니다. 그 결과 릴리즈 실패가 눈에 띄게 줄었습니다.",
        "Korean",
    )

    assert "수치" in follow_up or "지표" in follow_up
    assert follow_up.endswith("?")


def test_english_follow_up_asks_a_short_answer_to_go_concrete(monkeypatch) -> None:
    monkeypatch.delenv("AI_INTERVIEW_OLLAMA_MODEL", raising=False)

    follow_up = generate_follow_up_question(
        "What is your greatest strength?",
        "Problem solving.",
        "English",
    )

    assert "example" in follow_up.lower()
    assert follow_up.endswith("?")


def test_empty_answer_asks_for_an_answer_first(monkeypatch) -> None:
    monkeypatch.delenv("AI_INTERVIEW_OLLAMA_MODEL", raising=False)

    follow_up = generate_follow_up_question("Tell me about a failure.", "   ", "English")

    assert "record" in follow_up.lower() or "type" in follow_up.lower()


def test_follow_up_is_deterministic_without_a_provider(monkeypatch) -> None:
    """Offline mode must be reproducible: same answer, same probe."""
    monkeypatch.delenv("AI_INTERVIEW_OLLAMA_MODEL", raising=False)

    args = ("Describe a conflict you handled.", "We disagreed and then we shipped it.", "English")
    assert generate_follow_up_question(*args) == generate_follow_up_question(*args)
