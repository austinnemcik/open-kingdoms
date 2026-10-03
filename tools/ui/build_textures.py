"""Generate the 9-slice textures used by `client/ui/theme/main_theme.tres`.

    python tools/ui/build_textures.py [--sheet out.png]

Every texture is authored as SVG below, rasterised with resvg and (for wood
and parchment) multiplied by seamless procedural grain. Output goes to
`client/ui/theme/textures/`. Slice margins live in
`client/ui/theme/build_theme.gd`; keep the two in sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

from common import OUTLINE, PALETTE as P, UI_DIR, contact_sheet, darken, lighten, lin_grad, mix, periodic_noise, rasterize, svg_doc

OUT = UI_DIR / "theme" / "textures"

GOLD_RIM = [(0, P["gold_200"]), (0.45, P["gold_400"]), (1, P["gold_800"])]
PEWTER_RIM = [(0, "#b5aca0"), (1, "#6f675e")]
BRONZE_RIM = [(0, "#a8834f"), (1, "#5d4229")]

# name -> (top, bottom, ledge)
BUTTON_COLOURS = {
    "neutral": ("#46a0ab", "#1f5f6e", "#123c47"),
    "primary": ("#86d255", "#3f8f2e", "#24601c"),
    "gold": ("#ffd866", "#e3961d", "#9a5c10"),
    "danger": ("#ec6a55", "#a82f2a", "#6e1b1b"),
}
DISABLED = ("#91877b", "#6b6157", "#4a423a")
SLOT_COLOURS = {
    "slot": ("#6f4e35", "#3a281c", "#22160e"),
    "slot_red": ("#e0594a", "#962824", "#5e1717"),
}


def rr(x: float, y: float, w: float, h: float, r: float, fill: str, extra: str = "") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" {extra}/>'


def blur_filter(filter_id: str, std: float) -> str:
    return (
        f'<filter id="{filter_id}" x="-50%" y="-50%" width="200%" height="200%">'
        f'<feGaussianBlur stdDeviation="{std}"/></filter>'
    )


def state_colours(base: tuple[str, str, str], state: str) -> tuple[str, str, str]:
    top, bot, ledge = base
    if state == "hover":
        return lighten(top, 0.16), lighten(bot, 0.12), ledge
    if state == "pressed":
        return darken(bot, 0.05), darken(top, 0.22), ledge
    return top, bot, ledge


def raised(w: int, h: int, radius: float, colours: tuple[str, str, str], rim: list, pressed: bool, ledge_h: int) -> str:
    """Chunky raised button face with a gold rim and a darker ledge below it."""
    top, bot, ledge = colours
    dy = ledge_h - 2 if pressed else 0
    face_h = h - 6 - ledge_h + (2 if pressed else 0)
    defs = (
        lin_grad("body", [(0, top), (1, bot)])
        + lin_grad("rim", rim)
        + lin_grad("gloss", [(0, "#ffffff"), (1, "#ffffff")], opacity=[0.05, 0.3] if pressed else [0.36, 0.03])
    )
    body = rr(1, 2 + dy, w - 2, h - 3 - dy, radius, OUTLINE)
    if not pressed:
        body += rr(3, 4 + ledge_h, w - 6, h - 7 - ledge_h, radius - 2, ledge)
    body += rr(3, 4 + dy, w - 6, face_h, radius - 2, "url(#rim)")
    body += rr(6, 7 + dy, w - 12, face_h - 6, radius - 5, "url(#body)")
    if pressed:
        body += rr(8, 9 + dy + (face_h - 6) * 0.55, w - 16, (face_h - 6) * 0.4, radius - 7, "url(#gloss)", 'opacity="0.35"')
        body += rr(7, 8 + dy, w - 14, face_h - 8, radius - 6, "none", 'stroke="#000" stroke-opacity="0.28" stroke-width="2.5"')
    else:
        body += rr(8, 9 + dy, w - 16, (face_h - 6) * 0.42, radius - 7, "url(#gloss)")
        body += rr(7, 8 + dy, w - 14, face_h - 8, radius - 6, "none", 'stroke="#000" stroke-opacity="0.16" stroke-width="2"')
    return svg_doc(w, h, body, defs)


def buttons() -> dict[str, str]:
    out = {}
    for name, base in BUTTON_COLOURS.items():
        for state in ("normal", "hover", "pressed"):
            out[f"button_{name}_{state}"] = raised(96, 72, 15, state_colours(base, state), GOLD_RIM, state == "pressed", 6)
    out["button_disabled"] = raised(96, 72, 15, DISABLED, PEWTER_RIM, False, 6)
    for name, base in SLOT_COLOURS.items():
        for state in ("normal", "hover", "pressed"):
            out[f"{name}_{state}"] = raised(80, 80, 20, state_colours(base, state), GOLD_RIM, state == "pressed", 5)
    out["slot_disabled"] = raised(80, 80, 20, DISABLED, PEWTER_RIM, False, 5)
    return out


def notched_rect(x0: float, y0: float, x1: float, y1: float, n: float) -> str:
    """Rectangle path with concave quarter-circle corners (classic frame hairline)."""
    return (
        f"M{x0 + n} {y0} L{x1 - n} {y0} A{n} {n} 0 0 0 {x1} {y0 + n} L{x1} {y1 - n} "
        f"A{n} {n} 0 0 0 {x1 - n} {y1} L{x0 + n} {y1} A{n} {n} 0 0 0 {x0} {y1 - n} "
        f"L{x0} {y0 + n} A{n} {n} 0 0 0 {x0 + n} {y0}Z"
    )


def diamond(cx: float, cy: float, r: float, fill: str, extra: str = "") -> str:
    return f'<path d="M{cx} {cy - r} L{cx + r} {cy} L{cx} {cy + r} L{cx - r} {cy}Z" fill="{fill}" {extra}/>'


def panel_wood(mask: bool = False) -> str:
    """Window frame: walnut body, gold band, notched hairline, corner studs. 16px shadow pad."""
    if mask:
        return svg_doc(256, 256, rr(25, 25, 206, 206, 10, "#fff"))
    defs = (
        lin_grad("gold", GOLD_RIM, x2=0.6)
        + lin_grad("body", [(0, "#4f3725"), (1, "#3b281b")])
        + blur_filter("blur", 7)
        + lin_grad("sheen", [(0, "#ffffff"), (1, "#ffffff")], opacity=[0.07, 0.0])
    )
    body = rr(18, 24, 220, 222, 18, "#000", 'opacity="0.5" filter="url(#blur)"')
    body += rr(16, 16, 224, 224, 18, OUTLINE)
    body += rr(18, 18, 220, 220, 16, "url(#gold)")
    body += rr(23, 23, 210, 210, 12, "#24160d")
    body += rr(25, 25, 206, 206, 10, "url(#body)")
    body += rr(25, 25, 206, 60, 10, "url(#sheen)")
    body += f'<path d="{notched_rect(33, 33, 223, 223, 9)}" fill="none" stroke="{P["gold_600"]}" stroke-width="1.5" stroke-opacity="0.85"/>'
    for cx in (33, 223):
        for cy in (33, 223):
            body += diamond(cx, cy, 5.5, "url(#gold)", f'stroke="{OUTLINE}" stroke-width="1.5"')
    return svg_doc(256, 256, body, defs)


def panel_parchment(mask: bool = False) -> str:
    if mask:
        return svg_doc(256, 256, rr(3, 3, 250, 250, 8, "#fff"))
    defs = blur_filter("blur", 7) + '<clipPath id="clip"><rect x="3" y="3" width="250" height="250" rx="8"/></clipPath>'
    body = rr(0, 0, 256, 256, 11, "#4a3220")
    body += rr(1.5, 1.5, 253, 253, 9.5, P["gold_800"])
    body += rr(3, 3, 250, 250, 8, P["parchment_100"])
    body += (
        '<g clip-path="url(#clip)"><rect x="0" y="0" width="256" height="256" rx="10" fill="none" '
        'stroke="#a37b45" stroke-opacity="0.6" stroke-width="16" filter="url(#blur)"/></g>'
    )
    body += rr(4, 4, 248, 248, 7, "none", 'stroke="#fffaf0" stroke-opacity="0.55" stroke-width="1.5"')
    return svg_doc(256, 256, body, defs)


def card() -> str:
    """Compact dark panel for HUD cards and popups. 8px shadow pad."""
    defs = lin_grad("gold", GOLD_RIM, x2=0.5) + lin_grad("body", [(0, "#4d3523"), (1, "#32221a")]) + blur_filter("blur", 4)
    body = rr(9, 12, 78, 78, 12, "#000", 'opacity="0.5" filter="url(#blur)"')
    body += rr(8, 8, 80, 80, 12, OUTLINE)
    body += rr(9.5, 9.5, 77, 77, 10.5, "url(#gold)")
    body += rr(12, 12, 72, 72, 8.5, "url(#body)", 'fill-opacity="0.97"')
    body += rr(12.75, 12.75, 70.5, 70.5, 8, "none", 'stroke="#000" stroke-opacity="0.35" stroke-width="1.5"')
    return svg_doc(96, 96, body, defs)


def chip() -> str:
    """Pill for HUD resource counters."""
    defs = lin_grad("gold", [(0, P["gold_400"]), (1, P["gold_800"])]) + lin_grad("body", [(0, "#4a3424"), (1, "#261911")])
    body = rr(0, 0, 64, 40, 20, OUTLINE, 'fill-opacity="0.95"')
    body += rr(1.5, 1.5, 61, 37, 18.5, "url(#gold)")
    body += rr(3, 3, 58, 34, 17, "url(#body)")
    body += rr(8, 4.5, 48, 9, 4.5, "#fff", 'opacity="0.07"')
    return svg_doc(64, 40, body, defs)


def tooltip() -> str:
    body = rr(0, 0, 48, 48, 9, OUTLINE)
    body += rr(1, 1, 46, 46, 8, P["gold_600"])
    body += rr(2.5, 2.5, 43, 43, 6.5, P["ink_900"])
    return svg_doc(48, 48, body)


def inset(light: bool) -> str:
    """Recessed well: dark on wood, tan on parchment."""
    defs = lin_grad("shade", [(0, "#000000"), (1, "#000000")], opacity=[0.3, 0.0])
    if light:
        body = rr(0.75, 0.75, 46.5, 46.5, 8, "#8a6a40", 'fill-opacity="0.16" stroke="#7a5a36" stroke-opacity="0.45" stroke-width="1.5"')
        body += rr(2, 2, 44, 8, 5, "url(#shade)", 'opacity="0.3"')
    else:
        body = rr(0, 0, 48, 48, 9, "#fff", 'fill-opacity="0.09"')
        body += rr(0, 0, 48, 47, 9, "#1a100a")
        body += rr(1.5, 1.5, 45, 44, 7.5, "#241710")
        body += rr(1.5, 1.5, 45, 12, 7, "url(#shade)")
    return svg_doc(48, 48, body, defs)


def title_plaque() -> str:
    """Crimson banner with pointed ends that straddles a window's top edge."""
    defs = lin_grad("gold", GOLD_RIM) + lin_grad("body", [(0, "#c5463a"), (1, "#84231f")]) + blur_filter("blur", 2.5)

    def hexagon(inset_px: float) -> str:
        i = inset_px
        k = i * 1.25
        return f"M{24} {4 + i} L{136} {4 + i} L{156 - k} 30 L{136} {56 - i} L{24} {56 - i} L{4 + k} 30Z"

    body = f'<path d="{hexagon(0)}" transform="translate(0 3)" fill="#000" opacity="0.45" filter="url(#blur)"/>'
    body += f'<path d="{hexagon(0)}" fill="{OUTLINE}" stroke="{OUTLINE}" stroke-width="3" stroke-linejoin="round"/>'
    body += f'<path d="{hexagon(1.5)}" fill="url(#gold)"/>'
    body += f'<path d="{hexagon(5)}" fill="url(#body)" stroke="#5a1512" stroke-width="1.5"/>'
    body += f'<path d="{hexagon(8.5)}" fill="none" stroke="{P["gold_200"]}" stroke-opacity="0.55" stroke-width="1.2"/>'
    return svg_doc(160, 64, body, defs)


