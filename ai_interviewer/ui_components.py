from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from ai_interviewer.i18n import tr
from ai_interviewer.ui_theme import LIGHT_THEME, UiTheme


def card(parent: tk.Widget, padding: int | tuple[int, ...] = 14, style: str = "Card.TFrame") -> ttk.Frame:
    frame = ttk.Frame(parent, padding=padding, style=style)
    return frame


def section_header(parent: tk.Widget, title: str, subtitle: str | None = None) -> ttk.Frame:
    header = ttk.Frame(parent, style="Surface.TFrame")
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text=title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
    if subtitle:
        ttk.Label(header, text=subtitle, style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
    return header


def metric_tile(parent: tk.Widget, label: str, variable: tk.StringVar, column: int) -> ttk.Frame:
    tile = ttk.Frame(parent, padding=(12, 9), style="SubtleCard.TFrame")
    tile.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
    ttk.Label(tile, text=label.upper(), style="MetricLabel.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(tile, textvariable=variable, style="MetricValue.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
    return tile


def status_row(parent: tk.Widget, label: str, variable: tk.StringVar, row: int, style: str = "Status.TLabel") -> ttk.Label:
    ttk.Label(parent, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 8, 0))
    value = ttk.Label(parent, textvariable=variable, style=style, wraplength=330, justify="left")
    value.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=(0 if row == 0 else 8, 0))
    return value


def set_text_content(widget: tk.Text, content: str) -> None:
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
    widget.edit_modified(False)


class SignalCanvas(tk.Canvas):
    """A lightweight audio-studio visual that works without external assets."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        theme: UiTheme = LIGHT_THEME,
        height: int = 120,
        animated: bool = False,
        compact: bool = False,
    ) -> None:
        super().__init__(
            parent,
            height=height,
            bg=theme.surface_deep,
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self.theme = theme
        self.compact = compact
        self._phase = 0.0
        self._running = False
        self.bind("<Configure>", lambda _event: self._draw())
        if animated:
            self.start()
        else:
            self.after_idle(self._draw)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        if not self._running:
            return
        self._phase += 0.28
        self._draw()
        self.after(70, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.create_rectangle(0, 0, width, height, fill=self.theme.surface_deep, outline="")

        grid = 36 if not self.compact else 28
        for x in range(0, width, grid):
            self.create_line(x, 0, x, height, fill="#111a2b")
        for y in range(0, height, grid):
            self.create_line(0, y, width, y, fill="#111a2b")

        mid = height * 0.56
        self.create_line(0, mid, width, mid, fill=self.theme.border)
        bars = 58 if not self.compact else 34
        gap = 4 if not self.compact else 3
        bar_width = max(3, int((width - gap * (bars + 1)) / bars))
        start_x = max(12, int((width - (bar_width + gap) * bars) / 2))
        for index in range(bars):
            x0 = start_x + index * (bar_width + gap)
            wave_a = math.sin(index * 0.43 + self._phase)
            wave_b = math.sin(index * 0.17 - self._phase * 0.7)
            amp = (wave_a + wave_b + 2) / 4
            bar_height = 10 + amp * (height * (0.58 if not self.compact else 0.46))
            y0 = mid - bar_height / 2
            y1 = mid + bar_height / 2
            color = self.theme.accent if index % 9 == 0 else self.theme.primary
            if index % 5 == 0:
                color = self.theme.glow
            self.create_rectangle(x0, y0, x0 + bar_width, y1, fill=color, outline="")

        if not self.compact:
            self.create_text(22, 22, text="VOICE SIGNAL", fill=self.theme.muted, anchor="w", font=(self.theme.font, 8, "bold"))
            self.create_text(
                width - 22,
                height - 20,
                text="LOCAL SESSION",
                fill=self.theme.accent,
                anchor="e",
                font=(self.theme.font, 8, "bold"),
            )


def selectable_tile(
    parent: tk.Widget,
    *,
    title: str,
    description: str,
    selected: bool,
    command,
    theme: UiTheme = LIGHT_THEME,
    row: int,
    column: int,
    columnspan: int = 1,
    padx: tuple[int, int] | None = None,
    pady: tuple[int, int] | None = None,
) -> ttk.Frame:
    style = "ChoiceSelected.TFrame" if selected else "Choice.TFrame"
    title_style = "ChoiceSelectedTitle.TLabel" if selected else "ChoiceTitle.TLabel"
    body_style = "ChoiceSelectedBody.TLabel" if selected else "ChoiceBody.TLabel"
    tile = ttk.Frame(parent, padding=(14, 13), style=style, cursor="hand2")
    tile.grid(
        row=row,
        column=column,
        columnspan=columnspan,
        sticky="nsew",
        padx=padx if padx is not None else (0 if column == 0 else 10, 0),
        pady=pady if pady is not None else (0 if row == 0 else 10, 0),
    )
    tile.columnconfigure(1, weight=1)

    accent = tk.Frame(tile, width=4, bg=theme.accent if selected else theme.border)
    accent.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 12))
    ttk.Label(tile, text=(tr("common.selected") if selected else tr("common.choose")), style=body_style).grid(row=0, column=1, sticky="w")
    ttk.Label(tile, text=title, style=title_style, wraplength=280, justify="left").grid(row=1, column=1, sticky="ew", pady=(2, 0))
    ttk.Label(tile, text=description, style=body_style, wraplength=280, justify="left").grid(row=2, column=1, sticky="ew", pady=(8, 0))

    def bind_all(widget: tk.Widget) -> None:
        widget.bind("<Button-1>", lambda _event: command())
        widget.bind("<Return>", lambda _event: command())
        widget.bind("<space>", lambda _event: command())
        for child in widget.winfo_children():
            bind_all(child)

    bind_all(tile)
    return tile


def step_rail(parent: tk.Widget, labels: tuple[str, ...], current: int, theme: UiTheme = LIGHT_THEME) -> tk.Canvas:
    height = max(300, len(labels) * 46)
    canvas = tk.Canvas(parent, height=height, bg=theme.surface_deep, bd=0, highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    width = 230
    x = 24
    y0 = 26
    gap = 42
    canvas.create_line(x, y0, x, y0 + gap * (len(labels) - 1), fill=theme.border, width=2)
    for index, label in enumerate(labels):
        y = y0 + gap * index
        active = index == current
        done = index < current
        fill = theme.accent if active else theme.primary if done else theme.surface_alt
        outline = theme.glow if active else theme.border
        canvas.create_oval(x - 7, y - 7, x + 7, y + 7, fill=fill, outline=outline, width=2)
        canvas.create_text(
            x + 20,
            y,
            text=label,
            fill=theme.ink if active else theme.muted,
            anchor="w",
            font=(theme.font, 9, "bold" if active else "normal"),
            width=width - 44,
        )
    return canvas
