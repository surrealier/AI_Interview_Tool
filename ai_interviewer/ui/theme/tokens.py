from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tokens:
    """Design tokens for one theme. All UI colors, spacing, and type sizes
    come from here; nothing in ui/ may hardcode a hex value."""

    name: str
    is_dark: bool

    # Color roles (names kept from the old UiTheme for mechanical porting).
    app_bg: str
    surface: str
    surface_alt: str
    surface_deep: str
    ink: str
    muted: str
    border: str
    primary: str
    primary_dark: str
    primary_contrast: str
    accent: str
    success: str
    warning: str
    danger: str
    selection: str
    glow: str
    video_bg: str
    focus_ring: str
    grid_line: str

    # Typography (point sizes; Qt scales points with DPI).
    font: str = "Segoe UI"
    mono_font: str = "Cascadia Mono"
    size_display: int = 24
    size_title: int = 13
    size_section: int = 10
    size_body: int = 10
    size_caption: int = 9
    size_metric: int = 18
    size_question: int = 14

    # Geometry
    radius_sm: int = 4
    radius_md: int = 8
    radius_lg: int = 12
    # Spacing scale in px; index with sp[1]..sp[6].
    sp: tuple[int, ...] = (0, 4, 8, 12, 16, 24, 32)

    @property
    def font_stack(self) -> str:
        return f'"{self.font}", "Malgun Gothic", "Arial"'

    @property
    def mono_stack(self) -> str:
        return f'"{self.mono_font}", "Consolas", "Courier New"'


DARK = Tokens(
    name="dark",
    is_dark=True,
    app_bg="#070a12",
    surface="#0e1422",
    surface_alt="#151d2d",
    surface_deep="#090e19",
    ink="#f6f8fc",
    muted="#95a3b8",
    border="#263248",
    primary="#5ea1ff",
    primary_dark="#2f6bdb",
    primary_contrast="#071018",
    accent="#52dec2",
    success="#36d399",
    warning="#f5bd42",
    danger="#ff6b6b",
    selection="#16284b",
    glow="#a3f2ff",
    video_bg="#050814",
    focus_ring="#5ea1ff",
    grid_line="#111a2b",
)

LIGHT = Tokens(
    name="light",
    is_dark=False,
    app_bg="#f3f5f9",
    surface="#ffffff",
    surface_alt="#eef1f6",
    surface_deep="#e7ebf3",
    ink="#17202f",
    muted="#5a6a81",
    border="#d5dce8",
    primary="#2f6bdb",
    primary_dark="#2456b8",
    primary_contrast="#ffffff",
    accent="#0d9488",
    success="#15803d",
    warning="#b45309",
    danger="#dc2626",
    selection="#dce8ff",
    glow="#0e7490",
    video_bg="#0b1220",
    focus_ring="#2f6bdb",
    grid_line="#dfe5ee",
)

THEMES: dict[str, Tokens] = {"dark": DARK, "light": LIGHT}
