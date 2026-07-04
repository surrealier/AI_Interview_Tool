from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True, slots=True)
class UiTheme:
    name: str
    bootstrap_theme: str
    app_bg: str
    surface: str
    surface_alt: str
    ink: str
    muted: str
    border: str
    primary: str
    primary_dark: str
    accent: str
    success: str
    warning: str
    danger: str
    video_bg: str
    font: str = "Segoe UI"
    mono_font: str = "Cascadia Mono"
    surface_deep: str = "#070a12"
    selection: str = "#17223a"
    glow: str = "#9be7ff"


LIGHT_THEME = UiTheme(
    name="light",
    bootstrap_theme="darkly",
    app_bg="#070a12",
    surface="#0e1422",
    surface_alt="#151d2d",
    ink="#f6f8fc",
    muted="#95a3b8",
    border="#263248",
    primary="#5ea1ff",
    primary_dark="#2f6bdb",
    accent="#52dec2",
    success="#36d399",
    warning="#f5bd42",
    danger="#ff6b6b",
    video_bg="#050814",
    surface_deep="#090e19",
    selection="#16284b",
    glow="#a3f2ff",
)


def apply_ttk_styles(root: tk.Misc, theme: UiTheme = LIGHT_THEME) -> bool:
    """Apply product UI styles, using ttkbootstrap when available."""
    using_bootstrap = _try_bootstrap_theme(root, theme)
    style = ttk.Style(root)
    if not using_bootstrap:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    style.configure(
        ".",
        font=(theme.font, 10),
        background=theme.app_bg,
        foreground=theme.ink,
        bordercolor=theme.border,
        lightcolor=theme.border,
        darkcolor=theme.border,
        troughcolor=theme.surface_alt,
        fieldbackground=theme.surface_alt,
        selectbackground=theme.selection,
        selectforeground=theme.ink,
    )
    style.configure("App.TFrame", background=theme.app_bg)
    style.configure("Hero.TFrame", background=theme.surface_deep)
    style.configure("Card.TFrame", background=theme.surface, relief="solid", borderwidth=1)
    style.configure("SubtleCard.TFrame", background=theme.surface_alt, relief="solid", borderwidth=1)
    style.configure("Surface.TFrame", background=theme.surface)
    style.configure("Workspace.TFrame", background=theme.app_bg)
    style.configure("Stage.TFrame", background=theme.surface_deep)
    style.configure("Rail.TFrame", background=theme.surface_deep)
    style.configure("Choice.TFrame", background=theme.surface_alt, relief="solid", borderwidth=1)
    style.configure("ChoiceSelected.TFrame", background=theme.selection, relief="solid", borderwidth=1)
    style.configure("Signal.TFrame", background=theme.surface_deep)

    style.configure("HeroTitle.TLabel", background=theme.surface_deep, foreground=theme.ink, font=(theme.font, 25, "bold"))
    style.configure("HeroSubtitle.TLabel", background=theme.surface_deep, foreground=theme.muted, font=(theme.font, 10))
    style.configure("Title.TLabel", background=theme.surface, foreground=theme.ink, font=(theme.font, 13, "bold"))
    style.configure("Section.TLabel", background=theme.surface, foreground=theme.ink, font=(theme.font, 10, "bold"))
    style.configure("Subtitle.TLabel", background=theme.surface, foreground=theme.muted, font=(theme.font, 9))
    style.configure("Muted.TLabel", background=theme.surface, foreground=theme.muted, font=(theme.font, 9))
    style.configure("Kicker.TLabel", background=theme.surface, foreground=theme.primary, font=(theme.font, 9, "bold"))
    style.configure("Question.TLabel", background=theme.surface_alt, foreground=theme.ink, font=(theme.font, 15))
    style.configure("MetricLabel.TLabel", background=theme.surface_alt, foreground=theme.muted, font=(theme.font, 9, "bold"))
    style.configure("MetricValue.TLabel", background=theme.surface_alt, foreground=theme.ink, font=(theme.mono_font, 18, "bold"))
    style.configure("Status.TLabel", background=theme.surface_alt, foreground=theme.ink, font=(theme.font, 9, "bold"))
    style.configure("Success.TLabel", background=theme.surface_alt, foreground=theme.success, font=(theme.font, 9, "bold"))
    style.configure("Warning.TLabel", background=theme.surface_alt, foreground=theme.warning, font=(theme.font, 9, "bold"))
    style.configure("Danger.TLabel", background=theme.surface_alt, foreground=theme.danger, font=(theme.font, 9, "bold"))
    style.configure("RailTitle.TLabel", background=theme.surface_deep, foreground=theme.ink, font=(theme.font, 12, "bold"))
    style.configure("RailMuted.TLabel", background=theme.surface_deep, foreground=theme.muted, font=(theme.font, 9))
    style.configure("RailAccent.TLabel", background=theme.surface_deep, foreground=theme.accent, font=(theme.font, 9, "bold"))
    style.configure("ChoiceTitle.TLabel", background=theme.surface_alt, foreground=theme.ink, font=(theme.font, 12, "bold"))
    style.configure("ChoiceBody.TLabel", background=theme.surface_alt, foreground=theme.muted, font=(theme.font, 9))
    style.configure("ChoiceSelectedTitle.TLabel", background=theme.selection, foreground=theme.ink, font=(theme.font, 12, "bold"))
    style.configure("ChoiceSelectedBody.TLabel", background=theme.selection, foreground=theme.glow, font=(theme.font, 9))
    style.configure("QuestionPanelLabel.TLabel", background=theme.selection, foreground=theme.accent, font=(theme.font, 9, "bold"))
    style.configure("QuestionPanel.TLabel", background=theme.selection, foreground=theme.ink, font=(theme.font, 15))

    style.configure("Primary.TButton", font=(theme.font, 10, "bold"), padding=(16, 8))
    style.configure("Secondary.TButton", font=(theme.font, 10, "bold"), padding=(12, 7))
    style.configure("Tool.TButton", padding=(10, 6))
    style.configure("Ghost.TButton", padding=(10, 6))
    style.configure("Danger.TButton", font=(theme.font, 10, "bold"), padding=(12, 7))

    style.map(
        "Primary.TButton",
        background=[("active", theme.primary_dark), ("pressed", theme.primary_dark)],
        foreground=[("disabled", theme.muted)],
    )
    style.map(
        "Secondary.TButton",
        background=[("active", theme.selection), ("pressed", theme.selection)],
        foreground=[("disabled", theme.muted)],
    )
    style.configure("TNotebook", background=theme.surface, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(12, 6), font=(theme.font, 9, "bold"))
    style.configure("TCombobox", padding=(6, 4), fieldbackground=theme.surface_alt, foreground=theme.ink)
    style.configure("TEntry", padding=(6, 4), fieldbackground=theme.surface_alt, foreground=theme.ink)
    style.configure("TRadiobutton", background=theme.surface, foreground=theme.ink)
    style.configure("TCheckbutton", background=theme.surface, foreground=theme.ink)
    return using_bootstrap


def _try_bootstrap_theme(root: tk.Misc, theme: UiTheme) -> bool:
    try:
        from ttkbootstrap import Style as BootstrapStyle
    except ImportError:
        return False
    try:
        BootstrapStyle(master=root, theme=theme.bootstrap_theme)
    except Exception:
        return False
    return True
