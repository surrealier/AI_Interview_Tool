from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ai_interviewer.config import default_log_path


def configure_logging() -> None:
    log_path = default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    root.setLevel(logging.INFO)
    root.addHandler(handler)
