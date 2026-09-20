"""Competency rubric: the scoring vocabulary the whole intelligence layer shares.

Everything that scores, probes, or reports speaks in these terms, so an LLM
verdict, a heuristic fallback, and the UI never disagree about what a number
means. Korean labels live here because they are interview *content*, not UI
chrome (see tests/test_i18n.py).
"""

from __future__ import annotations

from dataclasses import dataclass


KOREAN = "Korean"
ENGLISH = "English"


@dataclass(frozen=True, slots=True)
class Competency:
    """One thing the interview is trying to find out about the candidate."""

    key: str
    ko: str
    en: str
    ko_focus: str
    en_focus: str

    def label(self, language: str) -> str:
        return self.ko if language == KOREAN else self.en

    def focus(self, language: str) -> str:
        return self.ko_focus if language == KOREAN else self.en_focus


OWNERSHIP = Competency(
    key="ownership",
    ko="주도성·오너십",
    en="Ownership & Drive",
    ko_focus="스스로 문제를 정의하고 끝까지 책임지고 끌고 간 근거",
    en_focus="Evidence the candidate defined the problem and carried it to completion",
)
PROBLEM_SOLVING = Competency(
    key="problem_solving",
    ko="문제 해결력",
    en="Problem Solving",
    ko_focus="문제를 구조화한 방식, 대안 비교, 판단 근거",
    en_focus="How the problem was framed, alternatives weighed, and decisions justified",
)
COMMUNICATION = Competency(
    key="communication",
    ko="커뮤니케이션",
    en="Communication",
    ko_focus="핵심부터 말하는 구조, 듣는 사람 기준의 설명",
    en_focus="Leading with the point and explaining for the listener",
)
COLLABORATION = Competency(
    key="collaboration",
    ko="협업·영향력",
    en="Collaboration & Influence",
    ko_focus="이해관계가 다른 사람을 움직인 방법과 그 결과",
    en_focus="How other people were moved, and what came of it",
)
LEARNING = Competency(
    key="learning",
    ko="학습 민첩성",
    en="Learning Agility",
    ko_focus="피드백과 실패 이후 행동이 실제로 바뀐 증거",
    en_focus="Behaviour that visibly changed after feedback or failure",
)
ROLE_FIT = Competency(
    key="role_fit",
    ko="직무 적합성",
    en="Role Fit",
    ko_focus="직무가 요구하는 역량과 실제 경험의 연결",
    en_focus="The link between what the role needs and what the candidate has done",
)
TECHNICAL_DEPTH = Competency(
    key="technical_depth",
    ko="기술 전문성",
    en="Technical Depth",
    ko_focus="원리 수준의 이해와 트레이드오프 설명",
    en_focus="First-principles understanding and explicit tradeoffs",
)
INTEGRITY = Competency(
    key="integrity",
    ko="가치관·책임감",
    en="Values & Integrity",
    ko_focus="어려운 상황에서 선택의 기준으로 삼은 원칙",
    en_focus="The principle that decided a hard call",
)

COMPETENCIES: tuple[Competency, ...] = (
    OWNERSHIP,
    PROBLEM_SOLVING,
    COMMUNICATION,
    COLLABORATION,
    LEARNING,
    ROLE_FIT,
    TECHNICAL_DEPTH,
    INTEGRITY,
)

COMPETENCY_KEYS: tuple[str, ...] = tuple(item.key for item in COMPETENCIES)
_BY_KEY = {item.key: item for item in COMPETENCIES}

DEFAULT_COMPETENCY = PROBLEM_SOLVING


def competency(key: str) -> Competency:
    return _BY_KEY.get(key, DEFAULT_COMPETENCY)


def competency_label(key: str, language: str) -> str:
    return competency(key).label(language)


# -- score dimensions --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Dimension:
    """One axis of a single answer's score, 0-100."""

    key: str
    ko: str
    en: str
    weight: float
    ko_question: str
    en_question: str

    def label(self, language: str) -> str:
        return self.ko if language == KOREAN else self.en

    def prompt_question(self, language: str) -> str:
        return self.ko_question if language == KOREAN else self.en_question


DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        key="structure",
        ko="구조",
        en="Structure",
        weight=0.20,
        ko_question="상황-과제-행동-결과가 순서대로 드러나는가?",
        en_question="Do situation, task, action, and result appear in order?",
    ),
    Dimension(
        key="evidence",
        ko="구체성",
        en="Evidence",
        weight=0.22,
        ko_question="고유명사, 기간, 본인 역할처럼 검증 가능한 사실이 있는가?",
        en_question="Are there verifiable specifics: names, timeframes, the candidate's own role?",
    ),
    Dimension(
        key="impact",
        ko="임팩트",
        en="Impact",
        weight=0.20,
        ko_question="결과가 수치나 확인 가능한 변화로 제시되는가?",
        en_question="Is the outcome given as a number or a checkable change?",
    ),
    Dimension(
        key="reasoning",
        ko="판단 근거",
        en="Reasoning",
        weight=0.18,
        ko_question="다른 선택지를 왜 버렸는지 설명하는가?",
        en_question="Does the answer say why the alternatives were rejected?",
    ),
    Dimension(
        key="relevance",
        ko="질문 적합성",
        en="Relevance",
        weight=0.12,
        ko_question="질문이 물은 것에 답하는가?",
        en_question="Does it answer the question that was asked?",
    ),
    Dimension(
        key="delivery",
        ko="전달력",
        en="Delivery",
        weight=0.08,
        ko_question="속도, 군더더기, 문장 길이가 듣기 좋은가?",
        en_question="Are pace, filler, and sentence length easy to listen to?",
    ),
)

DIMENSION_KEYS: tuple[str, ...] = tuple(item.key for item in DIMENSIONS)
_DIMENSION_BY_KEY = {item.key: item for item in DIMENSIONS}


def dimension(key: str) -> Dimension:
    return _DIMENSION_BY_KEY.get(key, DIMENSIONS[0])


def dimension_label(key: str, language: str) -> str:
    return dimension(key).label(language)


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def weighted_overall(scores: dict[str, float]) -> int:
    """Blend dimension scores into one 0-100 number.

    Only the dimensions actually present are counted, so a pass that cannot
    judge (say) reasoning does not silently score it as zero.
    """
    total_weight = 0.0
    total = 0.0
    for item in DIMENSIONS:
        value = scores.get(item.key)
        if value is None:
            continue
        total += clamp_score(value) * item.weight
        total_weight += item.weight
    if total_weight <= 0:
        return 0
    return int(round(clamp_score(total / total_weight)))


# -- bands -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Band:
    key: str
    floor: int
    ko: str
    en: str

    def label(self, language: str) -> str:
        return self.ko if language == KOREAN else self.en


BANDS: tuple[Band, ...] = (
    Band(key="outstanding", floor=85, ko="탁월", en="Outstanding"),
    Band(key="strong", floor=70, ko="우수", en="Strong"),
    Band(key="solid", floor=55, ko="보통", en="Solid"),
    Band(key="developing", floor=40, ko="개선 필요", en="Developing"),
    Band(key="insufficient", floor=0, ko="근거 부족", en="Insufficient"),
)

BAND_KEYS: tuple[str, ...] = tuple(item.key for item in BANDS)
_BAND_BY_KEY = {item.key: item for item in BANDS}


def band_for_score(score: float) -> Band:
    value = clamp_score(score)
    for item in BANDS:
        if value >= item.floor:
            return item
    return BANDS[-1]


def band_key_for_score(score: float) -> str:
    return band_for_score(score).key


def band_label(key: str, language: str) -> str:
    found = _BAND_BY_KEY.get(key)
    return key if found is None else found.label(language)


# -- interview-type weighting ------------------------------------------------

# Which competencies an interview type is actually trying to measure. The
# blueprint uses these to order questions; the report uses them to weight the
# headline score, so a technical interview is not judged on HR competencies.
INTERVIEW_TYPE_COMPETENCIES: dict[str, tuple[str, ...]] = {
    "hr": (OWNERSHIP.key, COMMUNICATION.key, COLLABORATION.key, INTEGRITY.key, ROLE_FIT.key),
    "star": (OWNERSHIP.key, PROBLEM_SOLVING.key, COLLABORATION.key, LEARNING.key),
    "role": (ROLE_FIT.key, PROBLEM_SOLVING.key, OWNERSHIP.key, COMMUNICATION.key),
    "technical": (TECHNICAL_DEPTH.key, PROBLEM_SOLVING.key, COMMUNICATION.key, LEARNING.key),
}

DEFAULT_INTERVIEW_TYPE = "hr"


def competencies_for_interview_type(interview_type: str) -> tuple[str, ...]:
    return INTERVIEW_TYPE_COMPETENCIES.get(
        interview_type, INTERVIEW_TYPE_COMPETENCIES[DEFAULT_INTERVIEW_TYPE]
    )
