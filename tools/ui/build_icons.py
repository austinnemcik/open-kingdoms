"""Generate the UI icon set: SVG sources and 128px PNGs.

    python tools/ui/build_icons.py [--sheet out.png]

Icons are authored below as SVG on a 128x128 canvas using a shared kit
(outline colour and width, material gradients, highlight strokes, one drop
shadow) so the whole set stays consistent. Output:
`client/ui/icons/svg/<name>.svg` (scalable source) and
`client/ui/icons/<name>.png` (128px, imported by Godot).

Style rules are documented in docs/UI_STYLE.md ("Icons").
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from common import OUTLINE as O, UI_DIR, contact_sheet, lin_grad, rasterize

OUT = UI_DIR / "icons"
SW = 5  # outline width at 128px

# Material gradients, lit from above: id -> (top, bottom)
MATERIALS = {
    "gold": ("#ffe58a", "#e39a1c"),
    "wheat": ("#ffdc6e", "#e59c22"),
    "wood": ("#cf9255", "#93592a"),
    "bark": ("#8a5630", "#58331b"),
    "stone": ("#cfd6dc", "#8a949f"),
    "steel": ("#f2f6f8", "#9aacba"),
    "red": ("#f06a54", "#a82f2a"),
    "green": ("#9be063", "#3f8f2e"),
    "blue": ("#74c6e6", "#2b78a6"),
    "cream": ("#fffaec", "#ecd9ae"),
    "parch": ("#f7ebcd", "#dcc592"),
    "dark": ("#5a4334", "#33231a"),
    "skin": ("#f6d3ae", "#dba87a"),
}

DEFS = "".join(lin_grad(f"m-{name}", [(0, top), (1, bot)]) for name, (top, bot) in MATERIALS.items()) + (
    '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
    '<feDropShadow dx="0" dy="3" stdDeviation="2.2" flood-color="#000" flood-opacity="0.4"/></filter>'
)


def m(name: str) -> str:
    return f"url(#m-{name})"


def p(d: str, fill: str = "none", stroke: str = O, sw: float = SW, extra: str = "") -> str:
    return (
        f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
        f'stroke-linejoin="round" stroke-linecap="round" {extra}/>'
    )


def flat(d: str, fill: str, opacity: float = 1.0) -> str:
    """Unoutlined shape for facets, shading and inner detail."""
    return f'<path d="{d}" fill="{fill}" opacity="{opacity}"/>'


def hl(d: str, sw: float = 4, opacity: float = 0.55, color: str = "#fff") -> str:
    """Highlight (or shade) stroke."""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"/>'


def ol(d: str, color: str, w: float) -> str:
    """Outlined line: a coloured stroke sitting on a wider outline stroke."""
    return p(d, sw=w + 2 * SW - 2) + p(d, stroke=color, sw=w)


def c(cx: float, cy: float, r: float, fill: str, stroke: str = O, sw: float = SW, extra: str = "") -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def dot(cx: float, cy: float, r: float, fill: str, opacity: float = 1.0) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{opacity}"/>'


def r(x: float, y: float, w: float, h: float, rx: float, fill: str, stroke: str = O, sw: float = SW, extra: str = "") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{sw}" stroke-linejoin="round" {extra}/>'
    )


def g(content: str, transform: str) -> str:
    return f'<g transform="{transform}">{content}</g>'


def gear_path(cx: float, cy: float, r_out: float, r_in: float, teeth: int, duty: float = 0.5) -> str:
    pts = []
    step = 2 * math.pi / teeth
    for i in range(teeth):
        a = i * step
        half = step * duty / 2
        for ang, rad in ((a - half * 1.25, r_in), (a - half * 0.75, r_out), (a + half * 0.75, r_out), (a + half * 1.25, r_in)):
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def saw_path(cx: float, cy: float, r_out: float, r_in: float, teeth: int) -> str:
    pts = []
    step = 2 * math.pi / teeth
    for i in range(teeth):
        a = i * step
        pts.append((cx + r_in * math.cos(a), cy + r_in * math.sin(a)))
        pts.append((cx + r_out * math.cos(a + step * 0.75), cy + r_out * math.sin(a + step * 0.75)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def star_path(cx: float, cy: float, r_out: float, r_in: float, points: int = 5) -> str:
    pts = []
    for i in range(points * 2):
        a = -math.pi / 2 + i * math.pi / points
        rad = r_out if i % 2 == 0 else r_in
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def sparkle(cx: float, cy: float, s: float) -> str:
    k = s * 0.22
    d = f"M{cx} {cy - s} L{cx + k} {cy - k} L{cx + s} {cy} L{cx + k} {cy + k} L{cx} {cy + s} L{cx - k} {cy + k} L{cx - s} {cy} L{cx - k} {cy - k}Z"
    return flat(d, "#fffdf2")


def crenel_path(x: float, y: float, w: float, h: float, merlons: int, depth: float = 9) -> str:
    """Rectangle whose top edge is a battlement."""
    seg = w / (merlons * 2 - 1)
    d = f"M{x} {y + h} L{x} {y}"
    for i in range(merlons * 2 - 1):
        x1 = x + (i + 1) * seg
        if i % 2 == 0:
            d += f" L{x1:.1f} {y}"
            if i < merlons * 2 - 2:
                d += f" L{x1:.1f} {y + depth}"
        else:
            d += f" L{x1:.1f} {y + depth} L{x1:.1f} {y}"
    return d + f" L{x + w} {y + h}Z"


def sword(angle: float) -> str:
    blade = p("M57 16 L64 0 L71 16 L71 82 L57 82Z", m("steel")) + hl("M64 14 L64 78", 2.5, 0.5, "#6f8494")
    guard = r(44, 80, 40, 10, 4, m("gold"))
    grip = r(59.5, 90, 9, 17, 3, m("bark"), sw=4)
    pommel = c(64, 111, 6.5, m("gold"), sw=4)
    return g(blade + grip + guard + pommel, f"rotate({angle} 64 64)")


def hammer() -> str:
    handle = r(57, 40, 14, 78, 6, m("wood")) + hl("M61 50 L61 108", 3, 0.35)
    head = r(26, 14, 76, 36, 8, m("steel")) + flat("M30 40 L98 40 L98 44 Q98 47 94 47 L34 47 Q30 47 30 44Z", "#6f8494", 0.55)
    head += hl("M34 22 L94 22", 4, 0.8)
    return handle + head


# --- resources ---------------------------------------------------------------


def icon_food() -> str:
    def ear(angle: float) -> str:
        s = ol("M64 110 L64 44", "#d9a02e", 4)
        for i in range(4):
            y = 70 - i * 14
            for side in (-1, 1):
                s += g(f'<ellipse cx="{64 + side * 10}" cy="{y}" rx="7" ry="11.5" fill="{m("wheat")}" stroke="{O}" stroke-width="4"/>', f"rotate({side * 28} {64 + side * 10} {y})")
        s += f'<ellipse cx="64" cy="19" rx="7.5" ry="12" fill="{m("wheat")}" stroke="{O}" stroke-width="4"/>'
        s += hl("M62 13 L62 22", 2.5, 0.7)
        return g(s, f"rotate({angle} 64 112)")

    tie = r(50, 92, 28, 13, 5, m("red"), sw=4) + hl("M55 96 L73 96", 2.5, 0.5)
    return ear(-30) + ear(30) + ear(0) + tie


def icon_wood() -> str:
    def log(cx: float, cy: float) -> str:
        s = c(cx, cy, 25, m("bark"))
        s += c(cx, cy, 17.5, "#f3d39b", stroke="#b47a3f", sw=3)
        s += f'<circle cx="{cx}" cy="{cy}" r="9.5" fill="none" stroke="#cf9e5f" stroke-width="2.5"/>'
        s += dot(cx, cy, 2.5, "#b47a3f")
        s += hl(f"M{cx - 20} {cy - 9} A22 22 0 0 1 {cx - 4} {cy - 21.5}", 3, 0.3)
        return s

    return log(38, 86) + log(90, 86) + log(64, 43)


def icon_stone() -> str:
    big = p("M20 98 L30 54 L60 30 L96 42 L114 78 L106 102Z", "#a7b1ba")
    big += flat("M30 54 L60 30 L96 42 L72 62Z", "#e3e8ec") + flat("M96 42 L114 78 L106 102 L72 62Z", "#7c8792")
    big += hl("M30 54 L72 62 L106 102 M72 62 L96 42", 2, 0.5, "#5f6a75")
    big += p("M20 98 L30 54 L60 30 L96 42 L114 78 L106 102Z")
    small = p("M10 106 L20 84 L44 78 L58 96 L52 112 L16 114Z", "#b4bdc5")
    small += flat("M20 84 L44 78 L58 96 L34 96Z", "#e9edf0") + hl("M20 84 L34 96 L58 96 M34 96 L30 113", 2, 0.5, "#5f6a75")
    small += p("M10 106 L20 84 L44 78 L58 96 L52 112 L16 114Z")
    return big + small


def icon_gold() -> str:
    def ingot(x: float, y: float) -> str:
        w, h = 54, 32
        s = p(f"M{x + 10} {y} L{x + w - 10} {y} L{x + w} {y + h} L{x} {y + h}Z", m("gold"))
        s += flat(f"M{x + 14} {y + 5} L{x + w - 14} {y + 5} L{x + w - 11} {y + 14} L{x + 11} {y + 14}Z", "#fff3b8", 0.9)
        s += flat(f"M{x + 6} {y + h - 8} L{x + w - 6} {y + h - 8} L{x + w - 3.5} {y + h - 2.5} L{x + 3.5} {y + h - 2.5}Z", "#b8720f", 0.55)
        return s

    return ingot(8, 78) + ingot(66, 78) + ingot(37, 42) + sparkle(96, 34, 13) + sparkle(24, 60, 8)


def icon_time() -> str:
    s = c(64, 66, 47, m("gold")) + c(64, 66, 35, m("cream"), stroke="#8a5a14", sw=3.5)
    for i in range(12):
        a = i * math.pi / 6
        r0, r1 = (25, 30.5) if i % 3 == 0 else (28, 30.5)
        s += hl(f"M{64 + r0 * math.sin(a):.1f} {66 - r0 * math.cos(a):.1f} L{64 + r1 * math.sin(a):.1f} {66 - r1 * math.cos(a):.1f}", 3, 1, "#8a5a14")
    s += hl("M64 66 L64 43 M64 66 L80 76", 6, 1, O) + dot(64, 66, 5, "#c0392f")
    s += hl("M28 50 A40 40 0 0 1 56 23", 4, 0.6)
    return s


def icon_speedup() -> str:
    glass = "M30 26 L82 26 C82 48 64 54 62 64 C64 74 82 80 82 102 L30 102 C30 80 48 74 50 64 C48 54 30 48 30 26Z"
    s = p(glass, "#dff3fb")
    s += flat("M38 40 L74 40 C70 50 60 55 56 60 C52 55 42 50 38 40Z", "#f2b632")
    s += flat("M36 100 C40 86 50 82 56 82 C62 82 72 86 76 100Z", "#f2b632")
    s += hl("M56 62 L56 82", 3, 1, "#f2b632") + hl("M38 34 C40 44 46 50 50 54", 3, 0.8) + p(glass)
    s += r(22, 12, 68, 15, 6, m("wood")) + r(22, 101, 68, 15, 6, m("wood")) + hl("M30 18 L82 18", 3, 0.4)
    for x in (84, 100):
        s += p(f"M{x} 46 L{x + 16} 64 L{x} 82", sw=15) + p(f"M{x} 46 L{x + 16} 64 L{x} 82", stroke="#86d255", sw=7)
    return s


def icon_power() -> str:
    s = p("M64 10 L110 24 C110 66 96 98 64 118 C32 98 18 66 18 24Z", m("gold"))
    s += p("M64 23 L98 33.5 C97 64 87 88 64 103 C41 88 31 64 30 33.5Z", m("red"), stroke="#6e1b1b", sw=3)
    s += flat("M64 23 L98 33.5 C97 64 87 88 64 103Z", "#000", 0.12)
    s += p("M72 30 L46 68 L62 68 L55 98 L84 56 L67 56Z", "#fff0a8", sw=4)
    s += hl("M27 30 L60 19", 3.5, 0.7)
    return s


# --- troops ------------------------------------------------------------------


def icon_infantry() -> str:
    s = p("M60 24 C58 4 88 0 106 14 C118 24 118 42 110 56 C108 40 98 28 80 24Z", m("red"))
    s += hl("M70 14 C82 10 96 14 104 24", 3.5, 0.45)
    helm = "M24 102 L24 60 C24 34 42 20 64 20 C86 20 104 34 104 60 L104 102 C92 112 78 112 70 108 L64 100 L58 108 C50 112 36 112 24 102Z"
    s += p(helm, m("steel"))
    s += flat("M92 40 C100 46 102 54 102 60 L102 101 C98 104 94 106 90 107Z", "#5f7686", 0.35)
    s += p("M38 58 L90 58 L90 72 L71 72 L71 96 L57 96 L57 72 L38 72Z", "#2a1c14", sw=4)
    s += hl("M64 24 L64 54", 4, 0.6, "#7d92a2") + hl("M32 56 C32 40 42 30 54 27", 4, 0.85)
    for x, y in ((31, 84), (31, 98), (97, 84), (97, 98)):
        s += dot(x, y, 2.6, "#6f8494")
    return s


def icon_cavalry() -> str:
    mane = p("M60 20 C84 14 112 40 114 78 C114 92 112 102 108 112 L92 112 C96 84 88 50 60 20Z", m("dark"))
    head = p("M38 112 C40 94 48 84 58 74 C50 79 42 85 34 83 C27 87 20 83 18 76 C16 69 22 63 28 55 C36 44 42 34 52 28 L48 10 L66 22 C88 26 102 48 104 76 C105 92 102 102 100 112Z", m("wood"))
    s = mane + head
    s += flat("M66 22 C88 26 102 48 104 76 C105 92 102 102 100 112 L84 112 C90 84 88 48 66 22Z", "#000", 0.14)
    s += hl("M50 22 L52 31", 3, 0.5) + hl("M34 56 C40 47 46 39 54 34", 3.5, 0.45)
    s += dot(48, 50, 5, O) + dot(49.5, 48.5, 1.6, "#fff") + dot(26, 73, 2.6, O)
    s += hl("M22 66 L44 78 M44 78 L58 62 M40 40 L58 62", 3.5, 1, "#c0392f")
    return s


def icon_archer() -> str:
    bow = ol("M38 12 C100 26 100 102 38 116", "#b9783c", 7)
    string = hl("M38 12 L26 64 L38 116", 2.5, 1, "#fff6e0")
    string = p("M38 12 L26 64 L38 116", sw=5) + string
    shaft = ol("M22 64 L100 64", "#e8c58e", 4)
    head = p("M96 50 L122 64 L96 78 L102 64Z", m("steel"), sw=4)
    feathers = p("M8 52 L24 52 L32 64 L24 76 L8 76 L16 64Z", m("red"), sw=4)
    return g(bow + string + shaft + head + feathers, "rotate(-40 64 64)")


def icon_siege() -> str:
    s = ol("M36 86 L60 44 M92 86 L68 44", "#93592a", 7)
    s += ol("M22 80 L100 26", "#cf9255", 8)
    s += r(8, 68, 26, 24, 5, m("stone")) + hl("M13 74 L28 74", 3, 0.6)
    s += c(102, 22, 12, m("stone")) + hl("M95 17 A9 9 0 0 1 104 13", 3, 0.7)
    s += c(64, 46, 6, m("gold"), sw=4)
    s += r(12, 84, 104, 13, 5, m("wood")) + hl("M18 88 L110 88", 3, 0.35)
    for cx in (32, 96):
        s += c(cx, 102, 14, m("bark")) + c(cx, 102, 5, m("gold"), sw=3.5)
    return s


# --- buildings ---------------------------------------------------------------


def window(x: float, y: float, w: float = 10, h: float = 16) -> str:
    return p(f"M{x} {y + h} L{x} {y + w / 2} A{w / 2} {w / 2} 0 0 1 {x + w} {y + w / 2} L{x + w} {y + h}Z", "#27506b", sw=3)


def icon_city_hall() -> str:
    s = ""
    for x in (14, 80):
        s += r(x + 4, 66, 26, 46, 2, m("cream"))
        s += p(f"M{x - 2} 68 L{x + 17} 42 L{x + 36} 68Z", m("blue")) + window(x + 12, 80)
    s += ol("M64 22 L64 6", "#8a5630", 3) + p("M66 5 L86 11 L66 18Z", m("red"), sw=3.5)
    s += r(44, 46, 40, 66, 2, m("cream")) + flat("M70 48 L82 48 L82 110 L70 110Z", "#b8935a", 0.25)
    s += p("M36 48 L64 14 L92 48Z", m("blue")) + hl("M48 40 L62 23", 3.5, 0.5)
    s += p("M54 112 L54 94 A10 10 0 0 1 74 94 L74 112Z", m("bark"), sw=4) + window(59, 58)
    s += r(8, 108, 112, 8, 3, m("stone"), sw=4)
    return s


def icon_farm() -> str:
    s = p("M22 112 L22 66 L38 40 L64 26 L90 40 L106 66 L106 112Z", m("red"))
    s += flat("M82 44 L90 40 L106 66 L106 112 L92 112 L92 66Z", "#000", 0.14)
    s += ol("M16 68 L34 38 L64 20 L94 38 L112 68", "#f7ebcd", 6)
    s += r(46, 72, 36, 40, 2, m("cream"), sw=4) + hl("M48 74 L80 110 M80 74 L48 110", 3.5, 1, "#b0483c")
    s += r(46, 72, 36, 40, 2, "none", sw=4)
    s += c(64, 50, 8.5, "#3a2418", stroke="#f7ebcd", sw=4)
    return s


def icon_lumber_mill() -> str:
    s = p(saw_path(64, 58, 48, 37, 14), m("steel"), sw=4.5)
    s += c(64, 58, 27, "none", stroke="#8ea0ae", sw=2.5) + c(64, 58, 9, m("gold"), sw=4)
    s += hl("M32 44 A36 36 0 0 1 56 24", 4, 0.8)
    s += r(8, 74, 104, 38, 16, m("bark"))
    s += hl("M22 84 L70 84 M30 98 L84 98", 3, 0.3, "#f3d39b")
    s += f'<ellipse cx="98" cy="93" rx="15" ry="19" fill="#f3d39b" stroke="{O}" stroke-width="{SW}"/>'
    s += f'<ellipse cx="98" cy="93" rx="7" ry="10" fill="none" stroke="#cf9e5f" stroke-width="2.5"/>'
    return s


def icon_quarry() -> str:
    s = p("M14 74 L32 56 L112 56 L112 96 L94 114 L14 114Z", "#a7b1ba")
    s += flat("M14 74 L32 56 L112 56 L94 74Z", "#e3e8ec") + flat("M94 74 L112 56 L112 96 L94 114Z", "#7c8792")
    s += hl("M14 74 L94 74 L94 114 M54 74 L54 114 M14 94 L54 94", 2, 0.55, "#5f6a75")
    s += p("M14 74 L32 56 L112 56 L112 96 L94 114 L14 114Z")
    s += ol("M26 98 L84 28", "#cf9255", 7)
    s += p("M52 12 C76 6 106 20 116 50 C102 36 88 32 78 36 C74 28 64 22 52 12Z", m("steel"))
    s += hl("M62 14 C80 14 96 22 106 36", 3, 0.8)
    return s


def icon_goldmine() -> str:
    s = p("M8 112 L20 62 L44 30 L82 24 L108 50 L120 112Z", "#9a8f85")
    s += flat("M20 62 L44 30 L82 24 L66 52Z", "#c9c0b6") + flat("M82 24 L108 50 L120 112 L96 112 L66 52Z", "#756b62")
    s += p("M8 112 L20 62 L44 30 L82 24 L108 50 L120 112Z")
    s += p("M42 112 L42 78 L86 78 L86 112Z", "#1c110b", sw=0.1)
    s += ol("M40 112 L40 72 M88 112 L88 72", "#b9783c", 7) + ol("M34 70 L94 70", "#cf9255", 8)
    s += p("M48 112 L56 96 L66 102 L72 92 L80 112Z", m("gold"), sw=4) + sparkle(72, 90, 9)
    for cx, cy in ((26, 88), (102, 78), (62, 42)):
        s += p(f"M{cx} {cy - 7} L{cx + 7} {cy} L{cx} {cy + 7} L{cx - 7} {cy}Z", m("gold"), sw=3.5)
    return s


def icon_storehouse() -> str:
    s = r(12, 44, 66, 68, 5, m("wood"))
    s += r(22, 54, 46, 48, 2, "#b9783c", stroke="#7a4a24", sw=3) + hl("M24 100 L66 56", 7, 1, "#7a4a24") + hl("M24 100 L66 56", 3.5, 1, "#cf9255")
    s += hl("M18 49 L72 49", 3, 0.4)
    s += p("M70 60 L110 60 C118 76 118 96 110 112 L70 112 C62 96 62 76 70 60Z", m("bark"))
    s += hl("M66 73 L114 73 M66 99 L114 99", 6, 1, O) + hl("M66 73 L114 73 M66 99 L114 99", 3, 1, "#b9c6d0")
    s += hl("M78 66 C74 78 74 94 78 106", 3, 0.25)
    s += p("M26 44 C22 26 34 14 48 16 C64 16 70 30 64 44Z", m("parch")) + hl("M40 16 L46 26 L52 16", 3, 1, "#93592a")
    return s


def icon_barracks() -> str:
    s = sword(-45) + sword(45)
    s += c(64, 72, 26, m("gold")) + c(64, 72, 18, m("red"), stroke="#6e1b1b", sw=3)
    s += c(64, 72, 6.5, m("gold"), sw=3.5) + hl("M44 62 A22 22 0 0 1 58 51", 3.5, 0.7)
    return s


def icon_archery_range() -> str:
    s = ol("M34 100 L24 118 M84 100 L94 118", "#93592a", 6)
    s += c(60, 66, 46, m("red")) + c(60, 66, 34, m("cream"), sw=3) + c(60, 66, 22.5, m("red"), sw=3) + c(60, 66, 10.5, m("gold"), sw=3)
    s += hl("M22 52 A40 40 0 0 1 46 28", 4, 0.45)
    s += ol("M62 64 L104 22", "#e8c58e", 4)
    s += p("M96 14 L112 8 L120 16 L114 32 L104 30 L98 24Z", m("green"), sw=4) + hl("M100 28 L114 14", 2.5, 1, O)
    return s


def icon_stable() -> str:
    d = "M28 110 C6 62 26 14 64 14 C102 14 122 62 100 110 L76 110 C92 70 88 40 64 40 C40 40 36 70 52 110Z"
    s = p(d, m("steel")) + hl("M26 62 C28 40 40 26 58 22", 4, 0.8)
    s += flat("M100 110 C122 62 102 14 64 14 C96 22 108 66 90 110Z", "#5f7686", 0.35) + p(d)
    for x, y in ((38, 94), (30, 70), (36, 44), (90, 94), (98, 70), (92, 44)):
        s += dot(x, y, 3.6, "#3d4c58")
    s += r(22, 104, 36, 12, 4, m("gold"), sw=4) + r(70, 104, 36, 12, 4, m("gold"), sw=4)
    return s


def icon_siege_workshop() -> str:
    s = p(gear_path(54, 56, 46, 34, 8), m("stone")) + c(54, 56, 14, "#3a2a20", sw=4)
    s += hl("M28 40 A30 30 0 0 1 46 27", 4, 0.7)
    s += g(hammer(), "translate(36 34) scale(0.72) rotate(38 64 64)")
    return s


def icon_hospital() -> str:
    s = r(24, 56, 80, 56, 3, m("cream")) + flat("M84 58 L102 58 L102 110 L84 110Z", "#b8935a", 0.22)
    s += p("M12 60 L64 18 L116 60Z", m("green")) + hl("M34 50 L62 28", 4, 0.45)
    s += p("M56 66 L72 66 L72 76 L82 76 L82 92 L72 92 L72 102 L56 102 L56 92 L46 92 L46 76 L56 76Z", m("green"), sw=4)
    s += r(16, 108, 96, 8, 3, m("stone"), sw=4)
    return s


def icon_academy() -> str:
    s = r(18, 52, 92, 48, 2, "#b9a57c", sw=0.1)
    for x in (22, 45, 69, 92):
        s += r(x, 56, 14, 44, 3, m("cream"), sw=4) + hl(f"M{x + 9.5} 60 L{x + 9.5} 96", 2.5, 0.35, "#93592a")
    s += r(14, 46, 100, 11, 3, m("cream"), sw=4)
    s += p("M10 47 L64 14 L118 47Z", m("blue")) + c(64, 35, 5.5, m("gold"), sw=3) + hl("M32 40 L60 23", 3.5, 0.45)
    s += r(12, 98, 104, 9, 3, m("stone"), sw=4) + r(5, 106, 118, 10, 3, m("stone"), sw=4)
    return s


# --- interface glyphs --------------------------------------------------------


def icon_upgrade() -> str:
    d = "M64 10 L114 62 L86 62 L86 114 L42 114 L42 62 L14 62Z"
    return p(d, m("green")) + hl("M64 22 L30 56 M50 62 L50 106", 4.5, 0.5)


def icon_build() -> str:
    return g(hammer(), "rotate(38 64 64)")


def icon_research() -> str:
    s = p("M8 34 L8 108 L56 108 C60 114 68 114 72 108 L120 108 L120 34Z", m("blue"))
    s += p("M64 36 C48 24 28 22 14 26 L14 98 C28 94 48 94 64 104Z", m("cream"), sw=4)
    s += p("M64 36 C80 24 100 22 114 26 L114 98 C100 94 80 94 64 104Z", m("cream"), sw=4)
    s += flat("M64 36 C70 31 76 28 82 26 L82 96 C76 97 70 100 64 104Z", "#93592a", 0.16)
    s += hl("M24 42 C34 40 46 42 54 46 M24 56 C34 54 46 56 54 60 M24 70 C34 68 46 70 54 74", 3, 0.65, "#93592a")
    s += hl("M76 46 C84 42 94 40 104 42 M76 60 C84 56 94 54 104 56 M76 74 C84 70 94 68 104 70", 3, 0.65, "#93592a")
    s += p("M90 22 L104 22 L104 52 L97 45 L90 52Z", m("red"), sw=3.5)
    return s


def icon_commander() -> str:
    s = p("M14 118 C14 90 38 78 64 78 C90 78 114 90 114 118Z", m("blue"))
    s += p("M50 80 L64 98 L78 80", m("gold"), sw=4)
    s += c(64, 56, 23, m("skin"))
    s += p("M36 42 L34 14 L50 27 L64 8 L78 27 L94 14 L92 42Z", m("gold")) + hl("M41 37 L87 37", 3, 0.6, "#b8720f")
    s += dot(64, 30, 4.5, "#c0392f") + dot(46, 31, 3, "#2b78a6") + dot(82, 31, 3, "#2b78a6")
    return s


def icon_alliance() -> str:
    s = p("M28 22 L100 22 L100 112 L64 92 L28 112Z", m("blue"))
    s += p("M36 28 L92 28 L92 99 L64 83.5 L36 99Z", "none", stroke="#ffe58a", sw=2.5)
    s += p(star_path(64, 56, 19, 8), m("gold"), sw=3.5)
    s += r(14, 12, 100, 13, 6, m("wood")) + c(14, 18.5, 7.5, m("gold"), sw=4) + c(114, 18.5, 7.5, m("gold"), sw=4)
    return s


def icon_mail() -> str:
    s = r(10, 28, 108, 76, 9, m("parch"))
    s += flat("M14 100 L52 66 L76 66 L114 100Z", "#c9ae7c", 0.5)
    s += hl("M13 100 L52 66 M115 100 L76 66", 3.5, 0.8, "#93592a")
    s += p("M12 32 L64 76 L116 32", m("cream"), sw=4.5, extra='fill-opacity="1"')
    s += r(10, 28, 108, 76, 9, "none")
    s += c(64, 74, 14, m("red"), sw=4) + c(64, 74, 7.5, "none", stroke="#ffb3a3", sw=2.5)
    return s


def icon_map() -> str:
    s = p("M10 30 L44 18 L84 32 L118 20 L118 98 L84 110 L44 96 L10 108Z", m("parch"))
    s += flat("M44 18 L84 32 L84 110 L44 96Z", "#b8935a", 0.25)
    s += hl("M44 18 L44 96 M84 32 L84 110", 2.5, 0.6, "#93592a")
    s += hl("M20 88 C30 76 36 80 44 70 C54 58 60 74 70 66", 3.5, 1, "#3f95a0")
    s += f'<path d="M24 50 L40 58 M52 84 L72 92" fill="none" stroke="#93592a" stroke-width="3.5" stroke-dasharray="5 6" stroke-linecap="round"/>'
    s += p("M10 30 L44 18 L84 32 L118 20 L118 98 L84 110 L44 96 L10 108Z")
    s += p("M90 74 C76 58 74 50 74 44 C74 34 81 27 90 27 C99 27 106 34 106 44 C106 50 104 58 90 74Z", m("red"), sw=4) + dot(90, 43, 6, "#fff6e0")
    return s


def icon_city() -> str:
    s = p(crenel_path(26, 56, 76, 56, 5), m("stone"))
    s += p("M52 112 L52 90 A12 12 0 0 1 76 90 L76 112Z", m("bark"), sw=4) + hl("M64 80 L64 110", 2.5, 0.6, O)
    for x in (8, 88):
        s += p(crenel_path(x, 34, 32, 78, 3), m("stone")) + window(x + 11, 58)
        s += hl(f"M{x + 6} 50 L{x + 6} 104", 3, 0.5)
    s += ol("M24 34 L24 14", "#8a5630", 3) + p("M26 12 L44 18 L26 25Z", m("red"), sw=3.5)
    s += ol("M104 34 L104 14", "#8a5630", 3) + p("M106 12 L124 18 L106 25Z", m("red"), sw=3.5)
    return s


def icon_settings() -> str:
    s = p(gear_path(64, 64, 52, 39, 8), m("steel")) + c(64, 64, 26, "none", stroke="#8ea0ae", sw=3)
    s += c(64, 64, 15, "#3a2a20", sw=4.5) + hl("M34 46 A35 35 0 0 1 56 30", 4.5, 0.85)
    return s


def icon_close() -> str:
    d = "M32 32 L96 96 M96 32 L32 96"
    return p(d, sw=30) + p(d, stroke="#fff6e0", sw=19) + hl("M30 36 L40 26 M88 26 L98 36", 4, 0.0)


def icon_back() -> str:
    d = "M12 64 L62 16 L62 44 L116 44 L116 84 L62 84 L62 112Z"
    return p(d, m("gold")) + hl("M24 64 L56 32 M62 51 L108 51", 4.5, 0.6)


def icon_info() -> str:
    s = c(64, 64, 50, m("blue")) + c(64, 64, 41, "none", stroke="#fff", sw=2.5, extra='opacity="0.35"')
    s += c(64, 37, 8.5, "#fff6e0", sw=4) + r(55.5, 53, 17, 44, 7, "#fff6e0", sw=4)
    return s


def icon_check() -> str:
    d = "M22 68 L50 96 L106 32"
    return p(d, sw=30) + p(d, stroke="#86d255", sw=19) + hl("M26 64 L50 88 L100 31", 4, 0.45)


def icon_lock() -> str:
    d = "M40 60 L40 42 C40 12 88 12 88 42 L88 60"
    s = p(d, sw=20) + p(d, stroke="#c5d0d9", sw=10) + hl("M40 44 C40 28 50 22 60 20", 3, 0.8)
    s += r(22, 56, 84, 60, 13, m("gold")) + hl("M32 64 L96 64", 4, 0.6)
    s += dot(64, 80, 9, O) + p("M64 82 L64 100", sw=9)
    return s


def icon_warning() -> str:
    s = p("M64 18 L116 106 L12 106Z", m("wheat"), sw=10) + p("M64 18 L116 106 L12 106Z", m("wheat"), stroke="#ffdc6e", sw=0.1)
    s += hl("M60 30 L24 92", 4, 0.5)
    s += r(57.5, 46, 13, 34, 6.5, O, sw=0.1) + dot(64, 93, 7.5, O)
    return s


ICONS = {
    "food": icon_food,
    "wood": icon_wood,
    "stone": icon_stone,
    "gold": icon_gold,
    "time": icon_time,
    "speedup": icon_speedup,
    "power": icon_power,
    "infantry": icon_infantry,
    "cavalry": icon_cavalry,
    "archer": icon_archer,
    "siege": icon_siege,
    "city_hall": icon_city_hall,
    "farm": icon_farm,
    "lumber_mill": icon_lumber_mill,
    "quarry": icon_quarry,
    "goldmine": icon_goldmine,
    "storehouse": icon_storehouse,
    "barracks": icon_barracks,
    "archery_range": icon_archery_range,
    "stable": icon_stable,
    "siege_workshop": icon_siege_workshop,
    "hospital": icon_hospital,
    "academy": icon_academy,
    "upgrade": icon_upgrade,
    "build": icon_build,
    "research": icon_research,
    "commander": icon_commander,
    "alliance": icon_alliance,
    "mail": icon_mail,
    "map": icon_map,
    "city": icon_city,
    "settings": icon_settings,
    "close": icon_close,
    "back": icon_back,
    "info": icon_info,
    "check": icon_check,
    "lock": icon_lock,
    "warning": icon_warning,
}


def icon_svg(name: str) -> str:
    body = f'<g filter="url(#shadow)">{ICONS[name]()}</g>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        f"<defs>{DEFS}</defs>{body}</svg>\n"
    )


def enable_mipmaps() -> int:
    """Icons are drawn far below 128px, so their Godot imports need mipmaps.

    Godot writes `<icon>.png.import` on first import; this flips the flag in
    place (run the import again afterwards, see tools/ui/build_all.sh).
    """
    patched = 0
    for path in OUT.glob("*.png.import"):
        text = path.read_text(encoding="utf-8")
        if "mipmaps/generate=false" in text:
            path.write_text(text.replace("mipmaps/generate=false", "mipmaps/generate=true"), encoding="utf-8", newline="\n")
            patched += 1
    return patched


def main() -> None:
    (OUT / "svg").mkdir(parents=True, exist_ok=True)
    images = []
    for name in ICONS:
        svg = icon_svg(name)
        (OUT / "svg" / f"{name}.svg").write_text(svg, encoding="utf-8", newline="\n")
        img = rasterize(svg)
        img.save(OUT / f"{name}.png")
        images.append((name, img))
    print(f"wrote {len(images)} icons to {OUT}")
    patched = enable_mipmaps()
    print(f"enabled mipmaps in {patched} .import files")
    if "--sheet" in sys.argv:
        sheet = Path(sys.argv[sys.argv.index("--sheet") + 1])
        contact_sheet(images, sheet, cols=8, cell=180, bg="#cbb893", scale=1.25)
        print(f"sheet: {sheet}")


if __name__ == "__main__":
    main()
