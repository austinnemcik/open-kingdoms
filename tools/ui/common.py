"""Shared helpers for the UI asset generators (palette, SVG rasterising).

The palette here is the single source of truth for generated art; the same
tokens are mirrored in `client/ui/ui_colors.gd` and `docs/UI_STYLE.md`.

Requires: pip install resvg-py Pillow numpy
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "client" / "ui"

# Colour tokens (sRGB hex). Keep in sync with client/ui/ui_colors.gd.
OUTLINE = "#2b1a0f"
PALETTE = {
    "ink_900": "#1d1410",
    "ink_800": "#2b1a0f",
    "wood_800": "#33231a",
    "wood_700": "#463020",
    "wood_600": "#5d4229",
    "wood_500": "#7a5a36",
    "parchment_50": "#fbf3de",
    "parchment_100": "#f1e3c4",
    "parchment_200": "#e2cc9d",
    "parchment_300": "#c9ae7c",
    "gold_200": "#ffe58a",
    "gold_400": "#f2b632",
    "gold_600": "#c9861a",
    "gold_800": "#8a5a14",
    "cream": "#fff6e0",
    "verdigris_400": "#3f95a0",
    "verdigris_700": "#1f5f6e",
    "green_400": "#7cc94e",
    "green_700": "#3f8f2e",
    "crimson_400": "#e8604c",
    "crimson_700": "#a82f2a",
}


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """Linear blend of two hex colours; t=0 gives a, t=1 gives b."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return "#%02x%02x%02x" % (
        round(ra + (rb - ra) * t),
        round(ga + (gb - ga) * t),
        round(ba + (bb - ba) * t),
    )


def lighten(color: str, t: float) -> str:
    return mix(color, "#ffffff", t)


def darken(color: str, t: float) -> str:
    return mix(color, "#000000", t)


def lin_grad(grad_id: str, stops: list[tuple[float, str]], x2: float = 0, y2: float = 1, opacity: list[float] | None = None) -> str:
    """Vertical (by default) objectBoundingBox linear gradient."""
    parts = [f'<linearGradient id="{grad_id}" x1="0" y1="0" x2="{x2}" y2="{y2}">']
    for i, (offset, color) in enumerate(stops):
        op = "" if opacity is None else f' stop-opacity="{opacity[i]}"'
        parts.append(f'<stop offset="{offset}" stop-color="{color}"{op}/>')
    parts.append("</linearGradient>")
    return "".join(parts)


def svg_doc(width: int, height: int, body: str, defs: str = "") -> str:
    defs_block = f"<defs>{defs}</defs>" if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{defs_block}{body}</svg>\n'
    )


def rasterize(svg: str, scale: float = 1.0) -> Image.Image:
    data = resvg_py.svg_to_bytes(svg_string=svg, zoom=scale)
    return Image.open(io.BytesIO(bytes(data))).convert("RGBA")


def periodic_noise(size: int, sigma_x: float, sigma_y: float, seed: int) -> np.ndarray:
    """Seamlessly tileable gaussian-filtered noise, unit variance."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.fftfreq(size)[None, :]
    filt = np.exp(-2 * (np.pi**2) * ((fx * sigma_x) ** 2 + (fy * sigma_y) ** 2))
    out = np.fft.ifft2(np.fft.fft2(white) * filt).real
    return out / out.std()


def contact_sheet(images: list[tuple[str, Image.Image]], path: Path, cols: int, cell: int, bg: str = "#6f6253", scale: float = 1.0) -> None:
    """Debug sheet for visual review (not shipped)."""
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), bg)
    for i, (_, img) in enumerate(images):
        if scale != 1.0:
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        x = (i % cols) * cell + (cell - img.width) // 2
        y = (i // cols) * cell + (cell - img.height) // 2
        sheet.alpha_composite(img, (max(x, 0), max(y, 0)))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