def tab(kind: str) -> str:
    dy = 0 if kind == "selected" else 5
    if kind == "selected":
        rim, top, bot = GOLD_RIM, "#ffe9a3", "#f0b93c"
    elif kind == "hover":
        rim, top, bot = BRONZE_RIM, "#7d5a3c", "#5a3e28"
    elif kind == "disabled":
        rim, top, bot = PEWTER_RIM, "#6f665c", "#59514a"
    else:
        rim, top, bot = BRONZE_RIM, "#634630", "#432e1f"
    defs = lin_grad("rim", rim) + lin_grad("body", [(0, top), (1, bot)]) + lin_grad("gloss", [(0, "#fff"), (1, "#fff")], opacity=[0.3, 0.0])

    def shape(i: float, r: float) -> str:
        return f"M{i} 48 L{i} {dy + i + r} A{r} {r} 0 0 1 {i + r} {dy + i} L{96 - i - r} {dy + i} A{r} {r} 0 0 1 {96 - i} {dy + i + r} L{96 - i} 48Z"

    body = f'<path d="{shape(0, 14)}" fill="{OUTLINE}"/>'
    body += f'<path d="{shape(2, 12)}" fill="url(#rim)"/>'
    body += f'<path d="{shape(4.5, 9.5)}" fill="url(#body)"/>'
    body += rr(8, dy + 6.5, 80, 12, 6, "url(#gloss)")
    return svg_doc(96, 48, body, defs)


