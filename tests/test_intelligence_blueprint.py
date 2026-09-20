from __future__ import annotations

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.blueprint import (
    SOURCE_LLM,
    SOURCE_PACK,
    InterviewBlueprint,
    build_blueprint,
    generate_blueprint,
    tag_competency,
    tag_stage,
)
from ai_interviewer.intelligence.llm.base import LLMReply, LLMRequest
from ai_interviewer.intelligence.llm.registry import ProviderChain


KO_QUESTIONS = [
    "자기소개를 1분 이내로 해주세요.",
    "팀에서 갈등을 겪었던 경험을 말씀해 주세요.",
    "시스템 장애를 해결한 경험을 설명해 주세요.",
    "실패에서 배운 점은 무엇인가요?",
    "마지막으로 하실 말씀 있나요?",
]


class _FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, payload):
        self.payload = payload
        self.requests: list[LLMRequest] = []

    def is_available(self) -> bool:
        return True

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        return LLMReply(text="{}", provider=self.name, model=self.model, data=self.payload)


# -- offline tagging ---------------------------------------------------------


def test_competency_tagging_follows_the_wording() -> None:
    assert tag_competency("팀에서 갈등을 겪은 경험", "Korean") == "collaboration"
    assert tag_competency("시스템 장애를 해결한 경험", "Korean") == "technical_depth"
    assert tag_competency("Describe a conflict with a stakeholder", "English") == "collaboration"
    assert tag_competency("Walk me through your architecture decisions", "English") == "technical_depth"


def test_unrecognised_question_falls_back_to_the_interview_type_focus() -> None:
    assert tag_competency("...", "English", "technical") == "technical_depth"
    assert tag_competency("...", "English", "hr") == "ownership"


def test_opening_and_closing_questions_get_their_stages() -> None:
    assert tag_stage("자기소개를 해주세요.", "Korean", 3, 8) == phrasebook.STAGE_OPENING
    assert tag_stage("마지막으로 하실 말씀 있나요?", "Korean", 2, 8) == phrasebook.STAGE_CLOSING
    assert tag_stage("Tell me about yourself", "English", 4, 8) == phrasebook.STAGE_OPENING


def test_middle_questions_split_between_core_and_deep_dive() -> None:
    stages = {tag_stage(f"Question {index}?", "English", index, 10) for index in range(1, 9)}
    assert phrasebook.STAGE_CORE in stages
    assert phrasebook.STAGE_DEEP_DIVE in stages


def test_blueprint_preserves_question_order_and_text() -> None:
    blueprint = build_blueprint(KO_QUESTIONS, "Korean", "hr", role="백엔드 엔지니어")
    assert blueprint.question_texts() == tuple(KO_QUESTIONS)
    assert blueprint.question_count == 5
    assert blueprint.role == "백엔드 엔지니어"
    assert all(item.source == SOURCE_PACK for item in blueprint.questions)


def test_blueprint_reports_coverage_and_gaps() -> None:
    blueprint = build_blueprint(KO_QUESTIONS, "Korean", "hr")
    coverage = blueprint.coverage()
    assert coverage["collaboration"] >= 1
    # HR focuses on integrity too, and this pack never asks about it.
    assert "integrity" in blueprint.uncovered_focus()


def test_blueprint_budget_reflects_the_stages() -> None:
    blueprint = build_blueprint(KO_QUESTIONS, "Korean", "hr")
    assert blueprint.total_budget_seconds > 0
    assert sum(blueprint.stage_counts().values()) == blueprint.question_count


def test_blank_questions_are_dropped() -> None:
    blueprint = build_blueprint(["  ", "Real question?", ""], "English", "hr")
    assert blueprint.question_count == 1


def test_blueprint_round_trips_through_json() -> None:
    original = build_blueprint(KO_QUESTIONS, "Korean", "star", role="PM", seniority="senior")
    restored = InterviewBlueprint.from_dict(original.to_dict())
    assert restored.question_texts() == original.question_texts()
    assert restored.seniority == "senior"
    assert [item.competency for item in restored.questions] == [
        item.competency for item in original.questions
    ]


def test_invalid_seniority_is_normalized() -> None:
    assert build_blueprint([], "English", "hr", seniority="wizard").seniority == "mid"


# -- provider-authored plan --------------------------------------------------


def _plan(count: int = 4) -> dict:
    stages = [
        phrasebook.STAGE_OPENING,
        phrasebook.STAGE_CORE,
        phrasebook.STAGE_DEEP_DIVE,
        phrasebook.STAGE_CLOSING,
    ]
    return {
        "notes": "Two core questions, one deep dive.",
        "questions": [
            {
                "text": f"Generated question {index}?",
                "competency": "problem_solving",
                "stage": stages[index % len(stages)],
                "intent": "Listen for tradeoffs.",
            }
            for index in range(count)
        ],
    }


def test_generated_plan_replaces_the_pack() -> None:
    provider = _FakeProvider(_plan())
    blueprint = generate_blueprint(
        chain=ProviderChain(providers=[provider]),
        language="English",
        interview_type="role",
        role="Staff Engineer",
        job_description="Own the payments platform.",
        question_count=4,
        fallback_questions=KO_QUESTIONS,
    )
    assert blueprint.engine == "fake:fake-1"
    assert blueprint.question_count == 4
    assert all(item.source == SOURCE_LLM for item in blueprint.questions)
    assert blueprint.notes
    assert "Staff Engineer" in provider.requests[0].user
    assert "Own the payments platform." in provider.requests[0].user


def test_generated_plan_is_ordered_by_stage() -> None:
    blueprint = generate_blueprint(
        chain=ProviderChain(providers=[_FakeProvider(_plan(8))]),
        language="English",
        question_count=8,
        fallback_questions=KO_QUESTIONS,
    )
    order = [phrasebook.STAGE_KEYS.index(item.stage) for item in blueprint.questions]
    assert order == sorted(order)


def test_no_provider_falls_back_to_the_pack() -> None:
    blueprint = generate_blueprint(
        chain=None,
        language="Korean",
        interview_type="hr",
        fallback_questions=KO_QUESTIONS,
    )
    assert blueprint.question_texts() == tuple(KO_QUESTIONS)
    assert blueprint.engine == "offline"


def test_unusable_plan_falls_back_to_the_pack() -> None:
    blueprint = generate_blueprint(
        chain=ProviderChain(providers=[_FakeProvider({"notes": "", "questions": []})]),
        language="Korean",
        fallback_questions=KO_QUESTIONS,
    )
    assert blueprint.question_texts() == tuple(KO_QUESTIONS)


def test_unknown_competency_from_a_model_is_replaced() -> None:
    payload = {
        "notes": "",
        "questions": [
            {"text": "Q?", "competency": "vibes", "stage": "core", "intent": ""},
        ],
    }
    blueprint = generate_blueprint(
        chain=ProviderChain(providers=[_FakeProvider(payload)]),
        language="English",
        fallback_questions=["fallback?"],
    )
    from ai_interviewer.intelligence.rubric import COMPETENCY_KEYS

    assert blueprint.questions[0].competency in COMPETENCY_KEYS
