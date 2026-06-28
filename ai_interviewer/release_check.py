from __future__ import annotations

import argparse

from ai_interviewer import __version__
from ai_interviewer.config import AppConfig
from ai_interviewer.diagnostics import diagnostics_text, collect_runtime_diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AI Interviewer release/runtime checks.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when required runtime checks fail.",
    )
    args = parser.parse_args(argv)

    config = AppConfig.load()
    config.ensure_directories()
    report = collect_runtime_diagnostics(config)
    print(f"AI Interviewer {__version__}")
    print(diagnostics_text(report))
    if args.strict and report.has_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
