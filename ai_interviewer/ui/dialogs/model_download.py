from __future__ import annotations

import logging
import time
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ai_interviewer.config import AppConfig
from ai_interviewer.i18n import tr
from ai_interviewer.model_downloader import (
    DownloadPlan,
    DownloadProgress,
    ModelDownloader,
    check_disk_space,
    format_bytes,
    plan_download,
)
from ai_interviewer.ui.widgets.buttons import IconButton
from ai_interviewer.ui.workers import run_bg


logger = logging.getLogger(__name__)


class _Bridge(QObject):
    """Marshals ModelDownloader's worker-thread callbacks onto the UI thread
    (cross-thread signal emission is queued automatically)."""

    progress = Signal(object)
    done = Signal()
    error = Signal(object)
    cancelled = Signal()


class ModelDownloadDialog(QDialog):
    """Window-modal dialog that plans and runs a model download with progress."""

    def __init__(
        self,
        parent: QWidget | None,
        config: AppConfig,
        model_id: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_model = config
        self.model_id = model_id
        self.on_complete = on_complete
        self.downloader: ModelDownloader | None = None
        self.plan: DownloadPlan | None = None
        self._succeeded = False

        self.setWindowTitle(tr("dl.title"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedSize(520, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        model_label = QLabel(model_id)
        model_label.setProperty("role", "section")
        layout.addWidget(model_label)

        self.status_label = QLabel(tr("dl.checking"))
        self.status_label.setWordWrap(True)
        layout.addSpacing(6)
        layout.addWidget(self.status_label)

        self.size_label = QLabel("")
        layout.addWidget(self.size_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(False)
        layout.addSpacing(8)
        layout.addWidget(self.progress_bar)

        self.progress_detail_label = QLabel("")
        self.progress_detail_label.setProperty("role", "muted")
        layout.addWidget(self.progress_detail_label)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        buttons.addStretch(1)
        self.retry_button = IconButton(tr("common.retry"), icon_name="refresh-cw", kind="tool")
        self.retry_button.clicked.connect(self._start_planning)
        self.retry_button.hide()
        buttons.addWidget(self.retry_button)
        self.cancel_button = IconButton(tr("common.cancel"), kind="secondary")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons.addWidget(self.cancel_button)

        self._bridge = _Bridge(self)
        self._bridge.progress.connect(self._on_progress)
        self._bridge.done.connect(self._on_done)
        self._bridge.error.connect(self._show_error)
        self._bridge.cancelled.connect(self._on_cancelled)

        self._start_planning()

    # -- lifecycle -------------------------------------------------------

    def _start_planning(self) -> None:
        self.retry_button.hide()
        self.cancel_button.setText(tr("common.cancel"))
        self.cancel_button.setEnabled(True)
        self.status_label.setText(tr("dl.checking"))
        self.size_label.setText("")
        self.progress_detail_label.setText("")
        self.progress_bar.setValue(0)

        run_bg(
            self,
            lambda: plan_download(self.config_model.model_root, self.model_id),
            on_done=self._on_plan_ready,
            on_error=self._show_error,
            name="model-download-plan",
        )

    def _on_plan_ready(self, plan: DownloadPlan) -> None:
        self.plan = plan
        if not plan.repos:
            self._succeeded = True
            self.status_label.setText(tr("dl.already_installed"))
            self.cancel_button.setText(tr("common.close"))
            return

        ok, required, free = check_disk_space(self.config_model.model_root, plan)
        self.size_label.setText(
            tr("dl.size_line", total=format_bytes(plan.total_bytes), free=format_bytes(free))
        )
        if not ok:
            self.status_label.setText(tr("dl.no_space", required=format_bytes(required)))
            self.cancel_button.setText(tr("common.close"))
            self.retry_button.show()
            return

        self.status_label.setText(tr("dl.downloading"))
        self.downloader = ModelDownloader(
            plan,
            on_progress=self._bridge.progress.emit,
            on_done=self._bridge.done.emit,
            on_error=self._bridge.error.emit,
            on_cancelled=self._bridge.cancelled.emit,
        )
        self.downloader.start()

    # -- callbacks (main thread via bridge) --------------------------------

    def _on_progress(self, progress: DownloadProgress) -> None:
        self.progress_bar.setValue(int(progress.fraction * 1000))
        speed = f"{format_bytes(progress.speed_bps)}/s" if progress.speed_bps > 0 else "-"
        remaining = progress.total_bytes - progress.downloaded_bytes
        if progress.speed_bps > 512:
            eta_seconds = int(remaining / progress.speed_bps)
            eta = time.strftime("%H:%M:%S", time.gmtime(min(eta_seconds, 86399)))
        else:
            eta = "-"
        self.progress_detail_label.setText(
            tr(
                "dl.progress_detail",
                done=format_bytes(progress.downloaded_bytes),
                total=format_bytes(progress.total_bytes),
                speed=speed,
                eta=eta,
            )
        )

    def _on_done(self) -> None:
        self._succeeded = True
        self.progress_bar.setValue(1000)
        self.status_label.setText(tr("dl.done"))
        self.cancel_button.setText(tr("common.close"))

    def _on_cancelled(self) -> None:
        self.status_label.setText(tr("dl.cancelled"))
        self.cancel_button.setText(tr("common.close"))
        self.cancel_button.setEnabled(True)
        self.retry_button.show()

    def _show_error(self, exc: Exception) -> None:
        logger.warning("Model download dialog error: %s", exc)
        self.status_label.setText(tr("dl.failed", error=exc))
        self.cancel_button.setText(tr("common.close"))
        self.cancel_button.setEnabled(True)
        self.retry_button.show()

    # -- actions -----------------------------------------------------------

    def _on_cancel_clicked(self) -> None:
        if self.downloader is not None and not self.downloader.finished:
            self.downloader.cancel()
            self.status_label.setText(tr("dl.cancelling"))
            self.cancel_button.setEnabled(False)
            return
        self.close()

    def closeEvent(self, event) -> None:
        if self.downloader is not None and not self.downloader.finished:
            self.downloader.cancel()
        for signal, slot in (
            (self._bridge.progress, self._on_progress),
            (self._bridge.done, self._on_done),
            (self._bridge.error, self._show_error),
            (self._bridge.cancelled, self._on_cancelled),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        completed = self._succeeded
        callback = self.on_complete
        super().closeEvent(event)
        if completed and callback is not None:
            callback()
