from __future__ import annotations

import pytest

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.delivery import analyze_delivery
from ai_interviewer.intelligence.evaluation import (
    analyze_answer,
    detect_gaps,
    evaluate_answer,
    heuristic_evaluation,
)
from ai_interviewer.intelligence.llm.base import LLMFailure, LLMReply, LLMRequest
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.rubric import DIMENSION_KEYS


STRONG_KO = (
    "작년에 결제 팀에서 배포 실패가 반복되는 상황이었습니다. 제가 먼저 실패 사례 40건을 모아 "
    "원인을 분류했고, 재현 가능성을 기준으로 체크리스트를 만들었습니다. 전면 자동화도 검토했지만 "
    "기간이 부족했기 때문에 단계적으로 접근했습니다. 그 결과 롤백이 월 3건에서 0건으로 줄었습니다."
)
WEAK_EN = "Problem solving. I always try my best and I am generally a hard worker."


class _FakeProvider:
    """Stands in for a model: returns a canned reply, or raises."""

    name = "fake"
    model = "fake-1"

    def __init__(self, payload: dict | None = None, *, fail: bool = False, available: bool = True):
        self.payload = payload
        self.fail = fail
        self.available = available
        self.requests: list[LLMRequest] = []

    def is_available(self) -> bool:
        return self.available

    def unavailable_reason(self) -> str:
        return "fake is switched off"

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        if self.fail:
            raise LLMFailure("fake provider exploded")
        return LLMReply(text="{}", provider=self.name, model=self.model, data=self.payload)


def _chain(provider) -> ProviderChain:
    return ProviderChain(providers=[provider])


# -- offline scoring ---------------------------------------------------------


def test_strong_korean_answer_outscores_a_generic_one() -> None:
    strong = evaluate_answer(
        "팀에서 갈등을 겪은 경험을 말씀해 주세요.", STRONG_KO, "Korean", duration_seconds=70
    )
    weak = evaluate_answer("What is your greatest strength?", WEAK_EN, "English", duration_seconds=12)

    assert strong.overall > weak.overall + 20
    assert strong.band in {"strong", "outstanding", "solid"}
    assert weak.band in {"insufficient", "developing"}


def test_every_dimension_is_scored_offline() -> None:
    evaluation = evaluate_answer("Tell me about a project.", STRONG_KO, "Korean", duration_seconds=70)
    assert {item.key for item in evaluation.dimensions} == set(DIMENSION_KEYS)
    assert all(0 <= item.score <= 100 for item in evaluation.dimensions)


def test_empty_answer_scores_zero_and_is_not_scored() -> None:
    evaluation = evaluate_answer("Tell me about a failure.", "   ", "English")
    assert evaluation.overall == 0
    assert evaluation.scored is False
    assert evaluation.gaps == (phrasebook.GAP_TOO_SHORT,)


def test_gap_detection_flags_the_missing_metric_only() -> None:
    answer = (
        "At the time our onboarding flow was dropping users. I mapped the funnel, "
        "I rewrote the two worst steps because the copy was misleading, and I shipped it. "
        "As a result completion improved and the team kept the new flow."
    )
    signals = analyze_answer("Describe an improvement you drove.", answer, "English", duration_seconds=60)
    assert phrasebook.GAP_NO_METRIC in signals.gaps
    assert phrasebook.GAP_NO_RESULT not in signals.gaps
    assert phrasebook.GAP_NO_ACTION not in signals.gaps


def test_collective_answer_without_first_person_flags_ownership() -> None:
    answer = (
        "We had a broken release process. We agreed on a checklist and we rolled it out "
        "to the whole team. We measured it afterwards and we were happy with the result, "
        "and the team kept using it for the next two quarters without changes."
    )
    gaps = detect_gaps(analyze_answer("Tell me about a team improvement.", answer, "English", duration_seconds=60))
    assert phrasebook.GAP_NO_ROLE in gaps


def test_heuristic_scoring_is_deterministic() -> None:
    signals = analyze_answer("Q?", STRONG_KO, "Korean", duration_seconds=70)
    first = heuristic_evaluation(signals, language="Korean")
    second = heuristic_evaluation(signals, language="Korean")
    assert first.score_map() == second.score_map()


