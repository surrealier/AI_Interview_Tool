from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from ai_interviewer.i18n import tr
from ai_interviewer.model_downloader import format_bytes


logger = logging.getLogger(__name__)

# Matches ids from session_store.new_session_id(): YYYYMMDD-HHMMSS-<8 hex>.
SESSION_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    path: Path
    created_at: str
    question_count: int
    answered_count: int
    size_bytes: int


def _directory_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def list_sessions(sessions_root: Path) -> list[SessionSummary]:
    """List saved sessions, newest first; tolerates missing/corrupt session.json."""
    sessions_root = Path(sessions_root)
    if not sessions_root.exists():
        return []
    summaries: list[SessionSummary] = []
    for child in sessions_root.iterdir():
        if not child.is_dir() or not SESSION_ID_PATTERN.match(child.name):
            continue
        created_at = ""
        question_count = 0
        answered_count = 0
        try:
            payload = json.loads((child / "session.json").read_text(encoding="utf-8"))
            created_at = str(payload.get("created_at", ""))
            records = payload.get("records", []) or []
            question_count = int(payload.get("question_count", len(records)))
            answered_count = sum(
                1
                for record in records
                if isinstance(record, dict)
                and (record.get("answer_seconds") not in ("", None) or str(record.get("transcript", "")).strip())
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Could not parse session.json for %s", child)
        summaries.append(
            SessionSummary(
                session_id=child.name,
                path=child,
                created_at=created_at,
                question_count=question_count,
                answered_count=answered_count,
                size_bytes=_directory_bytes(child),
            )
        )
    return sorted(summaries, key=lambda summary: summary.session_id, reverse=True)


def delete_session(sessions_root: Path, session_id: str) -> None:
    """Delete one session folder. Refuses anything that is not a direct,
    id-shaped child of sessions_root."""
    if not SESSION_ID_PATTERN.match(session_id):
        raise ValueError(f"Not a session id: {session_id!r}")
    sessions_root = Path(sessions_root).resolve()
    target = (sessions_root / session_id).resolve()
    if target.parent != sessions_root:
        raise ValueError(f"Session path escapes the sessions root: {target}")
    shutil.rmtree(target)


class SessionBrowserDialog(tk.Toplevel):
    """Browse, open, and delete saved interview sessions."""

    def __init__(self, master: tk.Misc, sessions_root: Path, active_session_id: str | None = None) -> None:
        super().__init__(master)
        self.sessions_root = Path(sessions_root)
        self.active_session_id = active_session_id

        self.title(tr("sb.title"))
        self.geometry("680x420")
        self.minsize(560, 300)
        self.transient(master)

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = ("created", "questions", "answered", "size")
        self.tree = ttk.Treeview(frame, columns=columns, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=tr("sb.col_session"))
        self.tree.heading("created", text=tr("sb.col_created"))
        self.tree.heading("questions", text=tr("sb.col_questions"))
        self.tree.heading("answered", text=tr("sb.col_answered"))
        self.tree.heading("size", text=tr("sb.col_size"))
        self.tree.column("#0", width=220, stretch=True)
        self.tree.column("created", width=160, stretch=False)
        self.tree.column("questions", width=70, anchor="e", stretch=False)
        self.tree.column("answered", width=70, anchor="e", stretch=False)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text=tr("sb.open_folder"), command=self._open_selected).pack(side="left")
        ttk.Button(buttons, text=tr("sb.delete"), command=self._delete_selected).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text=tr("sb.refresh"), command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text=tr("common.close"), command=self.destroy).pack(side="right")

        self.refresh()

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for summary in list_sessions(self.sessions_root):
            label = summary.session_id
            if summary.session_id == self.active_session_id:
                label += tr("sb.active_suffix")
            self.tree.insert(
                "",
                "end",
                iid=summary.session_id,
                text=label,
                values=(
                    summary.created_at.replace("T", " ")[:19],
                    summary.question_count,
                    summary.answered_count,
                    format_bytes(summary.size_bytes),
                ),
            )

    def _selected_session_id(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

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
            messagebox.showwarning(tr("sb.title"), tr("sb.cannot_delete_active"), parent=self)
            return
        if not messagebox.askyesno(tr("sb.delete_title"), tr("sb.delete_ask", session_id=session_id), parent=self):
            return
        try:
            delete_session(self.sessions_root, session_id)
        except (OSError, ValueError) as exc:
            logger.exception("Could not delete session %s", session_id)
            messagebox.showerror(tr("sb.delete_title"), str(exc), parent=self)
            return
        self.refresh()
