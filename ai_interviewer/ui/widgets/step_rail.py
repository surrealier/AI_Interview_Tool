from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ai_interviewer.ui.theme import manager as theme_manager


class StepRail(QWidget):
    """Vertical wizard progress rail: dots, connector line, step labels."""

    ROW_GAP = 42
    TOP_PAD = 26
    DOT_X = 24

    def __init__(self, labels: tuple[str, ...] = (), current: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels = tuple(labels)
        self._current = current
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._subscribe_theme()

    def set_steps(self, labels: tuple[str, ...]) -> None:
        self._labels = tuple(labels)
        self.updateGeometry()
        self.update()

    def set_current(self, index: int) -> None:
        if index != self._current:
            self._current = index
            self.update()

    def sizeHint(self) -> QSize:
        height = self.TOP_PAD * 2 + self.ROW_GAP * max(0, len(self._labels) - 1)
        return QSize(230, max(300, height))

    def paintEvent(self, _event) -> None:
        t = theme_manager.active_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._labels:
            return
        x = self.DOT_X
        y0 = self.TOP_PAD
        line_pen = QPen(QColor(t.border), 2)
        painter.setPen(line_pen)
        painter.drawLine(x, y0, x, y0 + self.ROW_GAP * (len(self._labels) - 1))

        base_font = QFont(self.font())
        base_font.setPointSize(t.size_caption)

        for index, text in enumerate(self._labels):
            y = y0 + self.ROW_GAP * index
            active = index == self._current
            done = index < self._current
            fill = QColor(t.accent if active else t.primary if done else t.surface_alt)
            outline = QColor(t.glow if active else t.border)
            painter.setPen(QPen(outline, 2))
            painter.setBrush(fill)
            painter.drawEllipse(QRectF(x - 7, y - 7, 14, 14))

            base_font.setBold(active)
            painter.setFont(base_font)
            painter.setPen(QColor(t.ink if active else t.muted))
            painter.drawText(
                QRectF(x + 20, y - 14, max(40, self.width() - x - 28), 28),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
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
