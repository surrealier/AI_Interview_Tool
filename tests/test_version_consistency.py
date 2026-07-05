import re
from pathlib import Path

from ai_interviewer import __version__
from ai_interviewer.release_check import display_version

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_version_is_pep440_like() -> None:
    assert re.match(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$", __version__)


def test_display_version_mapping() -> None:
    assert display_version("0.9.0b0") == "v0.9.0-beta"
    assert display_version("1.0.0rc1") == "v1.0.0-rc1"
    assert display_version("1.0.0") == "v1.0.0"


def test_pyproject_uses_dynamic_version() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject
    assert "ai_interviewer.__version__" in pyproject
    # No second hardcoded project version.
    assert not re.search(r"(?m)^version\s*=\s*\"", pyproject)


def test_release_notes_mention_current_version() -> None:
    notes = (PROJECT_ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert __version__ in notes or display_version() in notes


def test_build_script_has_no_hardcoded_version() -> None:
    script = (PROJECT_ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
    assert '[string]$Version = ""' in script
    assert "--print-display-version" in script
