from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ai_interviewer.i18n import tr


class ChoiceCard(QFrame):
    """Selectable option tile (wizard choices): accent bar + kicker + title +
    description, full keyboard/mouse activation, QSS-driven states."""

    clicked = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        *,
        selected: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("selected", "true" if selected else "false")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 13, 14, 13)
        outer.setSpacing(12)

        self._accent = QFrame(self)
        self._accent.setProperty("accentBar", "true")
        self._accent.setFixedWidth(4)
        outer.addWidget(self._accent)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        self._kicker = QLabel(tr("common.selected") if selected else tr("common.choose"), self)
        self._kicker.setProperty("role", "choiceBody")
        body.addWidget(self._kicker)

        self._title = QLabel(title, self)
        self._title.setProperty("role", "choiceTitle")
        self._title.setWordWrap(True)
        body.addSpacing(2)
        body.addWidget(self._title)

        self._description = QLabel(description, self)
        self._description.setProperty("role", "choiceBody")
        self._description.setWordWrap(True)
        body.addSpacing(8)
        body.addWidget(self._description)
        body.addStretch(1)

    def set_selected(self, selected: bool) -> None:
        if (self.property("selected") == "true") == selected:
            return
        self.setProperty("selected", "true" if selected else "false")
        self._kicker.setText(tr("common.selected") if selected else tr("common.choose"))
        for widget in (self, self._accent, self._kicker, self._title, self._description):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def is_selected(self) -> bool:
        return self.property("selected") == "true"

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)
