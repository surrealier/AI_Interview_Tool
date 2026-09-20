from __future__ import annotations

import subprocess
import sys


CORE_IMPORT_CHECK = """
import sys
import ai_interviewer.main
import ai_interviewer.diagnostics
import ai_interviewer.engine
import ai_interviewer.session_browser
import ai_interviewer.error_dialog
import ai_interviewer.credentials
import ai_interviewer.intelligence
assert "PySide6" not in sys.modules, "core imports must not pull in PySide6"
assert "tkinter" not in sys.modules, "tkinter must be gone from the app"
# The cloud SDK is optional: importing the analysis layer must not require it.
assert "anthropic" not in sys.modules, "the anthropic SDK must stay a lazy import"
print("clean")
"""


ANALYSIS_RUNS_WITHOUT_EXTRAS = """
import sys
from ai_interviewer.intelligence import analyze_answer_turn, build_report

insight = analyze_answer_turn(
    "Describe a problem you solved.",
    "We had a flaky deploy. I grouped the failures and shipped a checklist; "
    "rollbacks went from 3 a month to 0.",
    "English",
    duration_seconds=45,
)
assert insight.evaluation.overall > 0, "offline scoring produced nothing"
assert insight.delivery.measured, "delivery was not measured"
for module in ("anthropic", "torch", "sounddevice", "faster_whisper", "qwen_tts"):
    assert module not in sys.modules, f"offline analysis pulled in {module}"
print("clean")
"""


def test_core_imports_stay_toolkit_free() -> None:
    """--smoke must boot without Qt: importing the entry point and core
    modules may not load PySide6 (or the removed tkinter)."""
    result = subprocess.run(
        [sys.executable, "-c", CORE_IMPORT_CHECK],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout


def test_offline_analysis_needs_no_optional_runtime() -> None:
    """Scoring and probing must work on a bare install: no cloud SDK, no torch,
    no audio stack. This is what makes the offline engine the default rather
    than a placeholder."""
    result = subprocess.run(
        [sys.executable, "-c", ANALYSIS_RUNS_WITHOUT_EXTRAS],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout
