from ai_interviewer.default_questions import (
    ENGLISH_MODE,
    KOREAN_MODE,
    default_question_set_name,
    question_set_names,
    questions_for_set,
    questions_text,
)


def test_question_sets_are_split_by_language() -> None:
    korean_questions = questions_for_set(KOREAN_MODE, default_question_set_name(KOREAN_MODE))
    english_questions = questions_for_set(ENGLISH_MODE, default_question_set_name(ENGLISH_MODE))

    assert len(korean_questions) == 20
    assert len(english_questions) == 20
    assert "자기소개" in korean_questions[0]
    assert "introduce yourself" in english_questions[0].lower()
    assert not any("Please " in question for question in korean_questions)
    assert not any("자기소개" in question for question in english_questions)


def test_question_set_names_and_text_are_numbered() -> None:
    assert "기본 인성 면접" in question_set_names(KOREAN_MODE)
    assert "Core HR Interview" in question_set_names(ENGLISH_MODE)
    assert questions_text(KOREAN_MODE).splitlines()[0].startswith("1. ")
    assert questions_text(ENGLISH_MODE).splitlines()[0].startswith("1. ")
