from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from ai_interviewer.config import AppConfig
from ai_interviewer.ui import icons
from ai_interviewer.ui.theme.qss import build_qss
from ai_interviewer.ui.theme.tokens import DARK, LIGHT, Tokens


logger = logging.getLogger(__name__)

THEME_MODES = ("system", "light", "dark")

_manager: "ThemeManager | None" = None


def manager() -> "ThemeManager":
    if _manager is None:
        raise RuntimeError("ThemeManager has not been created yet.")
    return _manager


def active_tokens() -> Tokens:
    """Current theme tokens; safe default for headless/unit-test contexts."""
    if _manager is None:
        return DARK
    return _manager.tokens


class ThemeManager(QObject):
    """Owns the theme mode (system|light|dark), generates and applies the
    palette + stylesheet, and notifies token consumers on change."""

    themeChanged = Signal(object)  # emits the active Tokens

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        global _manager
        self._config = config
        self._style_set = False
        if config.ui_theme_mode not in THEME_MODES:
            config.ui_theme_mode = "system"
        self.tokens: Tokens = self._resolve_tokens()
        _manager = self
        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def mode(self) -> str:
        return self._config.ui_theme_mode

    def set_mode(self, mode: str) -> None:
        if mode not in THEME_MODES or mode == self._config.ui_theme_mode:
            return
        self._config.ui_theme_mode = mode
        try:
            self._config.save()
        except OSError:
            logger.exception("Could not persist the theme mode.")
        self.apply()

    def apply(self, app: QApplication | None = None) -> None:
        app = app or QApplication.instance()
        if app is None:
            return
        if not self._style_set:
            app.setStyle("Fusion")
            self._style_set = True
        self.tokens = self._resolve_tokens()
        icons.clear_cache()
        app.setPalette(_palette_from(self.tokens))
        app.setStyleSheet(build_qss(self.tokens))
        self.themeChanged.emit(self.tokens)

    def _resolve_tokens(self) -> Tokens:
        mode = self._config.ui_theme_mode
        if mode == "light":
            return LIGHT
        if mode == "dark":
            return DARK
        return DARK if _system_prefers_dark() else LIGHT

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self._config.ui_theme_mode == "system":
            self.apply()


def _system_prefers_dark() -> bool:
    hints = QGuiApplication.styleHints()
    if hints is None:
        return True
    return hints.colorScheme() == Qt.ColorScheme.Dark


def _palette_from(t: Tokens) -> QPalette:
    """QSS cannot reach every corner (native dialogs, menus in some styles,
    disabled roles); the palette keeps those consistent with the tokens."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: t.app_bg,
        QPalette.ColorRole.WindowText: t.ink,
        QPalette.ColorRole.Base: t.surface_alt,
        QPalette.ColorRole.AlternateBase: t.surface,
        QPalette.ColorRole.Text: t.ink,
        QPalette.ColorRole.Button: t.surface_alt,
        QPalette.ColorRole.ButtonText: t.ink,
        QPalette.ColorRole.Highlight: t.selection,
        QPalette.ColorRole.HighlightedText: t.ink,
        QPalette.ColorRole.ToolTipBase: t.surface_deep,
        QPalette.ColorRole.ToolTipText: t.ink,
        QPalette.ColorRole.PlaceholderText: t.muted,
        QPalette.ColorRole.Link: t.primary,
        QPalette.ColorRole.BrightText: t.glow,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.Text, QColor(t.muted))
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, QColor(t.muted))
    palette.setColor(disabled, QPalette.ColorRole.WindowText, QColor(t.muted))
    return palette
