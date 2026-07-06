from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QToolButton, QWidget

from ai_interviewer.ui import icons
from ai_interviewer.ui.theme import manager as theme_manager


def _icon_color(kind: str, tokens) -> str:
    if kind == "primary":
        return tokens.primary_contrast
    if kind == "ghost":
        return tokens.muted
    if kind == "danger":
        return tokens.danger
    return tokens.ink


class IconButton(QPushButton):
    """QPushButton with a theme-aware SVG icon and a QSS `kind` variant."""

    def __init__(
        self,
        text: str = "",
        *,
        icon_name: str | None = None,
        kind: str = "secondary",
        icon_size: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._icon_name = icon_name
        self._kind = kind
        self._icon_px = icon_size
        self.setProperty("kind", kind)
        if icon_name:
            self.setIconSize(QSize(icon_size, icon_size))
            self._refresh_icon()
        self._subscribe_theme()

    def set_icon_name(self, icon_name: str | None) -> None:
        self._icon_name = icon_name
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        if not self._icon_name:
            self.setIcon(QIcon())
            return
        tokens = theme_manager.active_tokens()
        self.setIcon(
            icons.icon(
                self._icon_name,
                _icon_color(self._kind, tokens),
                self._icon_px,
                disabled_color=tokens.muted,
            )
        )

    def _subscribe_theme(self) -> None:
        # Bound-method connections are auto-disconnected by Qt when the
        # receiver widget is destroyed; no manual teardown needed.
        try:
            mgr = theme_manager.manager()
        except RuntimeError:
            return
        mgr.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, _tokens) -> None:
        self._refresh_icon()


class SegButton(QToolButton):
    """Checkable segment button (theme mode selector etc.)."""

    def __init__(self, text: str, *, icon_name: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setProperty("seg", "true")
        self._icon_name = icon_name
        if icon_name:
            self.setIconSize(QSize(14, 14))
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self._refresh_icon()
        self._subscribe_theme()

    def _refresh_icon(self) -> None:
        if not self._icon_name:
            return
        tokens = theme_manager.active_tokens()
        self.setIcon(icons.icon(self._icon_name, tokens.ink, 14, disabled_color=tokens.muted))

    def _subscribe_theme(self) -> None:
        try:
            mgr = theme_manager.manager()
        except RuntimeError:
            return
        mgr.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, _tokens) -> None:
        self._refresh_icon()
