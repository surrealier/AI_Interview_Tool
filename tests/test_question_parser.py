from ai_interviewer.question_parser import clean_question_prefix, detect_language, parse_questions


def test_clean_question_prefix_number_forms() -> None:
    assert clean_question_prefix("1. 자기소개를 해주세요.") == "자기소개를 해주세요."
    assert clean_question_prefix("1) 자기소개를 해주세요.") == "자기소개를 해주세요."
    assert clean_question_prefix("1.2. 프로젝트 설명") == "프로젝트 설명"
    assert clean_question_prefix("2-1. 꼬리 질문") == "꼬리 질문"
    assert clean_question_prefix("01- 프로젝트 설명") == "프로젝트 설명"
    assert clean_question_prefix("Q1. What is your strength?") == "What is your strength?"


def test_does_not_strip_decimal_content() -> None:
    assert clean_question_prefix("3.14는 무엇인가요?") == "3.14는 무엇인가요?"


def test_parse_questions_skips_blank_lines() -> None:
    questions = parse_questions("\n1. 첫 질문\n\n2. Second question\n")
    assert [question.clean for question in questions] == ["첫 질문", "Second question"]


def test_detect_language() -> None:
    assert detect_language("자기소개를 해주세요.") == "Korean"
    assert detect_language("Tell me about yourself.") == "English"
