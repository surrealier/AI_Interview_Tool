from __future__ import annotations

import pytest

from ai_interviewer.ui.theme.tokens import DARK, LIGHT, THEMES


def _srgb_to_linear(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(foreground: str, background: str) -> float:
    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=["light", "dark"])
def test_body_text_meets_wcag_aa(tokens) -> None:
    assert contrast_ratio(tokens.ink, tokens.surface) >= 4.5
    assert contrast_ratio(tokens.ink, tokens.app_bg) >= 4.5
    assert contrast_ratio(tokens.ink, tokens.surface_alt) >= 4.5
    assert contrast_ratio(tokens.primary_contrast, tokens.primary) >= 4.5


def test_palettes_differ() -> None:
    assert LIGHT.app_bg != DARK.app_bg
    assert LIGHT.is_dark is False
    assert DARK.is_dark is True
    assert set(THEMES) == {"light", "dark"}


def test_build_qss_produces_full_sheets(tmp_path) -> None:
    from ai_interviewer.ui.theme.qss import build_qss

    def fake_icon_url(name: str, color: str) -> str:
        return (tmp_path / f"{name}.svg").as_posix()

    sheets = {}
    for name, tokens in THEMES.items():
        sheet = build_qss(tokens, icon_url=fake_icon_url)
        sheets[name] = sheet
        assert sheet.count("{") == sheet.count("}")
        for selector in (
            "QPushButton[kind=\"primary\"]",
            "QFrame[variant=\"card\"]",
            "QComboBox",
            "QTabBar::tab:selected",
            "QScrollBar::handle:vertical",
            "ChoiceCard[selected=\"true\"]",
            ":disabled",
            ":hover",
            ":focus",
        ):
            assert selector in sheet, f"{selector} missing from {name} sheet"
    assert sheets["light"] != sheets["dark"]
