from __future__ import annotations

import re
from dataclasses import dataclass


_LEADING_BULLET_RE = re.compile(r"^\s*(?:[-*+]|[>])\s+")

_NUMBER_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:Q(?:uestion)?\s*)?
    (?:
        \d{1,3}(?:[\.-]\d{1,3})*[\.\)\-:]\s+
        |
        \d{1,3}(?:[\.-]\d{1,3})+\s+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


@dataclass(frozen=True, slots=True)
class ParsedQuestion:
    raw: str
    clean: str


def clean_question_prefix(line: str) -> str:
    value = line.strip()
    value = _LEADING_BULLET_RE.sub("", value).strip()
    return _NUMBER_PREFIX_RE.sub("", value).strip()


def parse_questions(text: str) -> list[ParsedQuestion]:
    questions: list[ParsedQuestion] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        clean = clean_question_prefix(raw)
        if clean:
            questions.append(ParsedQuestion(raw=raw, clean=clean))
    return questions


def detect_language(text: str, default: str = "English") -> str:
    if _HANGUL_RE.search(text):
        return "Korean"
    return default
