from __future__ import annotations

from ai_interviewer.intelligence.delivery import analyze_delivery
from ai_interviewer.intelligence.evaluation import evaluate_answer
from ai_interviewer.intelligence.llm.base import LLMReply, LLMRequest
from ai_interviewer.intelligence.llm.registry import ProviderChain
from ai_interviewer.intelligence.report import (
    ReportItem,
    SessionReport,
    build_report,
    render_html,
    render_json,
    render_markdown,
)


STRONG = (
    "Last year our deploy pipeline failed most weeks. I collected 40 failures, grouped the causes, "
    "and because reproducibility mattered more than coverage I built a release checklist instead of "
    "full automation. Rollbacks went from 3 a month to 0."
)
WEAK = "We did well and everyone was happy about it in the end."


def _item(index: int, question: str, answer: str, competency: str, seconds: float = 60.0) -> ReportItem:
    delivery = analyze_delivery(answer, seconds, "English")
    evaluation = evaluate_answer(
        question, answer, "English", competency_key=competency, delivery=delivery, question_index=index
    )
    return ReportItem(
        question_index=index,
        question=question,
        competency=competency,
        transcript=answer,
        evaluation=evaluation,
        delivery=delivery,
        answer_seconds=seconds,
    )


def _items() -> list[ReportItem]:
    return [
        _item(1, "Describe an improvement you drove.", STRONG, "ownership"),
        _item(2, "Tell me about a team conflict.", WEAK, "collaboration", 15),
        ReportItem(question_index=3, question="Any questions for us?", competency="role_fit"),
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


# -- aggregation -------------------------------------------------------------


def test_report_counts_only_answered_questions() -> None:
    report = build_report(_items(), session_id="s1", language="English", interview_type="hr")
    assert report.question_count == 3
    assert report.answered_count == 2
    assert report.has_data is True


def test_empty_session_produces_a_report_that_says_so() -> None:
    report = build_report([], session_id="s1", language="English")
    assert report.has_data is False
    assert report.overall == 0
    assert report.summary


def test_unanswered_questions_do_not_drag_the_score_to_zero() -> None:
    only_strong = [_item(1, "Q?", STRONG, "ownership")]
    with_blank = only_strong + [ReportItem(question_index=2, question="Q2?", competency="role_fit")]
    assert build_report(with_blank).overall == build_report(only_strong).overall


def test_competency_scores_average_their_answers() -> None:
    report = build_report(_items(), interview_type="hr")
    by_key = {item.key: item for item in report.competencies}
    assert by_key["ownership"].score > by_key["collaboration"].score
    assert by_key["ownership"].answered == 1


def test_focus_competencies_are_weighted_above_incidental_ones() -> None:
    """A technical interview should not be dominated by an HR competency."""
    items = [
        _item(1, "Walk me through a design decision.", STRONG, "technical_depth"),
        _item(2, "Tell me about a conflict.", WEAK, "collaboration", 15),
    ]
    technical = build_report(items, interview_type="technical").overall
    hr = build_report(items, interview_type="hr").overall
    assert technical > hr


def test_dimension_averages_cover_every_scored_dimension() -> None:
    report = build_report(_items())
    assert {item.key for item in report.dimensions} >= {"structure", "evidence", "impact"}
    assert all(0 <= item.score <= 100 for item in report.dimensions)


def test_focus_areas_name_the_repeated_gaps() -> None:
    report = build_report(_items(), language="English")
    assert report.focus_areas
    assert report.next_actions


def test_delivery_is_rolled_up_across_answers() -> None:
    report = build_report(_items())
    assert report.delivery.measured is True
    assert report.delivery.word_count > 0


# -- narrative ---------------------------------------------------------------


def test_provider_writes_the_narrative_but_not_the_numbers() -> None:
    offline = build_report(_items(), interview_type="hr")
    payload = {
        "summary": "Model narrative.",
        "strengths": ["Owns outcomes."],
        "focus_areas": ["Quantify team work."],
        "next_actions": ["Rehearse the conflict story with numbers."],
    }
    provider = _FakeProvider(payload)
    report = build_report(
        _items(), interview_type="hr", chain=ProviderChain(providers=[provider])
    )
    assert report.summary == "Model narrative."
    assert report.strengths == ("Owns outcomes.",)
    assert report.engine == "fake:fake-1"
    assert report.degraded is False
    # The computed score is untouched by the narrative pass.
    assert report.overall == offline.overall
    assert [item.score for item in report.competencies] == [item.score for item in offline.competencies]


def test_narrative_failure_keeps_the_offline_text_and_marks_degraded() -> None:
    class _Failing(_FakeProvider):
        def complete(self, request: LLMRequest) -> LLMReply:
            return LLMReply(text="not json", provider=self.name, model=self.model, data=None)

    report = build_report(_items(), chain=ProviderChain(providers=[_Failing(None)]))
    assert report.degraded is True
    assert report.summary


# -- rendering ---------------------------------------------------------------


def test_markdown_render_includes_the_headline_and_every_question() -> None:
    report = build_report(_items(), session_id="s1", language="English", interview_type="hr")
    text = render_markdown(report)
    assert "# Interview Report" in text
    assert f"**{report.overall} / 100**" in text
    assert "Describe an improvement you drove." in text
    assert "Any questions for us?" in text
    assert "Not answered" in text


def test_html_render_is_a_standalone_document() -> None:
    report = build_report(_items(), session_id="s1", language="English")
    html = render_html(report)
    assert html.startswith("<!doctype html>")
    assert html.count("<html") == 1 and html.count("</html>") == 1
    assert "prefers-color-scheme: dark" in html
    assert str(report.overall) in html


def test_html_render_escapes_question_text() -> None:
    item = _item(1, "<script>alert(1)</script>", STRONG, "ownership")
    html = render_html(build_report([item], language="English"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_korean_report_renders_korean_headings() -> None:
    delivery = analyze_delivery("작년에 롤백을 3건에서 0건으로 줄였습니다.", 40, "Korean")
    evaluation = evaluate_answer(
        "개선 경험을 말씀해 주세요.",
        "작년에 롤백을 3건에서 0건으로 줄였습니다.",
        "Korean",
        competency_key="ownership",
        delivery=delivery,
    )
    item = ReportItem(
        question_index=1,
        question="개선 경험을 말씀해 주세요.",
        competency="ownership",
        transcript="작년에 롤백을 3건에서 0건으로 줄였습니다.",
        evaluation=evaluation,
        delivery=delivery,
    )
    text = render_markdown(build_report([item], language="Korean"))
    assert "면접 리포트" in text
    assert "역량별 결과" in text


def test_report_round_trips_through_json() -> None:
    original = build_report(_items(), session_id="s1", language="English", interview_type="hr")
    restored = SessionReport.from_dict(original.to_dict())
    assert restored.overall == original.overall
    assert restored.answered_count == original.answered_count
    assert len(restored.items) == len(original.items)
    assert [item.key for item in restored.competencies] == [item.key for item in original.competencies]
    assert render_json(original)
