"""Score visuals: the dial, the meters, the radar, and the chips.

All three painted widgets read their colors from the active theme tokens and
repaint on theme change, so a score keeps the same band color in light and dark.
Values are 0-100 to match the rubric; nothing here knows how a score was
produced.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from ai_interviewer.ui.theme import manager as theme_manager
from ai_interviewer.ui.theme.tokens import band_color_for_score


class _ThemedWidget(QWidget):
    """Base for painted widgets: repaint when the palette changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        try:
            theme_manager.manager().themeChanged.connect(self._on_theme_changed)
        except RuntimeError:
            # No manager in headless/unit-test contexts; active_tokens() still
            # returns a usable default.
            pass

    def _on_theme_changed(self, _tokens) -> None:
        self.update()


class ScoreDial(_ThemedWidget):
    """A single headline score as an arc with the number inside it."""

    def __init__(
        self,
        *,
        diameter: int = 132,
        thickness: int = 11,
        caption: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._score: float | None = None
        self._caption = caption
        self._thickness = thickness
        self.setFixedSize(diameter, diameter)

    def set_score(self, score: float | None, caption: str = "") -> None:
        self._score = None if score is None else max(0.0, min(100.0, float(score)))
        if caption:
            self._caption = caption
        self.update()

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        self.update()

    def paintEvent(self, _event) -> None:
        t = theme_manager.active_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inset = self._thickness / 2 + 1
        box = QRectF(inset, inset, self.width() - inset * 2, self.height() - inset * 2)

        track = QPen(QColor(t.track), self._thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawArc(box, 90 * 16, -360 * 16)

        score = self._score
        if score is not None:
            arc = QPen(QColor(band_color_for_score(t, score)), self._thickness)
            arc.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc)
            # Start at 12 o'clock and sweep clockwise, like a progress ring.
            painter.drawArc(box, 90 * 16, int(-360 * 16 * score / 100))

        number_font = QFont(self.font())
        number_font.setPointSize(max(14, int(self.height() * 0.24)))
        number_font.setBold(True)
        painter.setFont(number_font)
        painter.setPen(QColor(t.ink if score is not None else t.muted))
        text = "—" if score is None else f"{int(round(score))}"
        painter.drawText(
            QRectF(0, self.height() * 0.24, self.width(), self.height() * 0.38),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )

        if self._caption:
            caption_font = QFont(self.font())
            caption_font.setPointSize(max(7, int(self.height() * 0.075)))
            caption_font.setBold(True)
            painter.setFont(caption_font)
            painter.setPen(QColor(band_color_for_score(t, score) if score is not None else t.muted))
            painter.drawText(
                QRectF(0, self.height() * 0.60, self.width(), self.height() * 0.18),
                Qt.AlignmentFlag.AlignCenter,
                self._caption,
            )
        painter.end()


class ScoreBar(_ThemedWidget):
    """A labelled 0-100 meter; the row unit of every score breakdown."""

    def __init__(
        self,
        label: str = "",
        *,
        height: int = 26,
        label_width: int = 88,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._score: float | None = None
        self._suffix = ""
        self._label_width = label_width
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def set_score(self, score: float | None, suffix: str = "") -> None:
        self._score = None if score is None else max(0.0, min(100.0, float(score)))
        self._suffix = suffix
        self.update()

    def paintEvent(self, _event) -> None:
        t = theme_manager.active_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        label_font = QFont(self.font())
        label_font.setPointSize(t.size_caption)
        painter.setFont(label_font)
        painter.setPen(QColor(t.muted))
        painter.drawText(
            QRectF(0, 0, self._label_width, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._label,
        )

        value_width = 46
        bar_left = self._label_width + 6
        bar_right = self.width() - value_width
        bar_height = 7
        bar_top = (self.height() - bar_height) / 2
        bar_width = max(10.0, bar_right - bar_left - 8)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.track))
        painter.drawRoundedRect(QRectF(bar_left, bar_top, bar_width, bar_height), 4, 4)

        score = self._score
        if score is not None and score > 0:
            painter.setBrush(QColor(band_color_for_score(t, score)))
            painter.drawRoundedRect(
                QRectF(bar_left, bar_top, max(4.0, bar_width * score / 100), bar_height), 4, 4
            )

        value_font = QFont(t.mono_font)
        value_font.setPointSize(t.size_caption)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(QColor(t.ink if score is not None else t.muted))
        value_text = "—" if score is None else f"{int(round(score))}{self._suffix}"
        painter.drawText(
            QRectF(bar_right, 0, value_width, self.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            value_text,
        )
        painter.end()


class CompetencyRadar(_ThemedWidget):
    """Competency scores as a filled polygon over a labelled web.

    Below three axes a radar is meaningless, so the widget renders nothing and
    the caller is expected to fall back to bars.
    """

    MIN_AXES = 3

    def __init__(self, *, size: int = 260, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[tuple[str, float]] = []
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_entries(self, entries: list[tuple[str, float]]) -> None:
        self._entries = [(str(label), max(0.0, min(100.0, float(score)))) for label, score in entries]
        self.update()

    @property
    def renderable(self) -> bool:
        return len(self._entries) >= self.MIN_AXES

    def sizeHint(self):  # noqa: D102 - Qt override
        return super().sizeHint()

    def paintEvent(self, _event) -> None:
        if not self.renderable:
            return
        t = theme_manager.active_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        count = len(self._entries)
        center = QPointF(self.width() / 2, self.height() / 2 + 2)
        # Leave room for the axis labels drawn outside the web.
        radius = max(30.0, min(self.width(), self.height()) / 2 - 34)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ring in (0.25, 0.5, 0.75, 1.0):
            painter.setPen(QPen(QColor(t.grid_line if ring < 1.0 else t.border), 1))
            painter.drawPolygon(self._web(center, radius * ring, count))

        painter.setPen(QPen(QColor(t.grid_line), 1))
        for index in range(count):
            painter.drawLine(center, self._point(center, radius, index, count))

        polygon = QPolygonF(
            [
                self._point(center, radius * score / 100, index, count)
                for index, (_label, score) in enumerate(self._entries)
            ]
        )
        average = sum(score for _label, score in self._entries) / count
        line = QColor(band_color_for_score(t, average))
        fill = QColor(line)
        fill.setAlpha(64)
        painter.setBrush(fill)
        painter.setPen(QPen(line, 2))
        painter.drawPolygon(polygon)

        painter.setBrush(line)
        painter.setPen(Qt.PenStyle.NoPen)
        for point in polygon:
            painter.drawEllipse(point, 3.0, 3.0)

        label_font = QFont(self.font())
        label_font.setPointSize(max(7, t.size_chip))
        label_font.setBold(True)
        painter.setFont(label_font)
        for index, (label, score) in enumerate(self._entries):
            anchor = self._point(center, radius + 18, index, count)
            box = QRectF(anchor.x() - 58, anchor.y() - 11, 116, 22)
            painter.setPen(QColor(t.muted))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, f"{label} {int(round(score))}")
        painter.end()

    @staticmethod
    def _point(center: QPointF, radius: float, index: int, count: int) -> QPointF:
        # First axis points straight up; the rest go clockwise.
        angle = -math.pi / 2 + (2 * math.pi * index / count)
        return QPointF(center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle))

    def _web(self, center: QPointF, radius: float, count: int) -> QPolygonF:
        return QPolygonF([self._point(center, radius, index, count) for index in range(count)])


# -- chips -------------------------------------------------------------------


def chip(text: str, *, accent: bool = False, parent: QWidget | None = None) -> QLabel:
    """A small pill used for competency, stage, and engine tags."""
    label = QLabel(text, parent)
    label.setProperty("role", "chipAccent" if accent else "chip")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label
