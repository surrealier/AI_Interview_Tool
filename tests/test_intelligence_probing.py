from __future__ import annotations

from ai_interviewer.intelligence import phrasebook
from ai_interviewer.intelligence.evaluation import AnswerEvaluation, DimensionScore, evaluate_answer
from ai_interviewer.intelligence.llm.base import LLMReply, LLMRequest
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.probing import (
    DEFAULT_MAX_DEPTH,
    REASON_DEPTH,
    REASON_DISABLED,
    REASON_EMPTY,
    REASON_GAP,
    REASON_MAX_DEPTH,
    REASON_STRONG,
    decide_probe,
    follow_up_for_answer,
    generate_probe,
)


def _evaluation(overall: int, gaps: tuple[str, ...] = ()) -> AnswerEvaluation:
    return AnswerEvaluation(
        overall=overall,
        gaps=gaps,
        dimensions=(DimensionScore(key="structure", score=overall),),
        language="English",
    )


class _FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, question: str = "And what did that cost you?"):
        self.question = question
        self.requests: list[LLMRequest] = []

    def is_available(self) -> bool:
        return True

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        return LLMReply(
            text="{}",
            provider=self.name,
            model=self.model,
            data={"question": self.question, "gap": phrasebook.GAP_NO_METRIC, "rationale": "no number"},
        )


# -- decisions ---------------------------------------------------------------


def test_a_gap_earns_a_probe_aimed_at_it() -> None:
    decision = decide_probe(_evaluation(60, (phrasebook.GAP_NO_METRIC,)))
    assert decision.should_probe is True
    assert decision.gap == phrasebook.GAP_NO_METRIC
    assert decision.reason == REASON_GAP
    assert decision.depth == 1


def test_gaps_are_probed_in_priority_order() -> None:
    gaps = (phrasebook.GAP_NO_SITUATION, phrasebook.GAP_NO_METRIC)
    assert decide_probe(_evaluation(50, gaps)).gap == phrasebook.GAP_NO_SITUATION


def test_a_strong_answer_with_no_gaps_ends_the_thread() -> None:
    decision = decide_probe(_evaluation(88))
    assert decision.should_probe is False
    assert decision.reason == REASON_STRONG


def test_a_mediocre_answer_with_no_named_gap_still_goes_deeper() -> None:
    decision = decide_probe(_evaluation(64))
    assert decision.should_probe is True
    assert decision.gap == ""
    assert decision.reason == REASON_DEPTH


def test_depth_cap_stops_the_thread() -> None:
    evaluation = _evaluation(40, (phrasebook.GAP_NO_METRIC,))
    assert decide_probe(evaluation, depth=0, max_depth=1).should_probe is True
    stopped = decide_probe(evaluation, depth=1, max_depth=1)
    assert stopped.should_probe is False
    assert stopped.reason == REASON_MAX_DEPTH


def test_zero_depth_disables_probing_entirely() -> None:
    decision = decide_probe(_evaluation(30, (phrasebook.GAP_NO_METRIC,)), depth=0, max_depth=0)
    assert decision.should_probe is False


def test_probing_can_be_switched_off() -> None:
    decision = decide_probe(_evaluation(10, (phrasebook.GAP_NO_METRIC,)), enabled=False)
    assert decision.should_probe is False
    assert decision.reason == REASON_DISABLED


def test_unscored_answer_is_not_probed() -> None:
    assert decide_probe(None).reason == REASON_EMPTY
    assert decide_probe(AnswerEvaluation()).reason == REASON_EMPTY


# -- generation --------------------------------------------------------------


def test_offline_probe_matches_the_gap() -> None:
    decision = decide_probe(_evaluation(50, (phrasebook.GAP_NO_METRIC,)))
    probe = generate_probe("Tell me about an improvement.", "We improved it a lot.", "English", decision=decision)
    assert probe.exists
    assert probe.gap == phrasebook.GAP_NO_METRIC
    assert probe.engine == "offline"
    assert "number" in probe.question.lower() or "metric" in probe.question.lower()


def test_a_second_probe_on_the_same_gap_is_worded_differently() -> None:
    first = generate_probe(
        "Q?", "answer", "Korean", decision=decide_probe(_evaluation(50, (phrasebook.GAP_NO_METRIC,)), depth=0)
    )
    second = generate_probe(
        "Q?", "answer", "Korean", decision=decide_probe(_evaluation(50, (phrasebook.GAP_NO_METRIC,)), depth=1)
    )
    assert first.question != second.question


def test_empty_answer_asks_for_an_answer_rather_than_probing() -> None:
    probe = generate_probe("Q?", "   ", "English")
    assert probe.exists
    assert probe.gap == phrasebook.GAP_TOO_SHORT


def test_provider_probe_is_used_and_normalized() -> None:
    provider = _FakeProvider("So what did that cost you")
    probe = generate_probe(
        "Q?",
        "We shipped it.",
        "English",
        decision=decide_probe(_evaluation(50, (phrasebook.GAP_NO_METRIC,))),
        chain=ProviderChain(providers=[provider]),
    )
    assert probe.question.endswith("?")  # normalize_question adds it
    assert probe.engine == "fake:fake-1"
    assert probe.rationale == "no number"
    # A probe is spoken to a waiting candidate, so it runs at low effort.
    assert provider.requests[0].effort == "low"


def test_probe_never_exceeds_the_supported_depth() -> None:
    decision = decide_probe(_evaluation(30, (phrasebook.GAP_NO_METRIC,)), depth=0, max_depth=99)
    assert decision.depth <= 4


def test_follow_up_for_answer_works_without_a_prior_evaluation() -> None:
    probe = follow_up_for_answer(
        "Describe a failure.",
        "We missed the deadline and then we fixed it and everyone moved on afterwards.",
        "English",
    )
    assert probe.exists
    assert probe.question.endswith("?")


def test_probe_round_trips_through_json() -> None:
    from ai_interviewer.intelligence.probing import Probe

    original = generate_probe(
        "Q?", "answer text", "English", decision=decide_probe(_evaluation(50, (phrasebook.GAP_NO_ROLE,)))
    )
    restored = Probe.from_dict(original.to_dict())
    assert restored.question == original.question
    assert restored.gap == original.gap
    assert restored.depth == original.depth


def test_real_evaluation_feeds_a_probe_end_to_end() -> None:
    answer = "We had a problem and we solved it together as a team and everyone was pleased with it."
    evaluation = evaluate_answer("Describe a problem you solved.", answer, "English", duration_seconds=20)
    decision = decide_probe(evaluation, depth=0, max_depth=DEFAULT_MAX_DEPTH)
    assert decision.should_probe is True
    probe = generate_probe("Describe a problem you solved.", answer, "English", decision=decision)
    assert probe.question
