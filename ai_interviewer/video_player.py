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
        self._image_draw: Any | None = None
        self._image_tk: Any | None = None
        self._synthetic_mode = False
        self._synthetic_frame = 0

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
            if self._load_image_dependencies():
                self._running = True
                self._synthetic_mode = True
                self._synthetic_frame = 0
                self._tick_synthetic()
                return
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
        self._synthetic_mode = False
        self._tick()

    def stop(self) -> None:
        self._running = False
        self._synthetic_mode = False
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

    def _tick_synthetic(self) -> None:
        if not self._running or not self._synthetic_mode:
            return

        frame = self._synthetic_frame
        self._synthetic_frame += 1
        image = self._image.new("RGB", (self.width, self.height), (26, 29, 33))
        draw = self._image_draw.Draw(image)

        center_x = self.width // 2
        head_top = int(self.height * 0.16)
        head_bottom = int(self.height * 0.58)
        face_color = (226, 188, 156)
        hair_color = (42, 35, 32)
        suit_color = (43, 55, 73)
        shirt_color = (238, 241, 244)
        tie_color = (96, 54, 54)

        draw.rectangle((0, 0, self.width, self.height), fill=(25, 28, 32))
        draw.ellipse((center_x - 84, head_top - 20, center_x + 84, head_top + 70), fill=hair_color)
        draw.ellipse((center_x - 72, head_top, center_x + 72, head_bottom), fill=face_color)
        draw.polygon(
            (
                (center_x - 170, self.height),
                (center_x - 88, int(self.height * 0.58)),
                (center_x + 88, int(self.height * 0.58)),
                (center_x + 170, self.height),
            ),
            fill=suit_color,
        )
        draw.polygon(
            (
                (center_x - 54, int(self.height * 0.62)),
                (center_x, int(self.height * 0.78)),
                (center_x + 54, int(self.height * 0.62)),
            ),
            fill=shirt_color,
        )
        draw.polygon(
            (
                (center_x - 13, int(self.height * 0.64)),
                (center_x + 13, int(self.height * 0.64)),
                (center_x + 20, int(self.height * 0.94)),
                (center_x, int(self.height * 0.99)),
                (center_x - 20, int(self.height * 0.94)),
            ),
            fill=tie_color,
        )

        eye_y = int(self.height * 0.36)
        draw.ellipse((center_x - 38, eye_y, center_x - 26, eye_y + 8), fill=(22, 22, 22))
        draw.ellipse((center_x + 26, eye_y, center_x + 38, eye_y + 8), fill=(22, 22, 22))
        draw.arc((center_x - 45, eye_y - 18, center_x - 20, eye_y + 5), start=200, end=340, fill=(72, 48, 40), width=2)
        draw.arc((center_x + 20, eye_y - 18, center_x + 45, eye_y + 5), start=200, end=340, fill=(72, 48, 40), width=2)

        mouth_phase = frame % 18
        mouth_height = 6 + (10 if 4 <= mouth_phase <= 12 else 0)
        mouth_y = int(self.height * 0.48)
        draw.rounded_rectangle(
            (center_x - 30, mouth_y, center_x + 30, mouth_y + mouth_height),
            radius=mouth_height // 2,
            fill=(88, 32, 38),
        )
        if mouth_height > 8:
            draw.rectangle((center_x - 20, mouth_y + 1, center_x + 20, mouth_y + 4), fill=(244, 232, 220))

        self._photo = self._image_tk.PhotoImage(image)
        self.label.configure(image=self._photo, text="")
        self.label.after(80, self._tick_synthetic)

    def _load_dependencies(self) -> bool:
        if self._cv2 is not None:
            return True
        try:
            import cv2
        except ImportError:
            return False
        if not self._load_image_dependencies():
            return False

        self._cv2 = cv2
        return True

    def _load_image_dependencies(self) -> bool:
        if self._image is not None:
            return True
        try:
            from PIL import Image, ImageDraw, ImageTk
        except ImportError:
            return False
        self._image = Image
        self._image_draw = ImageDraw
        self._image_tk = ImageTk
        return True

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None

    def _show_placeholder(self, text: str) -> None:
        self._photo = None
        self.label.configure(image="", text=text)
