"""Paint every texture the client uses, procedurally, with a hand-painted look.

    python tools/blender/gen_textures.py [client/assets/textures]

Needs numpy + Pillow (system Python, not Blender). Deterministic: fixed seeds,
so re-running produces identical files. Outputs:

    atlas.png          shared building/prop atlas (layout: atlas_layout.py)
    ground_grass.png   tiling ground textures blended by ground.gdshader
    ground_dirt.png
    ground_cobble.png
    ground_rock.png
    noise.png          tiling value noise (macro variation, water ripples)

All "lighting" in the textures (bevels, lips, soft occlusion) is painted in
from a height field with the light at the top-left, which is what gives the
stylised hand-painted feel without normal maps.
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_layout as L  # noqa: E402

SS = 2  # supersampling factor for tiling textures


def rng(seed):
    return np.random.default_rng(seed)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sstep(a, b, x):
    return smooth((x - a) / (b - a))


def lerp(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a + (b - a) * t


def grid(n):
    c = (np.arange(n) + 0.5) / n
    return np.meshgrid(c, c)  # u (x right), v (y down)


def vnoise(n, fx, fy, seed):
    """Periodic value noise, n x n, fx/fy lattice cells across."""
    g = rng(seed).random((fy, fx))
    ys = np.arange(n) / n * fy
    xs = np.arange(n) / n * fx
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    ty = smooth(ys - y0)[:, None]
    tx = smooth(xs - x0)[None, :]
    y1 = (y0 + 1) % fy
    x1 = (x0 + 1) % fx
    a, b = g[np.ix_(y0, x0)], g[np.ix_(y0, x1)]
    c, d = g[np.ix_(y1, x0)], g[np.ix_(y1, x1)]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def fbm(n, f, seed, octaves=4, gain=0.5, fy=None):
    total = np.zeros((n, n))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        total += amp * vnoise(n, f * 2 ** o, (fy or f) * 2 ** o, seed + o * 17)
        norm += amp
        amp *= gain
    return total / norm


def shade(h, k):
    """Top-left lighting factor from a periodic height field."""
    gx = h - np.roll(h, 1, axis=1)
    gy = h - np.roll(h, 1, axis=0)
    return 1.0 + k * (gx + gy) * h.shape[0] / 384.0


def voronoi(n, k, seed, jitter=0.9):
    """Periodic Voronoi. Returns f1, f2 (cell units), id, and vector to site."""
    r = rng(seed)
    jj, ii = np.meshgrid(np.arange(k), np.arange(k), indexing="ij")
    pts = np.stack([ii + 0.5, jj + 0.5], -1) + (r.random((k, k, 2)) - 0.5) * jitter
    u, v = grid(n)
    px, py = u * k, v * k
    ci, cj = np.floor(px).astype(int), np.floor(py).astype(int)
    f1 = np.full((n, n), 1e9)
    f2 = np.full((n, n), 1e9)
    ident = np.zeros((n, n), int)
    vx = np.zeros((n, n))
    vy = np.zeros((n, n))
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            a, b = ci + di, cj + dj
            p = pts[b % k, a % k]
            dx = p[..., 0] + (a - a % k) - px
            dy = p[..., 1] + (b - b % k) - py
            d = np.hypot(dx, dy)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            ident = np.where(closer, (b % k) * k + (a % k), ident)
            vx = np.where(closer, dx, vx)
            vy = np.where(closer, dy, vy)
            f1 = np.where(closer, d, f1)
    return f1, f2, ident, vx, vy


def bricks(n, rows, cols, mortar, radius, seed, warp=0.012):
    """Running-bond brick layout. Returns (inside distance, brick id)."""
    u, v = grid(n)
    u = u + (fbm(n, 4, seed + 1) - 0.5) * warp
    v = v + (fbm(n, 4, seed + 2) - 0.5) * warp
    rf = np.floor(v * rows)
    row = rf.astype(int) % rows
    cu = u * cols + 0.5 * (row % 2)
    col = np.floor(cu).astype(int) % cols
    x = (cu - np.floor(cu) - 0.5) / cols
    y = (v * rows - rf - 0.5) / rows
    hx, hy = 0.5 / cols - mortar / 2, 0.5 / rows - mortar / 2
    qx, qy = np.abs(x) - hx + radius, np.abs(y) - hy + radius
    sd = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - radius
    return -sd, row * cols + col


# --- tiling materials (each returns an (n, n, 3) float sRGB array) -----------


def tex_stone(n, seed, rows, cols, base, alt, mortar_col, mortar=0.035, radius=0.03, bevel=0.03, k=1.5):
    inside, bid = bricks(n, rows, cols, mortar, radius, seed)
    r = rng(seed).random((rows * cols, 3))
    detail = fbm(n, 10, seed + 5, 4)
    blotch = fbm(n, 3, seed + 6, 3)
    color = lerp(hexc(base), hexc(alt), r[bid, 1])
    color = color * (0.86 + 0.26 * r[bid, 0])[..., None]
    color = color * (0.90 + 0.12 * detail + 0.10 * blotch)[..., None]
    h = sstep(0.0, bevel, inside)
    color = color * shade(h + detail * 0.10, k)[..., None]
    color = color * (0.80 + 0.20 * sstep(0.0, bevel * 2.5, inside))[..., None]
    m = hexc(mortar_col) * (0.88 + 0.24 * detail)[..., None]
    return lerp(m, color, sstep(-0.004, 0.006, inside))


def tex_plaster(n, seed):
    clouds = fbm(n, 3, seed, 4)
    fine = fbm(n, 24, seed + 3, 3)
    strokes = fbm(n, 5, seed + 9, 3, fy=28)
    color = lerp(hexc("#e3cfa6"), hexc("#f5e8c9"), clouds)
    color = color * (0.95 + 0.05 * fine + 0.05 * strokes)[..., None]
    stains = sstep(0.62, 0.85, fbm(n, 5, seed + 21, 4))
    color = lerp(color, hexc("#cdb68c"), stains * 0.45)
    return color * shade(fine * 0.5 + strokes * 0.4, 0.35)[..., None]


def tex_planks(n, seed, planks=6, base="#a8713f", alt="#8d5c33", gap="#3d2616"):
    u, v = grid(n)
    pf = np.floor(u * planks)
    pid = pf.astype(int) % planks
    fx = u * planks - pf
    r = rng(seed).random((planks, 4))
    grain = fbm(n, 36, seed + 1, 3, fy=2)
    grain2 = vnoise(n, 90, 3, seed + 2)
    color = lerp(hexc(base), hexc(alt), r[pid, 0])
    color = color * (0.86 + 0.16 * grain + 0.10 * grain2)[..., None]
    # board ends: two seams per plank at random heights
    seam = np.zeros((n, n))
    for i in range(2):
        pos = (r[pid, 1 + i] + i * 0.5) % 1.0
        d = np.abs(((v - pos + 0.5) % 1.0) - 0.5)
        seam = np.maximum(seam, 1 - sstep(0.004, 0.012, d))
    edge = np.minimum(fx, 1 - fx) / planks
    h = sstep(0.0, 0.02, edge) * (1 - seam * 0.8)
    color = color * shade(h, 1.2)[..., None]
    gapm = np.maximum(1 - sstep(0.004, 0.011, edge), seam)
    out = lerp(color, hexc(gap), gapm * 0.9)
    # nails near the seams
    return out


def tex_timber(n, seed):
    grain = fbm(n, 2, seed, 3, fy=30)
    fine = vnoise(n, 3, 96, seed + 4)
    color = lerp(hexc("#5a3a22"), hexc("#7e5431"), grain)
    color = color * (0.9 + 0.2 * fine)[..., None]
    cracks = sstep(0.72, 0.8, vnoise(n, 2, 44, seed + 8)) * sstep(0.4, 0.7, fbm(n, 6, seed + 9, 2))
    color = lerp(color, hexc("#2f1d10"), cracks * 0.7)
    return color * shade(grain * 0.6 + fine * 0.4, 0.5)[..., None]


def tex_roof(n, seed, rows=6, cols=6):
    """Neutral scalloped shingles, tinted per building through vertex colour."""
    u, v = grid(n)
    ry = v * rows
    ra = np.floor(ry)
    ta = ry - ra

    def tile(row, t):
        cu = u * cols + 0.5 * (row % 2)
        col = np.floor(cu)
        fx = cu - col - 0.5
        return fx, (row.astype(int) % rows) * cols + col.astype(int) % cols, t

    fxa, ida, _ = tile(ra, ta)
    fxb, idb, _ = tile(ra - 1, ta + 1)
    lip = 1.0 + 0.5 * np.sqrt(np.clip(1 - (2 * fxb) ** 2, 0, 1))
    in_b = (ta + 1) < lip
    t = np.where(in_b, ta + 1, ta)
    fx = np.where(in_b, fxb, fxa)
    tid = np.where(in_b, idb, ida)
    r = rng(seed).random((rows * cols, 3))
    val = 0.80 + 0.20 * r[tid, 0]
    warm = r[tid, 1]
    color = lerp(hexc("#d9d3cd"), hexc("#efe2cf"), warm) * val[..., None]
    color = color * (0.78 + 0.22 * sstep(0.0, 1.5, t))[..., None]  # lighter toward the lip
    below = (ta + 1) - lip  # distance below the lip of the tile above
    shadow = np.where(in_b, 0.0, np.exp(-np.clip(below, 0, None) / 0.10))
    color = color * (1 - 0.45 * shadow)[..., None]
    side = 1 - sstep(0.40, 0.49, np.abs(fx))
    color = color * (0.72 + 0.28 * side)[..., None]
    lipglow = np.where(in_b, sstep(0.10, 0.0, lip - (ta + 1)), 0.0)
    color = color * (1 + 0.10 * lipglow)[..., None]
    fine = fbm(n, 16, seed + 3, 3)
    return color * (0.94 + 0.10 * fine)[..., None]


def tex_thatch(n, seed, rows=3, base="#d8b45e", dark="#8f6c2c"):
    u, v = grid(n)
    ragged = (fbm(n, 24, seed + 1, 2, fy=1) - 0.5) * 0.12
    ry = (v + ragged) * rows
    t = ry - np.floor(ry)
    strands = vnoise(n, 96, 2, seed + 2) * 0.6 + vnoise(n, 40, 3, seed + 3) * 0.4
    color = lerp(hexc(dark), hexc(base), 0.35 + 0.65 * strands)
    color = color * (0.72 + 0.38 * sstep(0.0, 1.0, t))[..., None]
    color = color * (1 - 0.35 * np.exp(-t / 0.07))[..., None]
    wisps = sstep(0.78, 0.9, vnoise(n, 120, 5, seed + 5))
    return lerp(color, hexc("#f0d88c"), wisps * 0.5)


def tex_cobble(n, seed, k=7, base="#aaa091", alt="#8f8a84", gap="#544c42"):
    f1, f2, ident, _, _ = voronoi(n, k, seed, 0.8)
    r = rng(seed + 1).random((k * k, 3))
    e = f2 - f1
    h = sstep(0.05, 0.30, e)
    detail = fbm(n, 14, seed + 2, 3)
    color = lerp(hexc(base), hexc(alt), r[ident, 0]) * (0.84 + 0.28 * r[ident, 1])[..., None]
    color = lerp(color, hexc("#b9a37f"), (r[ident, 2] > 0.75) * 0.35)
    color = color * (0.92 + 0.14 * detail)[..., None]
    color = color * shade(h + detail * 0.08, 1.3)[..., None]
    color = color * (0.78 + 0.22 * h)[..., None]
    g = hexc(gap) * (0.85 + 0.3 * detail)[..., None]
    return lerp(g, color, sstep(0.03, 0.09, e))


def tex_dirt(n, seed, base="#a07a52", alt="#86633f"):
    clouds = fbm(n, 4, seed, 4)
    fine = fbm(n, 28, seed + 3, 3)
    color = lerp(hexc(alt), hexc(base), clouds) * (0.90 + 0.18 * fine)[..., None]
    f1, _, ident, _, _ = voronoi(n, 14, seed + 5, 1.0)
    r = rng(seed + 6).random((14 * 14, 2))
    size = 0.05 + 0.10 * r[ident, 0]
    pebble = (1 - sstep(size * 0.6, size, f1)) * (r[ident, 1] > 0.55)
    color = lerp(color, hexc("#c4ae8a") * (0.9 + 0.2 * fine)[..., None], pebble * 0.8)
    return color * shade(clouds * 0.6 + fine * 0.5 + pebble * 0.6, 0.7)[..., None]


def tex_rock(n, seed, k=5, base="#a39c92", alt="#8a8580"):
    f1, f2, ident, vx, vy = voronoi(n, k, seed, 1.0)
    r = rng(seed + 1).random((k * k, 4))
    slope = (vx * (r[ident, 0] - 0.5) + vy * (r[ident, 1] - 0.5)) * 1.6
    h = r[ident, 2] * 0.6 + slope
    detail = fbm(n, 12, seed + 2, 4)
    color = lerp(hexc(base), hexc(alt), r[ident, 3]) * (0.80 + 0.30 * r[ident, 2])[..., None]
    color = color * (0.90 + 0.18 * detail)[..., None]
    color = color * np.clip(shade(h + detail * 0.15, 0.9), 0.6, 1.4)[..., None]
    crack = 1 - sstep(0.0, 0.07, f2 - f1)
    return lerp(color, hexc("#5a554f"), crack * 0.7)


def tex_foliage(n, seed):
    """Neutral leaf clumps (tinted green by vertex colour)."""
    f1, _, ident, _, _ = voronoi(n, 6, seed, 0.9)
    g1, g2, _, _, _ = voronoi(n, 15, seed + 3, 1.0)
    r = rng(seed + 1).random((36, 2))
    big = np.clip(1 - f1 * 1.15, 0, 1)
    small = np.clip(1 - g1 * 1.3, 0, 1)
    h = big * 0.65 + small * 0.35
    val = 0.52 + 0.48 * sstep(0.1, 0.85, h) + (r[ident, 0] - 0.5) * 0.10
    val = val * np.clip(shade(h, 0.8), 0.75, 1.25)
    val = val * (0.86 + 0.14 * sstep(0.02, 0.14, g2 - g1))
    return lerp(hexc("#6f8f86"), hexc("#fffbe0"), np.clip(val, 0, 1))


def tex_marble(n, seed):
    inside, bid = bricks(n, 4, 2, 0.012, 0.004, seed, warp=0.0)
    r = rng(seed).random((8, 2))
    clouds = fbm(n, 3, seed + 2, 4)
    vein = np.abs(fbm(n, 4, seed + 7, 5) - 0.5)
    color = lerp(hexc("#e9e1d2"), hexc("#f8f4ea"), clouds) * (0.95 + 0.07 * r[bid, 0])[..., None]
    color = lerp(color, hexc("#cfc6b6"), (1 - sstep(0.0, 0.035, vein)) * 0.45)
    h = sstep(0.0, 0.02, inside)
    color = color * shade(h, 1.0)[..., None]
    return lerp(hexc("#b9ae9b"), color, sstep(-0.002, 0.004, inside))


def tex_flat(n, seed):
    return np.ones((n, n, 3)) * (0.955 + 0.045 * fbm(n, 6, seed, 3))[..., None]


def tex_gold(n, seed):
    u, v = grid(n)
    streak = vnoise(n, 3, 40, seed)
    band = 0.5 + 0.5 * np.sin((u + v) * 2 * math.pi * 2 + fbm(n, 3, seed + 2, 2) * 3)
    t = np.clip(0.25 + 0.5 * band + 0.25 * streak, 0, 1)
    return lerp(lerp(hexc("#b07a1c"), hexc("#e9b63c"), sstep(0.0, 0.6, t)), hexc("#fff0a8"), sstep(0.7, 1.0, t))


def tex_hay(n, seed):
    a = vnoise(n, 60, 3, seed)
    b = vnoise(n, 4, 50, seed + 1)
    c = fbm(n, 5, seed + 2, 3)
    t = np.clip(0.5 * a + 0.3 * b + 0.3 * c, 0, 1)
    color = lerp(hexc("#a8842f"), hexc("#ecd27c"), t)
    return color * shade(a * 0.6 + b * 0.5, 0.8)[..., None]


def tex_wheat(n, seed, rows=4):
    u, v = grid(n)
    wob = (fbm(n, 6, seed, 2) - 0.5) * 0.04
    t = (v + wob) * rows
    f = t - np.floor(t)
    ridge = 1 - np.abs(f - 0.5) * 2  # 1 on the crop row, 0 in the furrow
    tufts = fbm(n, 30, seed + 3, 3)
    soil = hexc("#7a5636") * (0.85 + 0.3 * fbm(n, 20, seed + 5, 3))[..., None]
    crop = lerp(hexc("#c79a2e"), hexc("#f4d873"), tufts)
    m = sstep(0.25, 0.55, ridge + (tufts - 0.5) * 0.5)
    out = lerp(soil, crop, m)
    return out * shade(m + tufts * 0.3, 1.0)[..., None]


def tex_fabric(n, seed):
    u, v = grid(n)
    weave = 0.5 + 0.25 * np.sin(u * 2 * math.pi * 48) + 0.25 * np.sin(v * 2 * math.pi * 48)
    folds = 0.5 + 0.5 * np.sin(u * 2 * math.pi * 3 + fbm(n, 2, seed, 2) * 4)
    val = 0.86 + 0.05 * weave + 0.09 * folds
    return np.ones((n, n, 3)) * val[..., None]


def tex_grass(n, seed):
    """Ground grass: soft colour drift plus thousands of little blade strokes."""
    clouds = fbm(n, 3, seed, 4)
    mid = fbm(n, 9, seed + 1, 3)
    color = lerp(hexc("#6fa63f"), hexc("#8fc24f"), clouds)
    color = lerp(color, hexc("#a2cc58"), sstep(0.55, 0.9, mid) * 0.5)
    img = Image.fromarray((np.clip(color, 0, 1) * 255).astype(np.uint8), "RGB")
    s = 2
    img = img.resize((n * s, n * s), Image.BICUBIC)
    d = ImageDraw.Draw(img, "RGBA")
    r = rng(seed + 5)
    count = int(n * n / 55)
    lights = ["#b4dc66", "#9ed257", "#c3e37a"]
    darks = ["#4f8a31", "#5a9636", "#467d2e"]
    for i in range(count):
        x, y = r.random(2) * n * s
        ln = (4 + r.random() * 7) * s
        ang = -math.pi / 2 + (r.random() - 0.5) * 1.1
        dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
        col = (lights if r.random() < 0.55 else darks)[int(r.integers(3))]
        rgba = tuple(int(c * 255) for c in hexc(col)) + (int(90 + r.random() * 110),)
        for ox in (-n * s, 0, n * s):
            for oy in (-n * s, 0, n * s):
                if -20 < x + ox < n * s + 20 and -20 < y + oy < n * s + 20:
                    d.line([(x + ox, y + oy), (x + ox + dx * 0.5 + 1.5 * s, y + oy + dy * 0.5),
                            (x + ox + dx, y + oy + dy)], fill=rgba, width=s)
    for i in range(int(n * n / 9000)):  # tiny flowers
        x, y = r.random(2) * n * s
        col = ["#fff6d8", "#ffe27a", "#f6f1ff"][int(r.integers(3))]
        rad = (1.2 + r.random()) * s
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=tuple(int(c * 255) for c in hexc(col)) + (235,))
    img = img.resize((n, n), Image.LANCZOS)
    return np.asarray(img).astype(float) / 255.0


# --- decals ---------------------------------------------------------------------


def rgb(h, a=255):
    return tuple(int(round(c * 255)) for c in hexc(h)) + (a,)


class Canvas:
    """Small supersampled RGBA drawing surface for decals."""

    def __init__(self, w, h, bg, ss=4):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new("RGB", (w * ss, h * ss), rgb(bg)[:3])
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def _s(self, box):
        return [c * self.ss for c in box]

    def rect(self, box, fill, radius=0):
        if radius:
            self.d.rounded_rectangle(self._s(box), radius * self.ss, fill=fill)
        else:
            self.d.rectangle(self._s(box), fill=fill)

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self._s(box), fill=fill, outline=outline, width=int(width * self.ss))

    def line(self, pts, fill, width):
        self.d.line([c * self.ss for p in pts for c in p], fill=fill, width=int(width * self.ss))

    def poly(self, pts, fill):
        self.d.polygon([c * self.ss for p in pts for c in p], fill=fill)

    def texture(self, seed, strength=0.10, fx=6, fy=None):
        """Multiply in soft painterly noise so flat fills do not look vector."""
        a = np.asarray(self.img).astype(float)
        n = max(self.img.size)
        nz = fbm(n, fx, seed, 3, fy=fy)[: self.img.size[1], : self.img.size[0]]
        a *= (1 - strength / 2 + strength * nz)[..., None]
        self.img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def done(self):
        return np.asarray(self.img.resize((self.w, self.h), Image.LANCZOS)).astype(float) / 255.0


def glass(c, box, seed):
    x0, y0, x1, y1 = box
    steps = 24
    top, bot = hexc("#2c4763"), hexc("#6d9ab3")
    for i in range(steps):
        t = i / (steps - 1)
        col = top + (bot - top) * t
        c.rect([x0, y0 + (y1 - y0) * i / steps, x1, y0 + (y1 - y0) * (i + 1) / steps + 1],
               tuple(int(v * 255) for v in col) + (255,))
    w = x1 - x0
    c.poly([(x0 + w * 0.15, y1), (x0 + w * 0.55, y0), (x0 + w * 0.72, y0), (x0 + w * 0.32, y1)], rgb("#cfe9f5", 70))
    c.poly([(x0 + w * 0.62, y1), (x0 + w * 0.95, y0 + (y1 - y0) * 0.2), (x0 + w, y0 + (y1 - y0) * 0.2),
            (x0 + w * 0.70, y1)], rgb("#cfe9f5", 45))
    c.rect([x0, y1 - (y1 - y0) * 0.22, x1, y1], rgb("#ffd98a", 50))


def decal_window_wood():
    c = Canvas(256, 256, "#5a3a22")
    c.rect([8, 8, 248, 248], rgb("#7b5230"), 6)
    c.rect([14, 14, 242, 20], rgb("#9a6c42"))
    c.rect([30, 30, 226, 226], rgb("#2b1b10"))
    glass(c, [34, 34, 222, 222], 1)
    c.rect([120, 30, 136, 226], rgb("#6b452a"))
    c.rect([30, 120, 226, 136], rgb("#6b452a"))
    c.rect([120, 30, 124, 226], rgb("#946a40"))
    c.rect([30, 120, 226, 124], rgb("#946a40"))
    c.rect([34, 34, 222, 42], rgb("#000000", 70))
    c.rect([8, 222, 248, 248], rgb("#8a5f38"), 4)
    c.rect([8, 222, 248, 228], rgb("#a97c4c"))
    c.texture(11, 0.12, 4, 30)
    return c.done()


def decal_window_arch():
    c = Canvas(256, 256, "#b8ab97")
    c.texture(12, 0.14, 8)
    # stone surround blocks
    for i in range(9):
        a0 = math.pi + i * math.pi / 9
        x = 128 + math.cos(a0) * 104
        y = 118 + math.sin(a0) * 104
        c.line([(128 + math.cos(a0) * 76, 118 + math.sin(a0) * 76), (x, y)], rgb("#7d7366"), 3)
    c.ellipse([24, 14, 232, 222], outline=rgb("#8d8273"), width=4)
    c.rect([24, 118, 232, 250], rgb("#b8ab97"))
    for y in (150, 196):
        c.line([(24, y), (52, y)], rgb("#7d7366"), 3)
        c.line([(204, y), (232, y)], rgb("#7d7366"), 3)
    c.line([(24, 118), (24, 250)], rgb("#8d8273"), 4)
    c.line([(232, 118), (232, 250)], rgb("#8d8273"), 4)
    c.ellipse([50, 40, 206, 196], fill=rgb("#241a12"))
    c.rect([50, 118, 206, 232], rgb("#241a12"))
    # glass, clipped by redrawing the surround shadow lines
    g = Canvas(256, 256, "#000000")
    glass(g, [58, 48, 198, 226], 2)
    mask = Image.new("L", c.img.size, 0)
    md = ImageDraw.Draw(mask)
    s = c.ss
    md.ellipse([58 * s, 48 * s, 198 * s, 188 * s], fill=255)
    md.rectangle([58 * s, 118 * s, 198 * s, 226 * s], fill=255)
    c.img.paste(g.img, (0, 0), mask)
    c.d = ImageDraw.Draw(c.img, "RGBA")
    c.rect([122, 48, 134, 226], rgb("#4a3220"))
    c.rect([58, 128, 198, 138], rgb("#4a3220"))
    c.rect([40, 226, 216, 246], rgb("#cfc4b0"), 3)
    c.rect([40, 240, 216, 246], rgb("#8d8273"))
    return c.done()


def _planks(c, box, count, cols, seam):
    x0, y0, x1, y1 = box
    w = (x1 - x0) / count
    for i in range(count):
        c.rect([x0 + i * w, y0, x0 + (i + 1) * w, y1], rgb(cols[i % len(cols)]))
        c.rect([x0 + i * w, y0, x0 + i * w + 2.5, y1], rgb(seam))
        c.rect([x0 + i * w + 2.5, y0, x0 + i * w + 5, y1], rgb("#ffffff", 28))


def decal_door_plank():
    c = Canvas(256, 256, "#4f331e")
    c.rect([6, 6, 250, 256], rgb("#6b452a"), 6)
    c.rect([10, 10, 246, 16], rgb("#8d6238"))
    c.rect([26, 26, 230, 256], rgb("#24160c"))
    _planks(c, [30, 30, 226, 256], 5, ["#93602f", "#84552a", "#9c6934"], "#3d2616")
    c.texture(21, 0.16, 5, 40)
    for y in (70, 190):
        c.rect([30, y, 226, y + 20], rgb("#3a3b42"), 3)
        c.rect([30, y, 226, y + 4], rgb("#6b6e78"))
        for x in (48, 88, 128, 168, 208):
            c.ellipse([x - 4, y + 6, x + 4, y + 14], fill=rgb("#8b8f9a"))
    c.ellipse([176, 120, 204, 148], outline=rgb("#c9a13c"), width=5)
    c.ellipse([186, 114, 196, 124], fill=rgb("#e0bb55"))
    c.rect([30, 30, 226, 40], rgb("#000000", 80))
    return c.done()


def decal_door_double():
    c = Canvas(256, 256, "#a89c8c")
    c.texture(31, 0.14, 8)
    for i in range(11):
        a0 = math.pi + i * math.pi / 11
        c.line([(128 + math.cos(a0) * 92, 122 + math.sin(a0) * 92),
                (128 + math.cos(a0) * 124, 122 + math.sin(a0) * 124)], rgb("#6f6659"), 3)
    for y in (160, 208):
        c.line([(0, y), (34, y)], rgb("#6f6659"), 3)
        c.line([(222, y), (256, y)], rgb("#6f6659"), 3)
    c.ellipse([30, 24, 226, 220], fill=rgb("#1f140b"))
    c.rect([30, 122, 226, 256], rgb("#1f140b"))
    d = Canvas(256, 256, "#000000")
    _planks(d, [36, 30, 220, 256], 8, ["#8a5a2e", "#7b4f28", "#946233"], "#3a2413")
    d.texture(32, 0.16, 5, 40)
    for y in (110, 200):
        d.rect([36, y, 220, y + 16], rgb("#34353c"), 2)
        d.rect([36, y, 220, y + 3], rgb("#666a75"))
        for x in range(50, 220, 26):
            d.ellipse([x - 3.5, y + 4.5, x + 3.5, y + 11.5], fill=rgb("#9296a2"))
    d.rect([125, 30, 131, 256], rgb("#1f140b"))
    d.ellipse([104, 150, 120, 166], outline=rgb("#d0a840"), width=4)
    d.ellipse([136, 150, 152, 166], outline=rgb("#d0a840"), width=4)
    mask = Image.new("L", c.img.size, 0)
    md = ImageDraw.Draw(mask)
    s = c.ss
    md.ellipse([36 * s, 30 * s, 220 * s, 214 * s], fill=255)
    md.rectangle([36 * s, 122 * s, 220 * s, 256 * s], fill=255)
    c.img.paste(d.img, (0, 0), mask)
    c.d = ImageDraw.Draw(c.img, "RGBA")
    c.ellipse([112, 2, 144, 34], fill=rgb("#c9bfad"), outline=rgb("#6f6659"), width=2)
    return c.done()


def decal_crate():
    c = Canvas(256, 256, "#b58349")
    _planks(c, [0, 0, 256, 256], 5, ["#b58349", "#a87740", "#bd8c52"], "#6e4a26")
    c.line([(26, 230), (230, 26)], rgb("#8f6234"), 34)
    c.line([(26, 222), (222, 26)], rgb("#a9773f", 160), 6)
    for box in ([0, 0, 256, 30], [0, 226, 256, 256], [0, 0, 30, 256], [226, 0, 256, 256]):
        c.rect(box, rgb("#8f6234"))
    c.rect([0, 0, 256, 6], rgb("#b88a50"))
    c.rect([0, 0, 6, 256], rgb("#b88a50"))
    c.rect([0, 250, 256, 256], rgb("#5e3f20"))
    c.rect([250, 0, 256, 256], rgb("#5e3f20"))
    for x, y in ((15, 15), (241, 15), (15, 241), (241, 241)):
        c.ellipse([x - 5, y - 5, x + 5, y + 5], fill=rgb("#4a4a50"))
    c.texture(41, 0.16, 5, 36)
    return c.done()


def decal_barrel():
    c = Canvas(256, 256, "#9a6a3a")
    _planks(c, [0, 0, 256, 256], 8, ["#9a6a3a", "#8b5d31", "#a67442"], "#553619")
    c.texture(51, 0.16, 5, 36)
    for y in (44, 190):
        c.rect([0, y, 256, y + 24], rgb("#3d3f47"))
        c.rect([0, y, 256, y + 5], rgb("#7b808d"))
        c.rect([0, y + 20, 256, y + 24], rgb("#24252a"))
    c.rect([0, 0, 256, 10], rgb("#000000", 60))
    c.rect([0, 240, 256, 256], rgb("#000000", 80))
    return c.done()


def decal_target():
    c = Canvas(256, 256, "#d2b062")
    c.texture(61, 0.25, 30)
    for rad, col in ((118, "#e9d9a8"), (112, "#f4efe2"), (88, "#2f3138"), (64, "#3f79c4"), (42, "#cf3a2e"), (18, "#f2c531")):
        c.ellipse([128 - rad, 128 - rad, 128 + rad, 128 + rad], fill=rgb(col))
    c.ellipse([14, 14, 242, 242], outline=rgb("#8f6c2c"), width=4)
    c.poly([(60, 60), (128, 20), (150, 30), (80, 80)], rgb("#ffffff", 40))
    return c.done()


def decal_wheel():
    c = Canvas(256, 256, "#2a1c11")
    c.ellipse([4, 4, 252, 252], fill=rgb("#3d3f47"))
    c.ellipse([14, 14, 242, 242], fill=rgb("#8a5c33"))
    c.ellipse([20, 20, 236, 236], outline=rgb("#a9773f"), width=4)
    c.ellipse([44, 44, 212, 212], fill=rgb("#2a1c11"))
    for i in range(8):
        a = i * math.pi / 4
        c.line([(128, 128), (128 + math.cos(a) * 96, 128 + math.sin(a) * 96)], rgb("#8a5c33"), 16)
        c.line([(128 - 3, 128 - 3), (128 + math.cos(a) * 96 - 3, 128 + math.sin(a) * 96 - 3)], rgb("#a9773f"), 4)
    c.ellipse([98, 98, 158, 158], fill=rgb("#6b452a"))
    c.ellipse([112, 112, 144, 144], fill=rgb("#3d3f47"))
    c.ellipse([118, 116, 132, 130], fill=rgb("#8b8f9a"))
    return c.done()


def decal_shield():
    c = Canvas(256, 256, "#55575f")
    c.ellipse([6, 6, 250, 250], fill=rgb("#b8322b"))
    c.d.pieslice(c._s([6, 6, 250, 250]), 180, 270, fill=rgb("#efe3c4"))
    c.d.pieslice(c._s([6, 6, 250, 250]), 0, 90, fill=rgb("#efe3c4"))
    c.texture(71, 0.14, 6)
    c.ellipse([6, 6, 250, 250], outline=rgb("#55575f"), width=14)
    c.ellipse([10, 10, 246, 246], outline=rgb("#9a9eaa"), width=4)
    c.ellipse([92, 92, 164, 164], fill=rgb("#d9ad3a"))
    c.ellipse([100, 98, 140, 132], fill=rgb("#fbe08a"))
    c.ellipse([92, 92, 164, 164], outline=rgb("#8a6417"), width=4)
    return c.done()


def _sun(c, cx, cy, r, col, hi):
    for i in range(8):
        a = i * math.pi / 4
        b = a + math.pi / 8
        c.poly([(cx + math.cos(a - 0.2) * r, cy + math.sin(a - 0.2) * r),
                (cx + math.cos(a) * r * 1.9, cy + math.sin(a) * r * 1.9),
                (cx + math.cos(a + 0.2) * r, cy + math.sin(a + 0.2) * r)], rgb(col))
        c.poly([(cx + math.cos(b - 0.14) * r, cy + math.sin(b - 0.14) * r),
                (cx + math.cos(b) * r * 1.45, cy + math.sin(b) * r * 1.45),
                (cx + math.cos(b + 0.14) * r, cy + math.sin(b + 0.14) * r)], rgb(col))
    c.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb(col))
    c.ellipse([cx - r * 0.6, cy - r * 0.7, cx + r * 0.3, cy + r * 0.2], fill=rgb(hi))


def decal_banner(base, dark, emblem):
    c = Canvas(128, 256, base)
    for x in (0, 44, 88):  # soft vertical folds
        c.rect([x, 0, x + 22, 256], rgb(dark, 70))
        c.rect([x + 22, 0, x + 30, 256], rgb("#ffffff", 22))
    c.rect([0, 0, 128, 20], rgb("#d9ad3a"))
    c.rect([0, 14, 128, 20], rgb("#8a6417"))
    c.rect([0, 0, 128, 5], rgb("#fbe08a"))
    c.rect([0, 206, 128, 216], rgb("#d9ad3a"))
    c.rect([0, 222, 128, 227], rgb("#d9ad3a"))
    if emblem == "sun":
        _sun(c, 64, 110, 22, "#e9bd45", "#fbe08a")
    else:
        for i, y in enumerate((140, 164)):
            c.line([(26, y + 14), (64, y - 12), (102, y + 14)], rgb("#e9bd45"), 9)
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = 26 if i % 2 == 0 else 11
            pts.append((64 + math.cos(a) * rr, 84 + math.sin(a) * rr))
        c.poly(pts, rgb("#e9bd45"))
    c.texture(81, 0.10, 6)
    return c.done()


def decal_log_end():
    c = Canvas(128, 128, "#4d331e")
    c.ellipse([5, 5, 123, 123], fill=rgb("#d6b279"))
    for rad in (48, 38, 28, 18, 9):
        c.ellipse([64 - rad, 64 - rad + 2, 64 + rad, 64 + rad + 2], outline=rgb("#a9824a"), width=2.5)
    c.ellipse([5, 5, 123, 123], outline=rgb("#5b3d24"), width=6)
    c.line([(64, 66), (100, 40)], rgb("#8a6636"), 2)
    c.texture(91, 0.12, 6)
    return c.done()


def decal_hay_end():
    c = Canvas(128, 128, "#a8842f")
    c.ellipse([3, 3, 125, 125], fill=rgb("#e2c56c"))
    pts = []
    for i in range(140):
        a = i * 0.32
        rr = 2 + i * 0.41
        pts.append((64 + math.cos(a) * rr, 64 + math.sin(a) * rr))
    c.line(pts, rgb("#a8842f"), 3)
    c.ellipse([3, 3, 125, 125], outline=rgb("#8f6c2c"), width=4)
    c.texture(92, 0.2, 24)
    return c.done()


def decal_slit():
    c = Canvas(128, 128, "#aea18f")
    c.texture(93, 0.14, 6)
    c.rect([44, 14, 84, 116], rgb("#8d8273"), 8)
    c.rect([52, 22, 76, 110], rgb("#17110c"), 10)
    c.rect([52, 22, 60, 110], rgb("#000000", 90), 6)
    c.rect([40, 108, 88, 120], rgb("#cfc4b0"), 3)
    return c.done()


def decal_sign_heal():
    c = Canvas(128, 128, "#6b452a")
    c.ellipse([6, 6, 122, 122], fill=rgb("#f6f1e4"))
    c.ellipse([6, 6, 122, 122], outline=rgb("#d9ad3a"), width=7)
    # a leaf-and-drop healer's mark (not a red cross: that emblem is protected)
    c.rect([54, 30, 74, 98], rgb("#3f9a6a"), 5)
    c.rect([30, 54, 98, 74], rgb("#3f9a6a"), 5)
    c.ellipse([56, 56, 72, 72], fill=rgb("#f6f1e4"))
    c.texture(94, 0.08, 6)
    return c.done()


# --- assembly ------------------------------------------------------------------


def to_image(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def downsample(a, n):
    """Wrap-aware LANCZOS downsample of a periodic array to n x n."""
    big = np.tile(a, (3, 3, 1))
    img = to_image(big).resize((3 * n, 3 * n), Image.LANCZOS)
    return np.asarray(img)[n:2 * n, n:2 * n].astype(float) / 255.0


TILE_PAINTERS = {
    "stone_brick": lambda n: tex_stone(n, 101, 6, 3, "#b9ac98", "#a8a29a", "#6f6659"),
    "stone_block": lambda n: tex_stone(n, 202, 4, 2, "#9698a0", "#868a96", "#54565f", mortar=0.03, radius=0.035,
                                       bevel=0.045, k=1.8),
    "plaster": lambda n: tex_plaster(n, 303),
    "wood_planks": lambda n: tex_planks(n, 404),
    "timber": lambda n: tex_timber(n, 505),
    "roof_tiles": lambda n: tex_roof(n, 606),
    "thatch": lambda n: tex_thatch(n, 707),
    "cobble": lambda n: tex_cobble(n, 808),
    "dirt": lambda n: tex_dirt(n, 909),
    "rock": lambda n: tex_rock(n, 1010),
    "foliage": lambda n: tex_foliage(n, 1111),
    "marble": lambda n: tex_marble(n, 1212),
    "flat": lambda n: tex_flat(n, 1313),
    "gold": lambda n: tex_gold(n, 1414),
    "hay": lambda n: tex_hay(n, 1515),
    "wheat": lambda n: tex_wheat(n, 1616),
    "fabric": lambda n: tex_fabric(n, 1717),
}

DECAL_PAINTERS = {
    "window_wood": decal_window_wood,
    "window_arch": decal_window_arch,
    "door_plank": decal_door_plank,
    "door_double": decal_door_double,
    "crate": decal_crate,
    "barrel": decal_barrel,
    "target": decal_target,
    "wheel": decal_wheel,
    "shield": decal_shield,
    "banner_red": lambda: decal_banner("#b8322b", "#7d1c1c", "sun"),
    "banner_blue": lambda: decal_banner("#2f55a4", "#1c3572", "star"),
    "log_end": decal_log_end,
    "hay_end": decal_hay_end,
    "slit": decal_slit,
    "sign_heal": decal_sign_heal,
}


def build_atlas():
    atlas = np.zeros((L.SIZE, L.SIZE, 3))
    for name, (x, y, cell, _) in L.TILES.items():
        p, g = L.period_px(cell), L.gutter(cell)
        tile = downsample(TILE_PAINTERS[name](p * SS), p)
        idx = (np.arange(cell) - g) % p
        atlas[y:y + cell, x:x + cell] = tile[np.ix_(idx, idx)]
    for name, (x, y, w, h) in L.DECALS.items():
        d = DECAL_PAINTERS[name]()
        i = L.DECAL_INSET  # squeeze into the inset, then bleed edges outwards
        inner = np.asarray(to_image(d).resize((w - 2 * i, h - 2 * i), Image.LANCZOS)).astype(float) / 255.0
        atlas[y:y + h, x:x + w] = np.pad(inner, ((i, i), (i, i), (0, 0)), mode="edge")
    return atlas


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "client", "assets", "textures")
    os.makedirs(out, exist_ok=True)
    to_image(build_atlas()).save(os.path.join(out, "atlas.png"), optimize=True)
    n = 512
    to_image(tex_grass(n, 2101)).save(os.path.join(out, "ground_grass.png"), optimize=True)
    to_image(downsample(tex_dirt(n * SS, 2202, "#b08a5c", "#96724a"), n)).save(
        os.path.join(out, "ground_dirt.png"), optimize=True)
    to_image(downsample(tex_cobble(n * SS, 2303, k=9, base="#b3a998", alt="#989088", gap="#6a5f50"), n)).save(
        os.path.join(out, "ground_cobble.png"), optimize=True)
    to_image(downsample(tex_rock(n * SS, 2404, k=6), n)).save(os.path.join(out, "ground_rock.png"), optimize=True)
    nz = fbm(256, 4, 2505, 5)
    nz = (nz - nz.min()) / (nz.max() - nz.min())
    to_image(np.repeat(nz[..., None], 3, axis=2)).save(os.path.join(out, "noise.png"), optimize=True)
    print("textures written to", os.path.abspath(out))


if __name__ == "__main__":
    main()
