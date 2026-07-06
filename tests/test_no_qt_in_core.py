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
assert "PySide6" not in sys.modules, "core imports must not pull in PySide6"
assert "tkinter" not in sys.modules, "tkinter must be gone from the app"
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
