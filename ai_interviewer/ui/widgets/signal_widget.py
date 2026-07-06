from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ai_interviewer.i18n import tr
from ai_interviewer.ui.theme import manager as theme_manager


class SignalWidget(QWidget):
    """Animated audio-studio bars; the asset-free visual signature of the app."""

    def __init__(
        self,
        *,
        height: int = 120,
        animated: bool = False,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._compact = compact
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._subscribe_theme()
        if animated:
            self.start()

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._phase += 0.28
        self.update()

    def paintEvent(self, _event) -> None:
        t = theme_manager.active_tokens()
        painter = QPainter(self)
        width = max(1, self.width())
        height = max(1, self.height())
        painter.fillRect(0, 0, width, height, QColor(t.surface_deep))

        grid = 28 if self._compact else 36
        painter.setPen(QPen(QColor(t.grid_line), 1))
        for x in range(0, width, grid):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, grid):
            painter.drawLine(0, y, width, y)

        mid = height * 0.56
        painter.setPen(QPen(QColor(t.border), 1))
        painter.drawLine(0, int(mid), width, int(mid))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        bars = 34 if self._compact else 58
        gap = 3 if self._compact else 4
        bar_width = max(3, int((width - gap * (bars + 1)) / bars))
        start_x = max(12, int((width - (bar_width + gap) * bars) / 2))
        for index in range(bars):
            x0 = start_x + index * (bar_width + gap)
            wave_a = math.sin(index * 0.43 + self._phase)
            wave_b = math.sin(index * 0.17 - self._phase * 0.7)
            amp = (wave_a + wave_b + 2) / 4
            bar_height = 10 + amp * (height * (0.46 if self._compact else 0.58))
            color = t.accent if index % 9 == 0 else t.primary
            if index % 5 == 0:
                color = t.glow
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(x0, mid - bar_height / 2, bar_width, bar_height))

        if not self._compact:
            caption_font = QFont(self.font())
            caption_font.setPointSize(8)
            caption_font.setBold(True)
            painter.setFont(caption_font)
            painter.setPen(QColor(t.muted))
            painter.drawText(
                QRectF(22, 10, width - 44, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                tr("signal.voice"),
            )
            painter.setPen(QColor(t.accent))
            painter.drawText(
                QRectF(22, height - 32, width - 44, 24),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                tr("signal.local"),
            )
        painter.end()

    def _subscribe_theme(self) -> None:
        # Bound-method connections are auto-disconnected by Qt when the
        # receiver widget is destroyed; no manual teardown needed.
        try:
            mgr = theme_manager.manager()
        except RuntimeError:
            return
        mgr.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, _tokens) -> None:
        self.update()