def progress_bg() -> str:
    defs = lin_grad("trough", [(0, "#0f0906"), (1, "#2c1d14")]) + lin_grad("rim", BRONZE_RIM)
    body = rr(0, 0, 48, 28, 14, OUTLINE)
    body += rr(1.5, 1.5, 45, 25, 12.5, "url(#rim)")
    body += rr(3.5, 3.5, 41, 21, 10.5, "url(#trough)")
    return svg_doc(48, 28, body, defs)


def progress_fill(top: str, bot: str, striped: bool) -> str:
    w = 52 if striped else 48
    defs = lin_grad("fill", [(0, top), (1, bot)]) + lin_grad("gloss", [(0, "#fff"), (1, "#fff")], opacity=[0.5, 0.1])
    defs += f'<clipPath id="clip"><rect x="4" y="4" width="{w - 8}" height="20" rx="10"/></clipPath>'
    body = rr(4, 4, w - 8, 20, 10, "url(#fill)")
    if striped:
        stripes = ""
        for k in range(-3, 4):
            x0 = k * 24
            stripes += f'<path d="M{x0} 24 L{x0 + 12} 24 L{x0 + 32} 4 L{x0 + 20} 4Z" fill="#fff" opacity="0.2"/>'
        body += f'<g clip-path="url(#clip)">{stripes}</g>'
    body += rr(4.75, 4.75, w - 9.5, 18.5, 9.25, "none", f'stroke="{darken(bot, 0.35)}" stroke-width="1.5"')
    body += rr(8, 6, w - 16, 5, 2.5, "url(#gloss)")
    return svg_doc(w, 28, body, defs)


