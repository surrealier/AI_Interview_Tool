from __future__ import annotations

from pathlib import Path
from tkinter import ttk
import tkinter as tk
from typing import Any


class InterviewerVideoPlayer:
    def __init__(self, parent: tk.Widget, width: int = 420, height: int = 236):
        self.width = width
        self.height = height
        self.video_path: Path | None = None
        self._capture: Any | None = None
        self._running = False
        self._photo: Any | None = None
        self._cv2: Any | None = None
        self._image: Any | None = None
        self._image_tk: Any | None = None

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.label = tk.Label(
            self.frame,
            width=width,
            height=height,
            bg="#111111",
            fg="#d6d6d6",
            anchor="center",
            justify="center",
            text="면접관 영상 대기",
        )
        self.label.grid(row=0, column=0, sticky="nsew")

    @property
    def widget(self) -> ttk.Frame:
        return self.frame

    def set_video_path(self, path: Path) -> None:
        self.video_path = Path(path)
        if not self._running:
            self._show_placeholder("면접관 영상 대기")

    def start(self) -> None:
        if self._running:
            return
        if self.video_path is None or not self.video_path.exists():
            self._show_placeholder("영상 파일 없음\nassets/interviewer.mp4 또는 영상 파일을 선택하세요.")
            return
        if not self._load_dependencies():
            self._show_placeholder("영상 재생 의존성 없음\nrequirements-interactive.txt 설치 필요")
            return

        self._capture = self._cv2.VideoCapture(str(self.video_path))
        if not self._capture or not self._capture.isOpened():
            self._show_placeholder("영상 파일을 열 수 없습니다.")
            self._release_capture()
            return

        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False
        self._release_capture()
        self._show_placeholder("면접관 영상 대기")

    def destroy(self) -> None:
        self.stop()
        self.frame.destroy()

    def _tick(self) -> None:
        if not self._running or self._capture is None:
            return

        ok, frame = self._capture.read()
        if not ok:
            self._capture.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        if ok:
            frame = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
            image = self._image.fromarray(frame)
            image.thumbnail((self.width, self.height))
            canvas = self._image.new("RGB", (self.width, self.height), (17, 17, 17))
            offset = ((self.width - image.width) // 2, (self.height - image.height) // 2)
            canvas.paste(image, offset)
            self._photo = self._image_tk.PhotoImage(canvas)
            self.label.configure(image=self._photo, text="")

        self.label.after(33, self._tick)

    def _load_dependencies(self) -> bool:
        if self._cv2 is not None:
            return True
        try:
            import cv2
            from PIL import Image, ImageTk
        except ImportError:
            return False

        self._cv2 = cv2
        self._image = Image
        self._image_tk = ImageTk
        return True

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None

    def _show_placeholder(self, text: str) -> None:
        self._photo = None
        self.label.configure(image="", text=text)
