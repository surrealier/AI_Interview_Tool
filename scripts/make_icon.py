"""Generate assets/icon.ico (interviewer microphone mark) with Pillow.

Run once when the mark changes: python scripts/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BG = (14, 20, 34, 255)  # ui_theme surface
PRIMARY = (94, 161, 255, 255)  # ui_theme primary
ACCENT = (82, 222, 194, 255)  # ui_theme accent
SIZES = (256, 128, 64, 48, 32, 16)


def draw_mark(size: int) -> Image.Image:
    scale = 8  # supersample for smooth edges
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def s(value: float) -> float:
        return value * canvas / 256

    # rounded-square badge
    draw.rounded_rectangle((s(8), s(8), s(248), s(248)), radius=s(56), fill=BG)

    # microphone capsule
    draw.rounded_rectangle((s(96), s(52), s(160), s(150)), radius=s(32), fill=PRIMARY)
    # mic cradle arc
    draw.arc((s(72), s(74), s(184), s(178)), start=20, end=160, fill=ACCENT, width=int(s(14)))
    # stem and base
    draw.rectangle((s(121), s(178), s(135), s(204)), fill=ACCENT)
    draw.rounded_rectangle((s(92), s(200), s(164), s(216)), radius=s(8), fill=ACCENT)

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    out_path = Path(__file__).resolve().parents[1] / "assets" / "icon.ico"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    images = [draw_mark(size) for size in SIZES]
    images[0].save(out_path, format="ICO", sizes=[(size, size) for size in SIZES], append_images=images[1:])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