def line_edit(kind: str) -> str:
    fill = P["parchment_200"] if kind == "readonly" else P["parchment_50"]
    defs = lin_grad("shade", [(0, "#6b4a2a"), (1, "#6b4a2a")], opacity=[0.32, 0.0])
    body = rr(0, 0, 48, 44, 9, OUTLINE if kind != "focus" else P["gold_800"])
    body += rr(1.5, 1.5, 45, 41, 7.5, P["gold_400"] if kind == "focus" else P["wood_500"])
    inset_px = 4 if kind == "focus" else 3
    body += rr(inset_px, inset_px, 48 - 2 * inset_px, 44 - 2 * inset_px, 9 - inset_px, fill)
    body += rr(inset_px, inset_px, 48 - 2 * inset_px, 9, 5, "url(#shade)")
    return svg_doc(48, 44, body, defs)


def check(kind: str) -> str:
    radio = kind.startswith("radio")
    checked = kind.endswith("_checked")
    r = 12 if radio else 6
    defs = lin_grad("on", [(0, "#86d255"), (1, "#3f8f2e")]) + lin_grad("off", [(0, P["parchment_200"]), (1, P["parchment_50"])])
    body = rr(1, 1, 26, 26, r + 1, OUTLINE)
    body += rr(2.5, 2.5, 23, 23, r - 0.5, P["gold_400"] if checked else P["wood_500"])
    body += rr(4.5, 4.5, 19, 19, max(r - 2.5, 2), "url(#on)" if checked else "url(#off)")
    if checked and radio:
        body += f'<circle cx="14" cy="14" r="5.5" fill="{OUTLINE}"/><circle cx="14" cy="14" r="4" fill="{P["cream"]}"/>'
    elif checked:
        d = "M8.5 14.5 L12.5 18.5 L20 9.5"
        body += f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
        body += f'<path d="{d}" fill="none" stroke="{P["cream"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    return svg_doc(28, 28, body, defs)


