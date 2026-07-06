from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ai_interviewer.i18n import tr
from ai_interviewer.model_downloader import format_bytes
from ai_interviewer.session_browser import SessionSummary, delete_session, list_sessions
from ai_interviewer.ui.dialogs import messages
from ai_interviewer.ui.widgets.buttons import IconButton
from ai_interviewer.ui.workers import run_bg


logger = logging.getLogger(__name__)


class SessionTableModel(QAbstractTableModel):
    def __init__(self, active_session_id: str | None) -> None:
        super().__init__()
        self._active_session_id = active_session_id
        self._rows: list[SessionSummary] = []

    def set_rows(self, rows: list[SessionSummary]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def summary_at(self, row: int) -> SessionSummary | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    # -- QAbstractTableModel ------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else 5

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return (
                tr("sb.col_session"),
                tr("sb.col_created"),
                tr("sb.col_questions"),
                tr("sb.col_answered"),
                tr("sb.col_size"),
            )[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        summary = self._rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                label = summary.session_id
                if summary.session_id == self._active_session_id:
                    label += tr("sb.active_suffix")
                return label
            if column == 1:
                return summary.created_at.replace("T", " ")[:19]
            if column == 2:
                return summary.question_count
            if column == 3:
                return summary.answered_count
            if column == 4:
                return format_bytes(summary.size_bytes)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in (2, 3, 4):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class SessionBrowserDialog(QDialog):
    """Browse, open, and delete saved interview sessions."""

    def __init__(self, parent: QWidget | None, sessions_root: Path, active_session_id: str | None = None) -> None:
        super().__init__(parent)
        self.sessions_root = Path(sessions_root)
        self.active_session_id = active_session_id

        self.setWindowTitle(tr("sb.title"))
        self.resize(680, 420)
        self.setMinimumSize(560, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.model = SessionTableModel(active_session_id)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.loading_label = QLabel(tr("sb.loading"))
        self.loading_label.setProperty("role", "muted")
        layout.addWidget(self.loading_label)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        open_button = IconButton(tr("sb.open_folder"), icon_name="folder-open", kind="tool")
        delete_button = IconButton(tr("sb.delete"), icon_name="x", kind="danger")
        refresh_button = IconButton(tr("sb.refresh"), icon_name="refresh-cw", kind="tool")
        close_button = IconButton(tr("common.close"), kind="secondary")
        open_button.clicked.connect(self._open_selected)
        delete_button.clicked.connect(self._delete_selected)
        refresh_button.clicked.connect(self.refresh)
        close_button.clicked.connect(self.close)
        buttons.addWidget(open_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(refresh_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        self.refresh()

    def refresh(self) -> None:
        self.loading_label.show()
        sessions_root = self.sessions_root
        run_bg(
            self,
            lambda: list_sessions(sessions_root),
            on_done=self._on_sessions_listed,
            on_error=self._on_listing_error,
            name="session-listing",
        )

    def _on_sessions_listed(self, summaries: list[SessionSummary]) -> None:
        self.loading_label.hide()
        self.model.set_rows(summaries)

    def _on_listing_error(self, exc: Exception) -> None:
        logger.exception("Could not list sessions", exc_info=exc)
        self.loading_label.hide()
        messages.error(self, tr("sb.title"), str(exc))

    def _selected_session_id(self) -> str | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        summary = self.model.summary_at(indexes[0].row())
        return summary.session_id if summary else None

    def _open_selected(self) -> None:
        session_id = self._selected_session_id()
        if session_id is None:
            return
        try:
            os.startfile(str(self.sessions_root / session_id))  # noqa: S606
        except OSError:
            logger.exception("Could not open session folder %s", session_id)

    def _delete_selected(self) -> None:
        session_id = self._selected_session_id()
        if session_id is None:
            return
        if session_id == self.active_session_id:
            messages.warning(self, tr("sb.title"), tr("sb.cannot_delete_active"))
            return
        if not messages.ask_yes_no(self, tr("sb.delete_title"), tr("sb.delete_ask", session_id=session_id)):
            return
        try:
            delete_session(self.sessions_root, session_id)
        except (OSError, ValueError) as exc:
            logger.exception("Could not delete session %s", session_id)
            messages.error(self, tr("sb.delete_title"), str(exc))
            return
        self.refresh()
