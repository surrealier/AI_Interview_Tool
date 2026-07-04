from __future__ import annotations

from ai_interviewer.error_dialog import install_thread_excepthooks
from ai_interviewer.gui import run_app
from ai_interviewer.logging_setup import configure_logging


def main() -> int:
    configure_logging()
    install_thread_excepthooks()
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