def arrow_down() -> str:
    d = "M5 8 L10 13 L15 8"
    body = f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
    body += f'<path d="{d}" fill="none" stroke="{P["cream"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    return svg_doc(20, 20, body)


def divider(ink: bool) -> str:
    colour = P["wood_500"] if ink else P["gold_400"]
    defs = (
        '<linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{colour}" stop-opacity="0"/><stop offset="0.5" stop-color="{colour}"/>'
        f'<stop offset="1" stop-color="{colour}" stop-opacity="0"/></linearGradient>'
    )
    body = rr(0, 7.25, 256, 1.5, 0, "url(#fade)")
    body += diamond(128, 8, 6.5, colour, f'stroke="{OUTLINE}" stroke-width="1.5"')
    body += diamond(112, 8, 3, colour) + diamond(144, 8, 3, colour)
    return svg_doc(256, 16, body, defs)


def portrait_frame() -> str:
    defs = (
        lin_grad("gold", GOLD_RIM, x2=0.5)
        + '<radialGradient id="bg" cx="0.5" cy="0.35" r="0.75"><stop offset="0" stop-color="#4b93b8"/>'
        '<stop offset="1" stop-color="#173650"/></radialGradient>'
        + blur_filter("blur", 3)
    )
    body = '<circle cx="56" cy="59" r="50" fill="#000" opacity="0.45" filter="url(#blur)"/>'
    body += f'<circle cx="56" cy="56" r="52" fill="{OUTLINE}"/><circle cx="56" cy="56" r="50" fill="url(#gold)"/>'
    body += f'<circle cx="56" cy="56" r="43" fill="{OUTLINE}"/><circle cx="56" cy="56" r="41.5" fill="url(#bg)"/>'
    body += '<circle cx="56" cy="56" r="46.5" fill="none" stroke="#fff" stroke-opacity="0.35" stroke-width="1.2"/>'
    return svg_doc(112, 112, body, defs)


