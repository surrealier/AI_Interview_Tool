from __future__ import annotations

import re
from pathlib import Path

import pytest

from ai_interviewer import i18n
from ai_interviewer.i18n import EN, KO, set_language, tr


PLACEHOLDER = re.compile(r"\{(\w+)\}")

# Files allowed to contain Korean literals: interview content (spoken text,
# question packs, probe and coaching templates, rubric labels), the catalog
# itself, and the dev-only theme gallery (its Korean samples exist to eyeball
# the Malgun Gothic fallback). "한국어" as a content-language name is also
# allowed anywhere. Interview content follows the *interview* language, which
# is independent of the UI language, so it cannot live in the tr() catalog.
ALLOWED_KOREAN_FILES = {
    "i18n.py",
    "default_questions.py",
    "followup.py",
    "qwen_provider.py",
    "dev_gallery.py",
    "phrasebook.py",
    "rubric.py",
}
ALLOWED_KOREAN_LITERALS = {"한국어", "Windows 기본 음성", "기본 인성 면접"}


@pytest.fixture(autouse=True)
def _restore_language():
    original = i18n.get_language()
    yield
    set_language(original)


def test_catalogs_have_identical_keys() -> None:
    assert set(KO) == set(EN)


def test_catalogs_have_no_empty_values() -> None:
    assert all(value.strip() for value in KO.values())
    assert all(value.strip() for value in EN.values())


def test_placeholders_match_between_languages() -> None:
    mismatched = [
        key
        for key in KO
        if set(PLACEHOLDER.findall(KO[key])) != set(PLACEHOLDER.findall(EN.get(key, "")))
    ]
    assert mismatched == []


def test_tr_switches_language() -> None:
    set_language("ko")
    assert tr("common.close") == "닫기"
    set_language("en")
    assert tr("common.close") == "Close"


def test_tr_falls_back_to_english_then_key() -> None:
    set_language("ko")
    assert tr("nonexistent.key") == "nonexistent.key"


def test_tr_formats_placeholders() -> None:
    set_language("en")
    assert "3.2 GB" in tr("wizard.model_not_installed", size="3.2 GB")


def test_no_stray_korean_literals_in_source() -> None:
    package_root = Path(i18n.__file__).parent
    korean = re.compile(r"[가-힣]+")
    offenders: list[str] = []
    for path in package_root.rglob("*.py"):
        if path.name in ALLOWED_KOREAN_FILES:
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found = korean.findall(line)
            if not found:
                continue
            remaining = [
                chunk
                for chunk in found
                if not any(chunk in allowed for allowed in ALLOWED_KOREAN_LITERALS)
            ]
            if remaining:
                offenders.append(f"{path.name}:{line_no}: {line.strip()[:80]}")
    assert offenders == []
