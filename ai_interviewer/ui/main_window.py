from __future__ import annotations

import logging

from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from ai_interviewer.app_state import SessionState
from ai_interviewer.config import resource_base_dir
from ai_interviewer.i18n import tr
from ai_interviewer.ui.context import AppContext
from ai_interviewer.ui.dialogs import messages
from ai_interviewer.ui.dialogs.model_download import ModelDownloadDialog
from ai_interviewer.ui.screens.report import ReportScreen
from ai_interviewer.ui.screens.wizard import WizardScreen
from ai_interviewer.ui.screens.workspace import WorkspaceScreen
from ai_interviewer.ui.workers import run_bg


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application shell: hosts the wizard and workspace screens on a
    QStackedWidget and owns cross-screen chores (language rebuild, downloads,
    shutdown)."""

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        ctx.window = self

        self.setWindowTitle("AI Interviewer")
        self.resize(1280, 860)
        self.setMinimumSize(1180, 760)
        icon_path = resource_base_dir() / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.wizard_screen: WizardScreen | None = WizardScreen(ctx, self)
        self.workspace_screen: WorkspaceScreen | None = None
        self.report_screen: ReportScreen | None = None
        self.stack.addWidget(self.wizard_screen)
        self._report_running = False

        ctx.languageRebuildRequested.connect(self._rebuild_current_view)

    # -- navigation ----------------------------------------------------------

    def show_wizard(self) -> WizardScreen:
        if self.wizard_screen is None:
            self.wizard_screen = WizardScreen(self.ctx, self)
            self.stack.addWidget(self.wizard_screen)
        self.stack.setCurrentWidget(self.wizard_screen)
        return self.wizard_screen

    def show_workspace(self) -> WorkspaceScreen:
        if self.workspace_screen is None:
            self.workspace_screen = WorkspaceScreen(self.ctx, self)
            self.stack.addWidget(self.workspace_screen)
        self.stack.setCurrentWidget(self.workspace_screen)
        return self.workspace_screen

    def workspace_question_text(self) -> str:
        if self.workspace_screen is None:
            return ""
        return self.workspace_screen.question_text_content()

    # -- report ---------------------------------------------------------------

    def show_report(self) -> ReportScreen:
        if self.report_screen is None:
            self.report_screen = ReportScreen(self.ctx, self)
            self.stack.addWidget(self.report_screen)
        self.stack.setCurrentWidget(self.report_screen)
        return self.report_screen

    def generate_report(self, force: bool = False) -> None:
        """Build the session report off the UI thread, then show it.

        `force` only matters for the rebuild button; a report is cheap to
        recompute offline and the cloud path is the user's explicit choice.
        """
        engine = self.ctx.engine
        if engine is None:
            messages.warning(self.ctx.window, tr("report.title"), tr("app.no_session"))
            return
        if self._report_running:
            return

        if self.workspace_screen is not None:
            self.workspace_screen.save_current_memo()
        self.ctx.apply_config_from_ui()

        screen = self.show_report()
        screen.set_loading()
        self._report_running = True
        chain = self.ctx.ai_chain()
        effort = self.ctx.ai_effort()

        run_bg(
            self,
            lambda: engine.build_report(chain=chain, effort=effort),
            on_done=self._on_report_ready,
            on_error=self._on_report_error,
            name="session-report",
        )

    def _on_report_ready(self, report) -> None:
        self._report_running = False
        if self.report_screen is not None:
            self.report_screen.show_report(report)
        self.ctx.status_var.set(tr("report.title"))

    def _on_report_error(self, exc: Exception) -> None:
        self._report_running = False
        logger.exception("Could not build the session report.", exc_info=exc)
        if self.report_screen is not None:
            self.report_screen.set_failed(str(exc))

    # -- downloads -----------------------------------------------------------

    def open_model_download(self, model_id: str, on_complete=None) -> None:
        def completed() -> None:
            self.ctx.provider = None
            self.ctx.preload_provider = None
            self.ctx.status_var.set(tr("wizard.model_download_done"))
            if on_complete is not None:
                on_complete()

        dialog = ModelDownloadDialog(self, self.ctx.config_model, model_id, on_complete=completed)
        dialog.open()

    # -- live language switch ---------------------------------------------------

    def _rebuild_current_view(self) -> None:
        """Rebuild the visible screen so tr() strings pick up the new language."""
        current = self.stack.currentWidget()
        if self.report_screen is not None and current is self.report_screen:
            self._rebuild_report()
            return
        if self.workspace_screen is None or current is self.wizard_screen:
            self._rebuild_wizard()
            return
        if self.ctx.session_state in {SessionState.IDLE, SessionState.READY}:
            questions = self.workspace_screen.question_text_content().strip()
            self._rebuild_workspace()
            if questions:
                self.workspace_screen.replace_question_text(questions)
            if self.ctx.engine is not None:
                self.workspace_screen._render_current_question()
        else:
            # Mid-session (speaking/recording): applied at the next rebuild.
            self.ctx.status_var.set(tr("app.language_applied_later"))

    def _rebuild_wizard(self) -> None:
        old = self.wizard_screen
        self.wizard_screen = WizardScreen(self.ctx, self)
        self.stack.addWidget(self.wizard_screen)
        if old is None or self.stack.currentWidget() is old:
            self.stack.setCurrentWidget(self.wizard_screen)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

    def _rebuild_report(self) -> None:
        """Re-render the report in the new UI language from the saved payload."""
        from ai_interviewer.intelligence import SessionReport

        old = self.report_screen
        self.report_screen = ReportScreen(self.ctx, self)
        self.stack.addWidget(self.report_screen)
        self.stack.setCurrentWidget(self.report_screen)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()
        stored = self.ctx.engine.session.report if self.ctx.engine is not None else None
        if stored:
            self.report_screen.show_report(SessionReport.from_dict(stored))

    def _rebuild_workspace(self) -> None:
        old = self.workspace_screen
        if old is not None:
            old.shutdown_widgets()
        self.workspace_screen = WorkspaceScreen(self.ctx, self)
        self.stack.addWidget(self.workspace_screen)
        if old is None or self.stack.currentWidget() is old:
            self.stack.setCurrentWidget(self.workspace_screen)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()

    # -- lifecycle -----------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.workspace_screen is not None:
            try:
                if self.ctx.engine is not None:
                    self.workspace_screen.save_current_memo()
            except Exception:
                logger.exception("Could not save the memo on close.")
            self.workspace_screen.shutdown_widgets()
        self.ctx.shutdown()
        super().closeEvent(event)
