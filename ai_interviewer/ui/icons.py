from __future__ import annotations

import logging
import tempfile
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ai_interviewer.config import resource_base_dir


logger = logging.getLogger(__name__)

_pixmap_cache: dict[tuple[str, str, int, float], QPixmap] = {}
_svg_file_cache: dict[tuple[str, str], str] = {}
_tmp_dir: Path | None = None


def _icons_dir() -> Path:
    return resource_base_dir() / "assets" / "icons"


@lru_cache(maxsize=None)
def _svg_text(name: str) -> str:
    path = _icons_dir() / f"{name}.svg"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Icon asset missing: %s", path)
        # 1px invisible placeholder keeps callers alive if an asset is absent.
        return '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"></svg>'


def _tinted_text(name: str, color: str) -> str:
    return _svg_text(name).replace("currentColor", color)


def _device_pixel_ratio() -> float:
    screen = QGuiApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen is not None else 1.0


def pixmap(name: str, color: str, size: int = 18, dpr: float | None = None) -> QPixmap:
    if dpr is None:
        dpr = _device_pixel_ratio()
    key = (name, color, size, dpr)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached
    renderer = QSvgRenderer(QByteArray(_tinted_text(name, color).encode("utf-8")))
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    px.setDevicePixelRatio(dpr)
    _pixmap_cache[key] = px
    return px


def icon(name: str, color: str, size: int = 18, disabled_color: str | None = None) -> QIcon:
    result = QIcon()
    result.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal)
    if disabled_color:
        result.addPixmap(pixmap(name, disabled_color, size), QIcon.Mode.Disabled)
    return result


def tinted_svg_url(name: str, color: str) -> str:
    """Write a tinted copy of the SVG to a per-process temp dir and return a
    forward-slash path for use inside QSS url()."""
    global _tmp_dir
    key = (name, color)
    cached = _svg_file_cache.get(key)
    if cached is not None:
        return cached
    if _tmp_dir is None:
        _tmp_dir = Path(tempfile.mkdtemp(prefix="aiinterview-qss-"))
    safe_color = color.lstrip("#")
    target = _tmp_dir / f"{name}-{safe_color}.svg"
    target.write_text(_tinted_text(name, color), encoding="utf-8")
    url = target.as_posix()
    _svg_file_cache[key] = url
    return url


def clear_cache() -> None:
    """Drop tinted pixmaps (called on theme switch; tinted files are keyed
    by color so they never go stale)."""
    _pixmap_cache.clear()
