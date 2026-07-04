from __future__ import annotations

import argparse
import re

from ai_interviewer import __version__
from ai_interviewer.config import AppConfig, application_base_dir
from ai_interviewer.diagnostics import diagnostics_text, collect_runtime_diagnostics


def display_version(version: str = __version__) -> str:
    """Map the PEP 440 version to the human-readable release tag.

    ``0.9.0b0`` -> ``v0.9.0-beta``, ``1.0.0rc1`` -> ``v1.0.0-rc1``,
    ``1.0.0`` -> ``v1.0.0``.
    """
    match = re.match(r"^(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?$", version)
    if not match:
        return f"v{version}"
    base, kind, num = match.groups()
    if kind is None:
        return f"v{base}"
    if kind == "rc":
        return f"v{base}-rc{num}"
    label = {"a": "alpha", "b": "beta"}[kind]
    return f"v{base}-{label}"


def release_notes_mention_version() -> bool | None:
    """Return True/False if RELEASE_NOTES.md was checked, None if not found."""
    notes_path = application_base_dir() / "RELEASE_NOTES.md"
    try:
        text = notes_path.read_text(encoding="utf-8")
    except OSError:
        return None
    return __version__ in text or display_version() in text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AI Interviewer release/runtime checks.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when required runtime checks fail.",
    )
    parser.add_argument(
        "--print-version",
        action="store_true",
        help="Print the PEP 440 package version and exit.",
    )
    parser.add_argument(
        "--print-display-version",
        action="store_true",
        help="Print the human-readable release tag (e.g. v0.9.0-beta) and exit.",
    )
    args = parser.parse_args(argv)

    if args.print_version:
        print(__version__)
        return 0
    if args.print_display_version:
        print(display_version())
        return 0

    config = AppConfig.load()
    config.ensure_directories()
    report = collect_runtime_diagnostics(config)
    print(f"AI Interviewer {__version__}")
    print(diagnostics_text(report))

    mentioned = release_notes_mention_version()
    if mentioned is False:
        print(
            f"[WARN] RELEASE_NOTES.md does not mention {__version__} / {display_version()}."
        )

    if args.strict and report.has_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
