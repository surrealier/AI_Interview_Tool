from __future__ import annotations

import sys

from ai_interviewer.error_dialog import install_thread_excepthooks
from ai_interviewer.logging_setup import configure_logging


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    configure_logging()
    install_thread_excepthooks()
    if "--smoke" in args:
        return run_smoke_check()

    from ai_interviewer.gui import run_app

    return run_app()


def run_smoke_check() -> int:
    """Headless packaged-build check; console=False, so report via log + exit code.

    Exit 0 means the packaged runtime boots and required storage works.
    Missing model weights do NOT fail the smoke check (a fresh install has
    none yet; the in-app downloader owns that), other required failures do.
    """
    import logging

    from ai_interviewer import __version__
    from ai_interviewer.config import AppConfig
    from ai_interviewer.diagnostics import STATUS_FAIL, collect_runtime_diagnostics, diagnostics_text
    from ai_interviewer.i18n import SUPPORTED_UI_LANGUAGES, set_language, tr

    logger = logging.getLogger("ai_interviewer.smoke")
    try:
        config = AppConfig.load()
        config.ensure_directories()
        if config.ui_language in SUPPORTED_UI_LANGUAGES:
            set_language(config.ui_language)
        report = collect_runtime_diagnostics(config)
        logger.info("smoke check for %s\n%s", __version__, diagnostics_text(report))
        model_item_names = {tr("diag.qwen_model"), tr("diag.qwen_tokenizer")}
        blocking = [
            item
            for item in report.items
            if item.status == STATUS_FAIL and item.required and item.name not in model_item_names
        ]
        if blocking:
            logger.error("smoke check FAILED: %s", "; ".join(f"{item.name}: {item.detail}" for item in blocking))
            return 1
        logger.info("smoke check OK")
        return 0
    except Exception:
        logger.exception("smoke check crashed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