def level_badge() -> str:
    """Small gold disc for level numbers and notification counts."""
    defs = lin_grad("gold", GOLD_RIM, x2=0.5) + lin_grad("body", [(0, "#c5463a"), (1, "#84231f")])
    body = f'<circle cx="20" cy="20" r="19" fill="{OUTLINE}"/><circle cx="20" cy="20" r="17.5" fill="url(#gold)"/>'
    body += '<circle cx="20" cy="20" r="14" fill="url(#body)" stroke="#5a1512" stroke-width="1.2"/>'
    return svg_doc(40, 40, body, defs)


def focus_ring() -> str:
    defs = blur_filter("blur", 2)
    ring = f'<rect x="4" y="4" width="40" height="40" rx="13" fill="none" stroke="{P["gold_200"]}" stroke-width="2.5"/>'
    body = f'<g filter="url(#blur)" opacity="0.8">{ring}</g>{ring}'
    return svg_doc(48, 48, body, defs)


def apply_grain(img: Image.Image, mask_svg: str, tile: int, offset: int, layers: list[tuple[float, float, float, int]]) -> Image.Image:
    """Multiply seamless noise into the masked body so the 9-slice centre can tile."""
    arr = np.asarray(img).astype(np.float64)
    mask = np.asarray(rasterize(mask_svg))[..., 3] / 255.0
    ys, xs = np.mgrid[0 : img.height, 0 : img.width]
    total = np.zeros((img.height, img.width))
    for sigma_x, sigma_y, amp, seed in layers:
        noise = periodic_noise(tile, sigma_x, sigma_y, seed)
        total += amp * noise[(ys - offset) % tile, (xs - offset) % tile]
    arr[..., :3] = np.clip(arr[..., :3] * (1 + (total * mask)[..., None]), 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def build() -> list[tuple[str, Image.Image]]:
    svgs: dict[str, str] = buttons()
    svgs.update(
        {
            "card": card(),
            "chip": chip(),
            "tooltip": tooltip(),
            "inset_dark": inset(False),
            "inset_light": inset(True),
            "title_plaque": title_plaque(),
            "tab_selected": tab("selected"),
            "tab_unselected": tab("unselected"),
            "tab_hover": tab("hover"),
            "tab_disabled": tab("disabled"),
            "progress_bg": progress_bg(),
            "progress_fill": progress_fill("#9be063", "#3f8f2e", False),
            "progress_fill_gold": progress_fill("#ffe58a", "#e3961d", False),
            "progress_fill_timer": progress_fill("#5cc3e6", "#226f9b", True),
            "lineedit_normal": line_edit("normal"),
            "lineedit_focus": line_edit("focus"),
            "lineedit_readonly": line_edit("readonly"),
            "check_unchecked": check("check_unchecked"),
            "check_checked": check("check_checked"),
            "radio_unchecked": check("radio_unchecked"),
            "radio_checked": check("radio_checked"),
            "arrow_down": arrow_down(),
            "divider": divider(False),
            "divider_ink": divider(True),
            "portrait_frame": portrait_frame(),
            "level_badge": level_badge(),
            "focus_ring": focus_ring(),
        }
    )
    images = [(name, rasterize(svg)) for name, svg in svgs.items()]
    images.append(("panel_wood", apply_grain(rasterize(panel_wood()), panel_wood(True), 144, 56, [(16, 1.1, 0.055, 11), (40, 5, 0.035, 12)])))
    images.append(("panel_parchment", apply_grain(rasterize(panel_parchment()), panel_parchment(True), 192, 32, [(14, 14, 0.028, 21), (0.8, 0.8, 0.014, 22)])))
    images.append(("empty", Image.new("RGBA", (4, 4), (0, 0, 0, 0))))
    return images


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    images = build()
    for name, img in images:
        img.save(OUT / f"{name}.png")
    print(f"wrote {len(images)} textures to {OUT}")
    if "--sheet" in sys.argv:
        sheet = Path(sys.argv[sys.argv.index("--sheet") + 1])
        contact_sheet(images, sheet, cols=7, cell=270, bg="#7c6f60")
        print(f"sheet: {sheet}")


if __name__ == "__main__":
    main()
