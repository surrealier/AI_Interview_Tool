from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable

from ai_interviewer.config import AppConfig
from ai_interviewer.model_downloader import (
    DownloadPlan,
    DownloadProgress,
    ModelDownloader,
    check_disk_space,
    format_bytes,
    plan_download,
)


logger = logging.getLogger(__name__)


class ModelDownloadDialog(tk.Toplevel):
    """Modal dialog that plans and runs a model download with progress."""

    def __init__(
        self,
        master: tk.Misc,
        config: AppConfig,
        model_id: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.config_model = config
        self.model_id = model_id
        self.on_complete = on_complete
        self.downloader: ModelDownloader | None = None
        self.plan: DownloadPlan | None = None
        self._closed = False
        self._succeeded = False

        self.title("모델 다운로드")
        self.geometry("520x260")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)

        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=model_id, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="다운로드 정보를 확인하는 중...")
        ttk.Label(frame, textvariable=self.status_var, wraplength=470, justify="left").grid(
            row=1, column=0, sticky="w", pady=(10, 4)
        )
        self.size_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.size_var).grid(row=2, column=0, sticky="w")

        self.progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=1000)
        self.progress_bar.grid(row=3, column=0, sticky="ew", pady=(14, 4))
        self.progress_detail_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.progress_detail_var).grid(row=4, column=0, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        buttons.columnconfigure(0, weight=1)
        self.retry_button = ttk.Button(buttons, text="다시 시도", command=self._start_planning)
        self.cancel_button = ttk.Button(buttons, text="취소", command=self._on_cancel_clicked)
        self.cancel_button.pack(side="right")

        self.grab_set()
        self._start_planning()

    # -- lifecycle -------------------------------------------------------

    def _start_planning(self) -> None:
        self.retry_button.pack_forget()
        self.cancel_button.configure(text="취소", state="normal")
        self.status_var.set("다운로드 정보를 확인하는 중...")
        self.size_var.set("")
        self.progress_detail_var.set("")
        self.progress_bar.configure(value=0)

        def worker() -> None:
            try:
                plan = plan_download(self.config_model.model_root, self.model_id)
            except Exception as exc:
                self._ui(lambda: self._show_error(exc))
                return
            self._ui(lambda: self._on_plan_ready(plan))

        threading.Thread(target=worker, daemon=True, name="model-download-plan").start()

    def _on_plan_ready(self, plan: DownloadPlan) -> None:
        self.plan = plan
        if not plan.repos:
            self._succeeded = True
            self.status_var.set("이미 설치되어 있습니다.")
            self.cancel_button.configure(text="닫기")
            return

        ok, required, free = check_disk_space(self.config_model.model_root, plan)
        self.size_var.set(
            f"다운로드 용량: {format_bytes(plan.total_bytes)} · 남은 디스크 공간: {format_bytes(free)}"
        )
        if not ok:
            self.status_var.set(
                f"디스크 공간이 부족합니다. 최소 {format_bytes(required)}의 여유 공간이 필요합니다."
            )
            self.cancel_button.configure(text="닫기")
            self.retry_button.pack(side="right", padx=(0, 8))
            return

        self.status_var.set("다운로드 중... 창을 닫아도 이어받기가 가능합니다.")
        self.downloader = ModelDownloader(
            plan,
            on_progress=lambda progress: self._ui(lambda: self._on_progress(progress)),
            on_done=lambda: self._ui(self._on_done),
            on_error=lambda exc: self._ui(lambda: self._show_error(exc)),
            on_cancelled=lambda: self._ui(self._on_cancelled),
        )
        self.downloader.start()

    # -- callbacks (main thread) ------------------------------------------

    def _on_progress(self, progress: DownloadProgress) -> None:
        self.progress_bar.configure(value=int(progress.fraction * 1000))
        speed = f"{format_bytes(progress.speed_bps)}/s" if progress.speed_bps > 0 else "-"
        remaining = progress.total_bytes - progress.downloaded_bytes
        if progress.speed_bps > 512:
            eta_seconds = int(remaining / progress.speed_bps)
            eta = time.strftime("%H:%M:%S", time.gmtime(min(eta_seconds, 86399)))
        else:
            eta = "-"
        self.progress_detail_var.set(
            f"{format_bytes(progress.downloaded_bytes)} / {format_bytes(progress.total_bytes)}"
            f" · 속도 {speed} · 남은 시간 {eta}"
        )

    def _on_done(self) -> None:
        self._succeeded = True
        self.progress_bar.configure(value=1000)
        self.status_var.set("다운로드 완료. 모델을 사용할 준비가 되었습니다.")
        self.cancel_button.configure(text="닫기")

    def _on_cancelled(self) -> None:
        self.status_var.set("다운로드가 취소되었습니다. 받은 부분은 이어받기에 사용됩니다.")
        self.cancel_button.configure(text="닫기", state="normal")
        self.retry_button.pack(side="right", padx=(0, 8))

    def _show_error(self, exc: Exception) -> None:
        logger.warning("Model download dialog error: %s", exc)
        self.status_var.set(f"다운로드에 실패했습니다: {exc}\n네트워크 연결을 확인한 뒤 다시 시도하세요.")
        self.cancel_button.configure(text="닫기", state="normal")
        self.retry_button.pack(side="right", padx=(0, 8))

    # -- actions -----------------------------------------------------------

    def _on_cancel_clicked(self) -> None:
        if self.downloader is not None and not self.downloader.finished:
            self.downloader.cancel()
            self.status_var.set("취소하는 중...")
            self.cancel_button.configure(state="disabled")
            return
        self._on_close_request()

    def _on_close_request(self) -> None:
        if self.downloader is not None and not self.downloader.finished:
            self.downloader.cancel()
        self._closed = True
        completed = self._succeeded
        callback = self.on_complete
        self.grab_release()
        self.destroy()
        if completed and callback is not None:
            callback()

    def _ui(self, action: Callable[[], None]) -> None:
        if self._closed:
            return
        try:
            self.after(0, action)
        except tk.TclError:
            pass