def test_off_topic_answer_loses_relevance() -> None:
    on_topic = evaluate_answer(
        "Describe a conflict with a colleague.",
        "I had a conflict with a colleague about release scope. I set up a call, we agreed on "
        "a cut line, and the release shipped on the agreed date without further disputes.",
        "English",
        duration_seconds=45,
    )
    off_topic = evaluate_answer(
        "Describe a conflict with a colleague.",
        "My favourite programming language is Python because the syntax is readable and the "
        "ecosystem is large, so I use it for almost everything I build these days.",
        "English",
        duration_seconds=45,
    )
    assert on_topic.score_for("relevance") > off_topic.score_for("relevance")


# -- provider path -----------------------------------------------------------


def _verdict(**scores: int) -> dict:
    base = {"structure": 80, "evidence": 80, "impact": 80, "reasoning": 80, "relevance": 80}
    base.update(scores)
    return {
        "scores": base,
        "summary": "Model summary.",
        "strengths": ["Clear structure."],
        "improvements": ["Add a number."],
        "gaps": [phrasebook.GAP_NO_METRIC],
        "model_answer": ["Situation", "Action", "Result"],
    }


def test_provider_verdict_replaces_the_heuristic_scores() -> None:
    provider = _FakeProvider(_verdict(structure=95))
    evaluation = evaluate_answer(
        "Tell me about a project.",
        STRONG_KO,
        "Korean",
        chain=_chain(provider),
        duration_seconds=70,
    )
    assert evaluation.score_for("structure") == 95
    assert evaluation.summary == "Model summary."
    assert evaluation.model_answer == ("Situation", "Action", "Result")
    assert evaluation.degraded is False
    assert evaluation.engine == "fake:fake-1"


def test_delivery_is_measured_locally_not_taken_from_the_model() -> None:
    """A model cannot hear pace, so its delivery number must be ignored."""
    provider = _FakeProvider(_verdict())
    measured = analyze_delivery(STRONG_KO, 70, "Korean")
    evaluation = evaluate_answer(
        "Tell me about a project.",
        STRONG_KO,
        "Korean",
        chain=_chain(provider),
        duration_seconds=70,
    )
    assert evaluation.score_for("delivery") == measured.score
    # The prompt must not ask the model for a delivery score at all.
    assert "delivery" not in provider.requests[0].schema["properties"]["scores"]["properties"]


def test_provider_failure_falls_back_and_marks_degraded() -> None:
    evaluation = evaluate_answer(
        "Tell me about a project.",
        STRONG_KO,
        "Korean",
        chain=_chain(_FakeProvider(fail=True)),
        duration_seconds=70,
    )
    assert evaluation.degraded is True
    assert evaluation.engine == "offline"
    assert evaluation.overall > 0  # the offline verdict still stands


def test_unavailable_provider_is_skipped_without_degrading_the_score() -> None:
    chain = ProviderChain(providers=[_FakeProvider(available=False)])
    evaluation = evaluate_answer("Q?", STRONG_KO, "Korean", chain=chain, duration_seconds=70)
    assert evaluation.degraded is True
    assert "switched off" in evaluation.note


def test_garbage_verdict_is_rejected() -> None:
    provider = _FakeProvider({"summary": "no scores here"})
    evaluation = evaluate_answer("Q?", STRONG_KO, "Korean", chain=_chain(provider), duration_seconds=70)
    assert evaluation.degraded is True
    assert evaluation.engine == "offline"


@pytest.mark.parametrize("value", [-40, 0, 55, 100, 500])
def test_out_of_range_model_scores_are_clamped(value: int) -> None:
    provider = _FakeProvider(_verdict(structure=value))
    evaluation = evaluate_answer("Q?", STRONG_KO, "Korean", chain=_chain(provider), duration_seconds=70)
    assert 0 <= evaluation.score_for("structure") <= 100


def test_evaluation_round_trips_through_json() -> None:
    from ai_interviewer.intelligence.evaluation import AnswerEvaluation

    original = evaluate_answer("Q?", STRONG_KO, "Korean", duration_seconds=70)
    restored = AnswerEvaluation.from_dict(original.to_dict())
    assert restored.overall == original.overall
    assert restored.score_map() == original.score_map()
    assert restored.gaps == original.gaps
