"""Bilingual interview content for the offline intelligence path.

Every Korean and English string the interviewer *says* or writes about an
answer lives here: probe questions, coaching notes, report headings, and the
keyword tables the offline analyzers use. Interview content follows the
interview language, not the UI language, so this is deliberately not i18n.py
(tests/test_i18n.py allows Korean literals in this file for that reason).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ai_interviewer.intelligence.rubric import ENGLISH, KOREAN


# -- gap taxonomy ------------------------------------------------------------

GAP_NO_SITUATION = "no_situation"
GAP_NO_ACTION = "no_action"
GAP_NO_RESULT = "no_result"
GAP_NO_METRIC = "no_metric"
GAP_NO_REASONING = "no_reasoning"
GAP_NO_ROLE = "no_role"
GAP_TOO_SHORT = "too_short"
GAP_TOO_GENERIC = "too_generic"
GAP_RAMBLING = "rambling"
GAP_OFF_TOPIC = "off_topic"

# Probe order matters: the first gap that applies is the one worth asking
# about. Missing context beats a missing metric, because a metric without a
# situation cannot be interpreted anyway.
GAP_PRIORITY: tuple[str, ...] = (
    GAP_OFF_TOPIC,
    GAP_TOO_SHORT,
    GAP_NO_SITUATION,
    GAP_NO_ACTION,
    GAP_NO_ROLE,
    GAP_NO_RESULT,
    GAP_NO_METRIC,
    GAP_NO_REASONING,
    GAP_TOO_GENERIC,
    GAP_RAMBLING,
)

GAP_KEYS: tuple[str, ...] = GAP_PRIORITY


_GAP_LABELS: Mapping[str, tuple[str, str]] = {
    GAP_NO_SITUATION: ("상황 설명 없음", "No situation given"),
    GAP_NO_ACTION: ("행동 설명 없음", "No actions described"),
    GAP_NO_RESULT: ("결과 없음", "No outcome stated"),
    GAP_NO_METRIC: ("수치 근거 없음", "No measurable evidence"),
    GAP_NO_REASONING: ("판단 근거 없음", "No reasoning shown"),
    GAP_NO_ROLE: ("본인 기여 불분명", "Own contribution unclear"),
    GAP_TOO_SHORT: ("답변이 너무 짧음", "Answer too short"),
    GAP_TOO_GENERIC: ("사례 없이 일반론", "Generic, no example"),
    GAP_RAMBLING: ("핵심이 흐려짐", "Point gets lost"),
    GAP_OFF_TOPIC: ("질문과 어긋남", "Drifts off the question"),
}


def gap_label(gap: str, language: str) -> str:
    ko, en = _GAP_LABELS.get(gap, (gap, gap))
    return ko if language == KOREAN else en


# -- probe questions ---------------------------------------------------------

# Several phrasings per gap so a second probe on the same gap does not repeat
# the first one word for word.
_PROBES_KO: Mapping[str, tuple[str, ...]] = {
    GAP_NO_SITUATION: (
        "그 일이 있었던 배경을 먼저 말씀해 주시겠어요? 어느 조직에서, 언제쯤 있었던 일인가요?",
        "말씀하신 상황이 어떤 조건에서 시작됐는지 조금 더 구체적으로 설명해 주시겠어요?",
    ),
    GAP_NO_ACTION: (
        "그 상황에서 본인이 직접 한 행동을 순서대로 말씀해 주시겠어요?",
        "가장 먼저 무엇을 하셨고, 그다음에는 무엇을 하셨나요?",
    ),
    GAP_NO_RESULT: (
        "그래서 최종적으로 어떻게 마무리됐나요?",
        "그 노력의 결과로 무엇이 달라졌는지 말씀해 주시겠어요?",
    ),
    GAP_NO_METRIC: (
        "말씀하신 개선을 수치로 표현하면 어느 정도였나요?",
        "그 결과를 어떤 지표로 확인하셨나요? 전후 숫자를 알 수 있을까요?",
    ),
    GAP_NO_REASONING: (
        "그 방법을 고르기 전에 검토했다가 버린 다른 안은 무엇이었고, 왜 버리셨나요?",
        "그 판단을 내릴 때 가장 중요하게 본 기준은 무엇이었나요?",
    ),
    GAP_NO_ROLE: (
        "지금 말씀은 팀 단위로 들리는데, 그중 본인이 직접 결정하고 실행한 부분은 어디까지였나요?",
        "그 일에서 본인의 역할과 다른 팀원의 역할을 구분해서 말씀해 주시겠어요?",
    ),
    GAP_TOO_SHORT: (
        "실제로 있었던 사례 하나를 들어 조금 더 구체적으로 설명해 주시겠어요?",
        "방금 답변을 뒷받침하는 경험을 하나만 자세히 풀어 주시겠어요?",
    ),
    GAP_TOO_GENERIC: (
        "일반적인 원칙 말고, 실제로 그렇게 하셨던 가장 최근 사례를 하나만 짚어 주시겠어요?",
        "그 생각을 실제 업무에서 적용해 본 구체적인 장면을 하나 말씀해 주시겠어요?",
    ),
    GAP_RAMBLING: (
        "지금 내용을 30초 안에 핵심만 다시 정리해 주시겠어요? 결론부터 말씀해 주시면 좋겠습니다.",
        "가장 중요한 한 가지만 남긴다면 무엇인가요?",
    ),
    GAP_OFF_TOPIC: (
        "제가 여쭤본 질문 기준으로 다시 답변해 주시겠어요?",
        "질문으로 돌아가서, 그 부분에 대한 본인의 경험을 말씀해 주시겠어요?",
    ),
}

_PROBES_EN: Mapping[str, tuple[str, ...]] = {
    GAP_NO_SITUATION: (
        "Could you set the scene first? Which team was this, and roughly when?",
        "What were the starting conditions when this came to you?",
    ),
    GAP_NO_ACTION: (
        "Walk me through what you personally did, step by step.",
        "What did you do first, and what came after that?",
    ),
    GAP_NO_RESULT: (
        "How did it end up?",
        "What was different afterwards because of that work?",
    ),
    GAP_NO_METRIC: (
        "If you put a number on that improvement, what was it?",
        "Which metric told you it worked? Do you recall the before and after?",
    ),
    GAP_NO_REASONING: (
        "What options did you consider and reject before choosing that, and why?",
        "What was the deciding factor in that call?",
    ),
    GAP_NO_ROLE: (
        "That sounds like team work. Where exactly did your own decisions and hands-on work stop?",
        "Could you separate your part from what your teammates did?",
    ),
    GAP_TOO_SHORT: (
        "Could you give me one concrete example and take me through it?",
        "Pick one experience that backs that up and tell me the detail.",
    ),
    GAP_TOO_GENERIC: (
        "Rather than the principle, give me the most recent time you actually did that.",
        "Describe one specific moment where you applied that at work.",
    ),
    GAP_RAMBLING: (
        "Could you give me that again in about thirty seconds, starting with the outcome?",
        "If only one point survived, which one would it be?",
    ),
    GAP_OFF_TOPIC: (
        "Could you answer against the question I asked?",
        "Coming back to the question, what is your own experience there?",
    ),
}


def probe_questions(gap: str, language: str) -> tuple[str, ...]:
    table = _PROBES_KO if language == KOREAN else _PROBES_EN
    return table.get(gap, table[GAP_TOO_SHORT])


def probe_question(gap: str, language: str, variant: int = 0) -> str:
    options = probe_questions(gap, language)
    return options[max(0, variant) % len(options)]


# Asked when the answer has no obvious gap but there is depth budget left.
_DEPTH_PROBES: Mapping[str, tuple[str, ...]] = {
    KOREAN: (
        "그 경험에서 가장 어려웠던 판단은 무엇이었고, 어떤 기준으로 결정하셨나요?",
        "같은 상황을 다시 맞는다면 무엇을 다르게 하시겠어요?",
        "그 일을 통해 본인의 일하는 방식에서 바뀐 점이 있나요?",
    ),
    ENGLISH: (
        "What was the hardest judgement call in that, and what decided it?",
        "If you met the same situation again, what would you do differently?",
        "Did that change how you work since?",
    ),
}


def depth_probe(language: str, variant: int = 0) -> str:
    options = _DEPTH_PROBES.get(language, _DEPTH_PROBES[ENGLISH])
    return options[max(0, variant) % len(options)]


_EMPTY_ANSWER: Mapping[str, str] = {
    KOREAN: "답변을 먼저 녹음하거나 입력해 주시면, 그 내용을 기준으로 더 구체적으로 질문드리겠습니다.",
    ENGLISH: "Record or type an answer first and I will follow up on what you said.",
}


def empty_answer_prompt(language: str) -> str:
    return _EMPTY_ANSWER.get(language, _EMPTY_ANSWER[ENGLISH])


# -- coaching notes ----------------------------------------------------------

_IMPROVEMENTS: Mapping[str, tuple[str, str]] = {
    GAP_NO_SITUATION: (
        "답변 첫 문장에 상황(어디서, 언제, 무슨 문제)을 한 줄로 깔아 주세요.",
        "Open with one line of context: where, when, what problem.",
    ),
    GAP_NO_ACTION: (
        "본인이 한 행동을 동사 중심으로 2~3단계로 나눠 말해 주세요.",
        "Break your own actions into two or three verb-led steps.",
    ),
    GAP_NO_RESULT: (
        "마지막에 결과 한 문장을 반드시 붙여 주세요. 결과 없는 경험은 평가하기 어렵습니다.",
        "Always close with the outcome; an experience without one cannot be assessed.",
    ),
    GAP_NO_METRIC: (
        "결과를 숫자로 바꿔 보세요. 비율, 기간, 건수 중 하나라도 있으면 신뢰도가 크게 올라갑니다.",
        "Turn the outcome into a number: a rate, a duration, or a count all work.",
    ),
    GAP_NO_REASONING: (
        "선택하지 않은 대안을 한 번 언급하면 판단력이 드러납니다.",
        "Naming one rejected alternative is what shows judgement.",
    ),
    GAP_NO_ROLE: (
        "'우리'를 '제가'로 바꿔 보세요. 본인 기여가 보이지 않으면 점수를 줄 수 없습니다.",
        "Swap 'we' for 'I'. An invisible contribution cannot be credited.",
    ),
    GAP_TOO_SHORT: (
        "핵심 경험 하나를 골라 60~90초 분량으로 풀어 주세요.",
        "Pick one experience and give it sixty to ninety seconds.",
    ),
    GAP_TOO_GENERIC: (
        "원칙 뒤에 실제 사례를 붙이세요. 사례 없는 원칙은 기억에 남지 않습니다.",
        "Attach a real example to the principle; principles alone do not stick.",
    ),
    GAP_RAMBLING: (
        "결론을 먼저 말하고 근거를 뒤에 붙이는 순서로 바꿔 보세요.",
        "Lead with the conclusion, then support it.",
    ),
    GAP_OFF_TOPIC: (
        "답변 시작 전에 질문의 핵심 단어를 한 번 되짚어 보세요.",
        "Echo the key word of the question before you answer.",
    ),
}


def improvement_note(gap: str, language: str) -> str:
    ko, en = _IMPROVEMENTS.get(gap, _IMPROVEMENTS[GAP_TOO_SHORT])
    return ko if language == KOREAN else en


_STRENGTHS: Mapping[str, tuple[str, str]] = {
    "structure": ("상황-행동-결과 흐름이 정리되어 있습니다.", "The situation-action-result arc is clear."),
    "evidence": ("구체적인 사실과 맥락이 충분히 담겼습니다.", "Concrete facts and context are there."),
    "impact": ("결과를 확인 가능한 형태로 제시했습니다.", "The outcome is stated in a checkable form."),
    "reasoning": ("판단 기준과 대안 비교가 드러납니다.", "The decision criteria and alternatives come through."),
    "relevance": ("질문의 의도에 정확히 답했습니다.", "It answers what was actually asked."),
    "delivery": ("말하기 속도와 문장 길이가 안정적입니다.", "Pace and sentence length are steady."),
}


def strength_note(dimension_key: str, language: str) -> str:
    ko, en = _STRENGTHS.get(dimension_key, _STRENGTHS["structure"])
    return ko if language == KOREAN else en


_PACE_LABELS: Mapping[str, tuple[str, str]] = {
    "slow": ("느린 편", "Slow"),
    "steady": ("안정적", "Steady"),
    "fast": ("빠른 편", "Fast"),
    "unknown": ("측정 불가", "Not measured"),
}


def pace_label(pace: str, language: str) -> str:
    ko, en = _PACE_LABELS.get(pace, _PACE_LABELS["unknown"])
    return ko if language == KOREAN else en


_DELIVERY_NOTES: Mapping[str, tuple[str, str]] = {
    "slow": ("말이 조금 느립니다. 문장을 짧게 끊으면 자연스럽게 빨라집니다.", "A little slow. Shorter sentences will pick up the pace."),
    "fast": ("말이 빠릅니다. 문장 사이에 반 박자 쉬면 전달력이 올라갑니다.", "You are speaking fast. Half a beat between sentences helps."),
    "filler": ("군더더기 표현이 잦습니다. 잠깐 멈추는 편이 더 안정적으로 들립니다.", "Filler words are frequent; a short pause reads better than a filler."),
    "long_sentence": ("한 문장이 너무 깁니다. 한 문장에 한 가지 내용만 담아 보세요.", "Sentences run long. Keep one idea per sentence."),
    "hedge": ("단정하지 않는 표현이 많습니다. 확인된 사실은 단정해서 말해 주세요.", "Lots of hedging. State the confirmed facts plainly."),
}


def delivery_note(key: str, language: str) -> str:
    ko, en = _DELIVERY_NOTES.get(key, _DELIVERY_NOTES["filler"])
    return ko if language == KOREAN else en


# -- report copy -------------------------------------------------------------

_REPORT_TEXT: Mapping[str, Mapping[str, str]] = {
    KOREAN: {
        "title": "면접 리포트",
        "overall": "종합 점수",
        "competency": "역량별 결과",
        "questions": "질문별 상세",
        "strengths": "강점",
        "focus": "보완 포인트",
        "actions": "다음 연습 과제",
        "dimensions": "평가 항목",
        "delivery": "전달력 요약",
        "no_data": "평가된 답변이 없습니다. 답변을 녹음하거나 입력한 뒤 평가를 실행해 주세요.",
        "not_answered": "미응답",
        "generated_by": "분석 엔진",
        "answered": "평가 답변",
        "wpm": "분당 어절",
        "filler": "군더더기 비율",
        "duration": "총 답변 시간",
    },
    ENGLISH: {
        "title": "Interview Report",
        "overall": "Overall score",
        "competency": "By competency",
        "questions": "Question detail",
        "strengths": "Strengths",
        "focus": "Focus areas",
        "actions": "Practice next",
        "dimensions": "Score dimensions",
        "delivery": "Delivery summary",
        "no_data": "Nothing scored yet. Record or type an answer, then run the analysis.",
        "not_answered": "Not answered",
        "generated_by": "Analysis engine",
        "answered": "Answers scored",
        "wpm": "Words per minute",
        "filler": "Filler rate",
        "duration": "Total answer time",
    },
}


def report_text(key: str, language: str) -> str:
    table = _REPORT_TEXT.get(language, _REPORT_TEXT[ENGLISH])
    return table.get(key, key)


_NEXT_ACTIONS: Mapping[str, tuple[str, str]] = {
    "structure": (
        "질문 3개를 골라 '상황 한 문장 → 행동 세 문장 → 결과 한 문장' 형식으로 다시 녹음해 보세요.",
        "Re-record three answers as one line of situation, three of action, one of result.",
    ),
    "evidence": (
        "경험 5개에 대해 조직, 기간, 본인 역할을 표로 정리해 두고 답변에 끼워 넣어 보세요.",
        "Tabulate team, timeframe, and your role for five experiences and weave them in.",
    ),
    "impact": (
        "각 경험의 결과를 숫자 하나로 요약해 보세요. 숫자가 없으면 전후 상태 비교라도 만들어 두세요.",
        "Reduce each experience to one number; if there is none, write a before-and-after.",
    ),
    "reasoning": (
        "주요 경험마다 '버린 대안 1개 + 버린 이유'를 미리 준비해 두세요.",
        "Prepare one rejected alternative and why, for each major experience.",
    ),
    "relevance": (
        "질문을 듣고 첫 문장에서 질문의 핵심 단어를 되짚는 연습을 해 보세요.",
        "Practise echoing the question's key word in your first sentence.",
    ),
    "delivery": (
        "60초 타이머를 켜고 답변을 녹음해 속도와 군더더기를 직접 들어 보세요.",
        "Record against a sixty-second timer and listen back for pace and filler.",
    ),
}


def next_action(dimension_key: str, language: str) -> str:
    ko, en = _NEXT_ACTIONS.get(dimension_key, _NEXT_ACTIONS["structure"])
    return ko if language == KOREAN else en


# -- summary templates -------------------------------------------------------

_ANSWER_SUMMARY: Mapping[str, tuple[str, str]] = {
    KOREAN: ("STAR 요소 {covered}/4 확인, 종합 {overall}점.", " 보완 필요: {gaps}"),
    ENGLISH: ("{covered}/4 STAR elements present, overall {overall}.", " To fix: {gaps}"),
}


def answer_summary(covered: int, overall: int, gaps: str, language: str) -> str:
    base, suffix = _ANSWER_SUMMARY.get(language, _ANSWER_SUMMARY[ENGLISH])
    text = base.format(covered=covered, overall=overall)
    return text + suffix.format(gaps=gaps) if gaps else text


_SESSION_SUMMARY: Mapping[str, str] = {
    KOREAN: "답변 {answered}/{total}개 평가, 종합 {overall}점({band}).",
    ENGLISH: "{answered} of {total} answers scored, overall {overall} ({band}).",
}


def session_summary(answered: int, total: int, overall: int, band: str, language: str) -> str:
    template = _SESSION_SUMMARY.get(language, _SESSION_SUMMARY[ENGLISH])
    return template.format(answered=answered, total=total, overall=overall, band=band)


# -- keyword tables ----------------------------------------------------------

# Offline competency tagging: first table whose keyword appears in the
# question wins, checked in COMPETENCY_TAG_ORDER.
COMPETENCY_TAG_ORDER: tuple[str, ...] = (
    "technical_depth",
    "collaboration",
    "learning",
    "role_fit",
    "integrity",
    "ownership",
    "communication",
    "problem_solving",
)

COMPETENCY_KEYWORDS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    KOREAN: {
        "technical_depth": ("기술", "설계", "아키텍처", "성능", "장애", "코드", "알고리즘", "배포", "테스트", "보안", "데이터"),
        "collaboration": ("갈등", "협업", "팀", "동료", "상사", "설득", "이해관계", "조율", "리더십"),
        "learning": ("배운", "학습", "피드백", "실패", "성장", "부족", "약점", "개선"),
        "role_fit": ("지원", "직무", "회사", "입사", "커리어", "포부", "3년", "6개월"),
        "integrity": ("윤리", "가치", "원칙", "책임", "신뢰", "규정"),
        "ownership": ("주도", "직접", "끝까지", "추진", "성과", "성취", "책임지고", "제안"),
        "communication": ("설명", "발표", "소개", "전달", "보고", "문서"),
        "problem_solving": ("문제", "해결", "판단", "우선순위", "결정", "대안", "리스크", "위기"),
    },
    ENGLISH: {
        "technical_depth": (
            "technical", "design", "architecture", "performance", "outage", "code",
            "algorithm", "deploy", "testing", "security", "data", "system",
        ),
        "collaboration": (
            "conflict", "collaborat", "team", "colleague", "manager", "persuad",
            "stakeholder", "align", "leadership", "influence",
        ),
        "learning": ("learn", "feedback", "failure", "failed", "growth", "weakness", "improve", "mistake"),
        "role_fit": ("apply", "role", "company", "position", "career", "join", "months", "years"),
        "integrity": ("ethic", "value", "principle", "responsib", "trust", "policy", "integrity"),
        "ownership": ("own", "drove", "drive", "initiative", "achievement", "impact", "led", "proposed"),
        "communication": ("explain", "present", "introduce", "communicat", "report", "document", "write"),
        "problem_solving": ("problem", "solve", "decision", "priorit", "tradeoff", "risk", "crisis", "judge"),
    },
}


def competency_keywords(language: str) -> Mapping[str, tuple[str, ...]]:
    return COMPETENCY_KEYWORDS.get(language, COMPETENCY_KEYWORDS[ENGLISH])


# STAR markers. Korean matching is substring-based because verb endings
# inflect; English is matched on lowercased substrings for the same reason.
STAR_MARKERS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    KOREAN: {
        "situation": (
            "당시", "상황", "배경", "때문에", "프로젝트", "회사에서", "팀에서", "무렵", "시절",
            "작년", "올해", "지난", "처음", "입사", "재직",
        ),
        "task": ("목표", "과제", "역할", "맡", "요구", "해야", "미션", "담당", "책임", "기한"),
        "action": (
            "제가", "저는", "했습니다", "했고", "진행", "설계", "제안", "설득", "정리", "구축",
            "도입", "분석", "조율", "만들었", "바꿨", "정했", "잡아", "작성", "공유",
        ),
        "result": (
            "결과", "덕분에", "줄였", "줄었", "늘렸", "늘었", "개선", "달성", "완료", "성공",
            "단축", "높였", "낮췄", "낮아", "절감", "감소", "증가", "해결", "출시", "안정화",
        ),
    },
    ENGLISH: {
        "situation": ("at the time", "context", "background", "project", "when i", "we had", "the team", "situation"),
        "task": ("goal", "task", "my role", "responsible", "needed to", "had to", "asked me", "owned"),
        "action": ("i ", "i designed", "i proposed", "i built", "i led", "i analysed", "i analyzed", "i negotiated", "i wrote"),
        "result": ("as a result", "result", "reduced", "increased", "improved", "achieved", "shipped", "cut ", "saved", "grew"),
    },
}


def star_markers(language: str) -> Mapping[str, tuple[str, ...]]:
    return STAR_MARKERS.get(language, STAR_MARKERS[ENGLISH])


REASONING_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("때문에", "이유는", "기준으로", "판단", "대신", "대안", "비교", "선택한", "우선", "트레이드오프", "고려"),
    ENGLISH: (
        "because", "the reason", "criteria", "instead of", "alternative", "compared",
        "tradeoff", "trade-off", "we chose", "i chose", "prioritis", "prioritiz", "considered",
    ),
}


def reasoning_markers(language: str) -> tuple[str, ...]:
    return REASONING_MARKERS.get(language, REASONING_MARKERS[ENGLISH])


GENERIC_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("항상", "늘", "보통", "대체로", "일반적으로", "최선을 다", "열심히", "노력하는 편", "성격입니다", "중요하다고 생각"),
    ENGLISH: (
        "always", "usually", "generally", "in general", "i try to", "i believe in",
        "hard worker", "team player", "i think it is important", "my philosophy",
    ),
}


def generic_markers(language: str) -> tuple[str, ...]:
    return GENERIC_MARKERS.get(language, GENERIC_MARKERS[ENGLISH])


COLLECTIVE_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("우리", "저희", "팀에서", "다들", "함께"),
    ENGLISH: ("we ", "we'", "our ", "the team ", "us "),
}

FIRST_PERSON_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("제가", "저는", "저의", "본인이", "직접"),
    ENGLISH: ("i ", "i'", "my ", "me "),
}


def collective_markers(language: str) -> tuple[str, ...]:
    return COLLECTIVE_MARKERS.get(language, COLLECTIVE_MARKERS[ENGLISH])


def first_person_markers(language: str) -> tuple[str, ...]:
    return FIRST_PERSON_MARKERS.get(language, FIRST_PERSON_MARKERS[ENGLISH])


# Fillers are matched as whole space-separated tokens, so common Korean
# particles ("그", "좀") do not fire on every word that contains them.
FILLER_TOKENS: Mapping[str, frozenset[str]] = {
    KOREAN: frozenset(
        {
            "음", "어", "아", "그", "저", "저기", "뭐", "뭐랄까", "약간", "좀", "이제",
            "그니까", "그러니까", "그래서요", "말하자면", "사실은", "일단은",
        }
    ),
    ENGLISH: frozenset(
        {
            "um", "umm", "uh", "uhh", "er", "ah", "like", "basically", "actually",
            "literally", "honestly", "right", "okay", "so",
        }
    ),
}

FILLER_PHRASES: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("그런 것 같아요", "뭐 이런", "어 그"),
    ENGLISH: ("you know", "sort of", "kind of", "i mean", "you see"),
}


def filler_tokens(language: str) -> frozenset[str]:
    return FILLER_TOKENS.get(language, FILLER_TOKENS[ENGLISH])


def filler_phrases(language: str) -> tuple[str, ...]:
    return FILLER_PHRASES.get(language, FILLER_PHRASES[ENGLISH])


HEDGE_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("같습니다", "같아요", "아마", "정도인", "듯합니다", "듯해요", "인 것 같", "잘 모르겠"),
    ENGLISH: ("i guess", "maybe", "probably", "i think maybe", "not sure", "kind of think", "somewhat"),
}


def hedge_markers(language: str) -> tuple[str, ...]:
    return HEDGE_MARKERS.get(language, HEDGE_MARKERS[ENGLISH])


# -- blueprint copy ----------------------------------------------------------

STAGE_OPENING = "opening"
STAGE_CORE = "core"
STAGE_DEEP_DIVE = "deep_dive"
STAGE_CLOSING = "closing"

STAGE_KEYS: tuple[str, ...] = (STAGE_OPENING, STAGE_CORE, STAGE_DEEP_DIVE, STAGE_CLOSING)

_STAGE_LABELS: Mapping[str, tuple[str, str]] = {
    STAGE_OPENING: ("도입", "Opening"),
    STAGE_CORE: ("핵심 질문", "Core"),
    STAGE_DEEP_DIVE: ("심층 검증", "Deep dive"),
    STAGE_CLOSING: ("마무리", "Closing"),
}


def stage_label(stage: str, language: str) -> str:
    ko, en = _STAGE_LABELS.get(stage, _STAGE_LABELS[STAGE_CORE])
    return ko if language == KOREAN else en


_OPENING_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("자기소개", "소개를", "간단히 소개"),
    ENGLISH: ("introduce yourself", "tell me about yourself", "walk me through your background"),
}

_CLOSING_MARKERS: Mapping[str, tuple[str, ...]] = {
    KOREAN: ("마지막으로", "질문 있으신가요", "하고 싶은 질문", "채용해야", "마지막 한 말씀"),
    ENGLISH: ("finally", "any questions", "anything you want to ask", "why should we hire"),
}


def opening_markers(language: str) -> tuple[str, ...]:
    return _OPENING_MARKERS.get(language, _OPENING_MARKERS[ENGLISH])


def closing_markers(language: str) -> tuple[str, ...]:
    return _CLOSING_MARKERS.get(language, _CLOSING_MARKERS[ENGLISH])


def contains_any(text: str, markers: Sequence[str]) -> bool:
    return any(marker in text for marker in markers)


# A measurement is a figure plus a unit. The unit alone is not evidence:
# every Korean unit here is also a substring of common words (분류, 초기,
# 건강, 명확), so the figure is what makes the match meaningful.
MEASUREMENT_PATTERN = (
    r"\d+\s*(?:%|퍼센트|배|억|만|천|건|명|개월|개|주|시간|분|초|점|원|회|일|년|초당|배로|bp|x)"
)

# Figures written without a unit still count, just for less.
NUMBER_PATTERN = r"\d+(?:[.,]\d+)*"

# Words a question uses to ask, not to specify; excluded from relevance overlap.
QUESTION_STOPWORDS: Mapping[str, frozenset[str]] = {
    KOREAN: frozenset(
        {
            "그리고",
            "그래서",
            "하지만",
            "경험을",
            "말씀해",
            "주세요",
            "해주세요",
            "주시겠어요",
            "대해",
            "무엇",
            "어느",
            "어떤",
            "어떻게",
            "있나요",
            "있으신가요",
            "설명해",
            "본인",
        }
    ),
    ENGLISH: frozenset(
        {
            "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
            "your", "you", "me", "about", "what", "how", "why", "tell", "describe",
            "please", "can", "could", "would", "give", "one", "that", "this", "it", "is",
            "are", "was", "were", "do", "did", "have", "has", "had",
        }
    ),
}


def question_stopwords(language: str) -> frozenset[str]:
    return QUESTION_STOPWORDS.get(language, QUESTION_STOPWORDS[ENGLISH])
