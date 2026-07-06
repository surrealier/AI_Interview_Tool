from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ai_interviewer.i18n import tr


class InterviewerVideoWidget(QLabel):
    """Interviewer stage: plays the configured video via cv2, or animates a
    QPainter-drawn synthetic interviewer when no video is available.
    Double-click toggles a fullscreen mirror window."""

    def __init__(self, width: int = 520, height: int = 292, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage_width = width
        self._stage_height = height
        self.video_path: Path | None = None
        self._capture: Any | None = None
        self._cv2: Any | None = None
        self._running = False
        self._synthetic_mode = False
        self._synthetic_frame = 0
        self._last_frame: QImage | None = None
        self._fullscreen: _FullscreenVideoWindow | None = None

        self.setProperty("role", "videoStage")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Fixed stage height; width follows the column so the card never clips.
        self.setMinimumSize(280, height)
        self.setMaximumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setText(tr("video.placeholder"))

        self._video_timer = QTimer(self)
        self._video_timer.setInterval(33)
        self._video_timer.timeout.connect(self._tick)
        self._synthetic_timer = QTimer(self)
        self._synthetic_timer.setInterval(80)
        self._synthetic_timer.timeout.connect(self._tick_synthetic)

    # -- public API (same shape as the old InterviewerVideoPlayer) ---------

    def set_video_path(self, path: Path) -> None:
        self.video_path = Path(path)
        if not self._running:
            self._show_placeholder(tr("video.placeholder"))

    def start(self) -> None:
        if self._running:
            return
        if self.video_path is None or not self.video_path.exists():
            self._running = True
            self._synthetic_mode = True
            self._synthetic_frame = 0
            self._synthetic_timer.start()
            return
        if not self._load_cv2():
            self._show_placeholder(tr("video.runtime_missing"))
            return

        self._capture = self._cv2.VideoCapture(str(self.video_path))
        if not self._capture or not self._capture.isOpened():
            self._show_placeholder(tr("video.cannot_open"))
            self._release_capture()
            return

        self._running = True
        self._synthetic_mode = False
        self._video_timer.start()

    def stop(self) -> None:
        self._running = False
        self._synthetic_mode = False
        self._video_timer.stop()
        self._synthetic_timer.stop()
        self._release_capture()
        self._show_placeholder(tr("video.placeholder"))

    def shutdown(self) -> None:
        self.stop()
        self._close_fullscreen()

    # -- fullscreen ----------------------------------------------------------

    def mouseDoubleClickEvent(self, _event) -> None:
        self.toggle_fullscreen()

    def toggle_fullscreen(self) -> None:
        if self._fullscreen is not None:
            self._close_fullscreen()
            return
        window = _FullscreenVideoWindow(on_close=self._close_fullscreen)
        window.showFullScreen()
        self._fullscreen = window
        if self._last_frame is not None:
            window.show_frame(self._last_frame)

    def _close_fullscreen(self) -> None:
        window = self._fullscreen
        self._fullscreen = None
        if window is not None:
            window.close()
            window.deleteLater()

    # -- frame loop ------------------------------------------------------------

    def _tick(self) -> None:
        if not self._running or self._capture is None:
            return
        ok, frame = self._capture.read()
        if not ok:
            self._capture.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        if ok:
            rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
            self._render_image(image)

    def _tick_synthetic(self) -> None:
        if not self._running or not self._synthetic_mode:
            return
        self._render_image(_draw_synthetic_interviewer(self._stage_width, self._stage_height, self._synthetic_frame))
        self._synthetic_frame += 1

    def _render_image(self, image: QImage) -> None:
        self._last_frame = image
        self.setPixmap(_letterboxed(image, self.width(), self.height()))
        self.setText("")
        if self._fullscreen is not None:
            self._fullscreen.show_frame(image)

    def _show_placeholder(self, text: str) -> None:
        self._last_frame = None
        self.setPixmap(QPixmap())
        self.setText(text)
        if self._fullscreen is not None:
            self._fullscreen.show_placeholder(text)

    # -- deps -----------------------------------------------------------------

    def _load_cv2(self) -> bool:
        if self._cv2 is not None:
            return True
        try:
            import cv2
        except ImportError:
            return False
        self._cv2 = cv2
        return True

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None


class _FullscreenVideoWindow(QWidget):
    def __init__(self, on_close) -> None:
        super().__init__()
        self._on_close = on_close
        self.setWindowTitle(tr("video.fullscreen_title"))
        self.setStyleSheet("background-color: #050505;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #f5f5f5; background-color: #050505;")
        layout.addWidget(self._label)

    def show_frame(self, image: QImage) -> None:
        self._label.setText("")
        self._label.setPixmap(_letterboxed(image, max(1, self.width()), max(1, self.height())))

    def show_placeholder(self, text: str) -> None:
        self._label.setPixmap(QPixmap())
        self._label.setText(text)

    def mouseDoubleClickEvent(self, _event) -> None:
        self._request_close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._request_close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        super().closeEvent(event)

    def _request_close(self) -> None:
        callback = self._on_close
        self._on_close = lambda: None
        callback()


def _letterboxed(image: QImage, width: int, height: int) -> QPixmap:
    pixmap = QPixmap.fromImage(image).scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return pixmap


def _draw_synthetic_interviewer(width: int, height: int, frame: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB888)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    center_x = width // 2
    head_top = int(height * 0.16)
    head_bottom = int(height * 0.58)
    face_color = QColor(228, 190, 158)
    hair_color = QColor(36, 35, 39)
    suit_color = QColor(25, 43, 73)
    shirt_color = QColor(242, 245, 249)
    tie_color = QColor(32, 84, 214)

    painter.fillRect(0, 0, width, height, QColor(12, 17, 29))
    painter.fillRect(0, int(height * 0.64), width, height, QColor(16, 24, 39))
    painter.setBrush(hair_color)
    painter.drawEllipse(center_x - 84, head_top - 20, 168, 90)
    painter.setBrush(face_color)
    painter.drawEllipse(center_x - 72, head_top, 144, head_bottom - head_top)
    painter.setBrush(suit_color)
    painter.drawPolygon(
        QPolygon(
            [
                QPoint(center_x - 170, height),
                QPoint(center_x - 88, int(height * 0.58)),
                QPoint(center_x + 88, int(height * 0.58)),
                QPoint(center_x + 170, height),
            ]
        )
    )
    painter.setBrush(shirt_color)
    painter.drawPolygon(
        QPolygon(
            [
                QPoint(center_x - 54, int(height * 0.62)),
                QPoint(center_x, int(height * 0.78)),
                QPoint(center_x + 54, int(height * 0.62)),
            ]
        )
    )
    painter.setBrush(tie_color)
    painter.drawPolygon(
        QPolygon(
            [
                QPoint(center_x - 13, int(height * 0.64)),
                QPoint(center_x + 13, int(height * 0.64)),
                QPoint(center_x + 20, int(height * 0.94)),
                QPoint(center_x, int(height * 0.99)),
                QPoint(center_x - 20, int(height * 0.94)),
            ]
        )
    )

    eye_y = int(height * 0.36)
    painter.setBrush(QColor(22, 22, 22))
    painter.drawEllipse(center_x - 38, eye_y, 12, 8)
    painter.drawEllipse(center_x + 26, eye_y, 12, 8)
    painter.setPen(QPen(QColor(72, 48, 40), 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRect(center_x - 45, eye_y - 18, 25, 23), 200 * 16, 140 * 16)
    painter.drawArc(QRect(center_x + 20, eye_y - 18, 25, 23), 200 * 16, 140 * 16)
    painter.setPen(Qt.PenStyle.NoPen)

    mouth_phase = frame % 18
    mouth_height = 6 + (10 if 4 <= mouth_phase <= 12 else 0)
    mouth_y = int(height * 0.48)
    painter.setBrush(QColor(88, 32, 38))
    painter.drawRoundedRect(
        QRect(center_x - 30, mouth_y, 60, mouth_height),
        mouth_height / 2,
        mouth_height / 2,
    )
    if mouth_height > 8:
        painter.setBrush(QColor(244, 232, 220))
        painter.drawRect(center_x - 20, mouth_y + 1, 40, 3)

    painter.end()
    return image
