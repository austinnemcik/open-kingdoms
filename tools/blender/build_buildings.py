"""Generate every building model (12 kinds x 5 visual tiers) as .glb.

    blender -b --factory-startup -P tools/blender/build_buildings.py -- client/assets/models [kind[:tier] ...]

Output: <out_dir>/<kind>_t<tier>.glb. Tier = 1 + (level - 1) // 5.
Rules (docs/ART_BIBLE.md): 1 unit = 1 tile, footprints match data/buildings.yaml
exactly, front faces -Y, base on z = 0. Tiers go wood -> timber-framed ->
stone -> ornate (banners, gold trim) -> majestic (marble, gold, spires).
To add a building: write `build_<kind>(k, t)` and register it in BUILDERS.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okkit import Kit, clear_scene, export_glb, mix, script_args  # noqa: E402

# Identity roof colours (sRGB): one glance at the roof tells you the building.
ROOF = {
    "city_hall": "#3f66bd",
    "farm": "#cf7a3c",
    "lumber_mill": "#9a6b42",
    "quarry": "#6f7682",
    "goldmine": "#2f7a78",
    "storehouse": "#c4633a",
    "barracks": "#b8402f",
    "archery_range": "#4f8a3f",
    "stable": "#b0783a",
    "siege_workshop": "#566070",
    "hospital": "#58a98c",
    "academy": "#7a56b0",
}
GOLD = "#ffffff"
DARK = "#2a211b"

# Per-tier wall material / tint, skirt (foundation) and ground pad.
WALL = {1: ("wood_planks", None), 2: ("plaster", None), 3: ("stone_brick", None), 4: ("stone_brick", "#fff3dc"),
        5: ("marble", "#f6ecda")}
SKIRT = {1: None, 2: ("stone_brick", "#d9d0c4"), 3: ("stone_block", None), 4: ("stone_block", None),
         5: ("stone_block", "#e6e2ee")}
PAD = {1: ("dirt", None), 2: ("cobble", "#e8dcc8"), 3: ("cobble", None), 4: ("cobble", "#f4ecdc"),
       5: ("marble", "#dccfba")}
TRIM = {1: "#ffffff", 2: "#ffffff", 3: "#d8c8b8", 4: "#d8c8b8", 5: "#d8c8b8"}


def pick(t, *vals):
    """Value for tier t from a per-tier list (shorter lists repeat the last)."""
    return vals[min(t, len(vals)) - 1]


def pad(k, fp, t, mat=None, tint=None):
    m, c = PAD[t]
    k.pad(fp, mat or m, tint if mat else c, h=0.05, side="stone_block" if t >= 3 else None)
    return 0.05


def house(k, t, x, y, z, w, d, h, roof, axis="x", rh=None, door=None, door_x=0.0, door_kind=None, wins="fr",
          win_n=None, chimney=None, hip=False, frame=True, over=0.12, wall=None, win_z=None, door_w=None,
          ridge_gold=None, thatch=None):
    """A tier-styled house: walls, foundation, roof, door, windows, chimney."""
    wmat, wtint = wall or WALL[t]
    k.box(x, y, z, w, d, h, wmat, wtint, skip="tb")
    if SKIRT[t]:
        k.box(x, y, z, w + 0.06, d + 0.06, min(0.14, h * 0.25), SKIRT[t][0], SKIRT[t][1], skip="b", taper=0.985)
    if t == 1 and frame:
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box(x + sx * (w / 2 - 0.02), y + sy * (d / 2 - 0.02), z, 0.07, 0.07, h, "timber")
    elif t == 2 and frame:
        k.timber_frame(x, y, z + 0.14, w, d, h - 0.14, mid=h > 0.7, braces="fr" if w > 0.8 else "")
    elif t >= 4 and frame:
        k.box(x, y, z + h - 0.07, w + 0.05, d + 0.05, 0.05, "gold", GOLD, skip="tb")
    span = d if axis == "x" else w
    rh = rh or span * 0.55
    use_thatch = (t == 1) if thatch is None else thatch
    rmat, rtint = ("thatch", None) if use_thatch else ("roof_tiles", roof)
    gold_ridge = (t >= 4) if ridge_gold is None else ridge_gold
    if hip:
        k.hip_roof(x, y, z + h, w, d, rh, rtint, rmat, over=over)
    else:
        k.gable_roof(x, y, z + h, w, d, rh, rtint, rmat, axis=axis, over=over, wall=wmat, wall_tint=wtint,
                     ridge_mat="gold" if gold_ridge else None, ridge_tint=GOLD)
    faces = {"f": (x, y - d / 2, w), "k": (x, y + d / 2, w), "r": (x + w / 2, y, d), "l": (x - w / 2, y, d)}
    wkind = "window_wood" if t <= 2 else "window_arch"
    sill = "timber" if t <= 2 else "marble"
    ws = min(0.24, h * 0.36)
    wz = z + (win_z if win_z is not None else h * 0.42)
    for f in wins:
        fx, fy, length = faces[f]
        n = win_n if win_n is not None else max(1, int(length / 0.55))
        slots = [(i + 0.5) / n - 0.5 for i in range(n)]
        for s in slots:
            off = s * (length - 0.16)
            if door == f and abs(off - door_x) < (door_w or 0.3) / 2 + ws / 2 + 0.03:
                continue
            px, py = (fx + off, fy) if f == "f" else (fx - off, fy) if f == "k" else (fx, fy + off) if f == "r" else (fx, fy - off)
            k.window(px, py, wz, ws * 0.85, ws, f, wkind, sill)
    if door:
        fx, fy, length = faces[door]
        dk = door_kind or ("door_plank" if t <= 2 else "door_double")
        dw = door_w or min(0.34, h * 0.5)
        dh = min(h * 0.72, dw * 1.45)
        px, py = (fx + door_x, fy) if door in "fk" else (fx, fy + door_x)
        k.door(px, py, z, dw, dh, door, dk, step="cobble" if t >= 2 else None)
    if chimney:
        cx, cy = chimney
        k.chimney(x + cx, y + cy, z + h * 0.8, rh + h * 0.2 + 0.12, 0.15, "stone_brick")
    return z + h + rh


def gold_band(k, x, y, z, w, d, th=0.05):
    k.box(x, y, z, w + 0.05, d + 0.05, th, "gold", GOLD, skip="tb")


def yard_props(k, items):
    """items: (kind, x, y, extra...)."""
    for it in items:
        kind, x, y = it[0], it[1], it[2]
        if kind == "crate":
            k.crate(x, y, 0.05, it[3] if len(it) > 3 else 0.18, it[4] if len(it) > 4 else 0.3)
        elif kind == "barrel":
            k.barrel(x, y, 0.05, it[3] if len(it) > 3 else 0.085, (it[3] if len(it) > 3 else 0.085) * 2.6)
        elif kind == "sack":
            k.sack(x, y, 0.05, 0.09, seed=int(x * 100 + y * 10))
        elif kind == "bale":
            k.hay_bale(x, y, 0.05, 0.13, 0.2, it[3] if len(it) > 3 else 0.0)


# --- City Hall (4x4) -------------------------------------------------------------


def build_city_hall(k, t):
    blue = ROOF["city_hall"]
    z = pad(k, 4, t)
    if t == 1:
        house(k, 1, 0, 0.25, z, 2.5, 1.7, 0.8, blue, rh=1.05, door="f", door_kind="door_double", door_w=0.5,
              wins="fr", chimney=(0.8, 0.35))
        # porch
        for sx in (-1, 1):
            k.box(sx * 0.42, -0.95, z, 0.08, 0.08, 0.62, "timber")
        k.gable_roof(0, -0.8, z + 0.62, 1.0, 0.5, 0.42, None, "thatch", axis="y", over=0.06)
        # watch platform
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box(-1.45 + sx * 0.22, 1.25 + sy * 0.22, z, 0.07, 0.07, 1.5, "timber")
        k.box(-1.45, 1.25, z + 1.05, 0.62, 0.62, 0.05, "wood_planks", skip="")
        k.fence(-1.74, 0.96, -1.16, 0.96, z + 1.1, 0.2, 0.04, 1)
        k.fence(-1.16, 0.96, -1.16, 1.54, z + 1.1, 0.2, 0.04, 1)
        k.hip_roof(-1.45, 1.25, z + 1.5, 0.62, 0.62, 0.45, None, "thatch", over=0.1)
        k.flag(-1.45, 1.25, z + 1.9, 0.55, blue)
        k.fence(-1.75, -1.75, -0.5, -1.75, z)
        k.fence(0.5, -1.75, 1.75, -1.75, z)
        k.fence(1.75, -1.75, 1.75, -0.4, z)
        k.fence(-1.75, -1.75, -1.75, 0.2, z)
        for sx in (-1, 1):
            k.standard(sx * 0.75, -1.2, z, 0.85, "banner_blue")
        yard_props(k, [("barrel", 1.45, -0.9), ("barrel", 1.62, -0.72), ("crate", 1.4, 1.3, 0.22),
                       ("crate", 1.15, 1.42, 0.17, 0.9), ("sack", -1.3, -1.2), ("bale", -1.45, -0.6, 0.4)])
        k.log_pile(1.45, 0.45, z, 0.6, 0.06, (3, 2), math.pi / 2)
    elif t == 2:
        house(k, 2, 0, 0.3, z, 2.7, 1.8, 1.0, blue, rh=1.1, wins="fr", chimney=(0.9, 0.4), win_n=3)
        house(k, 2, 0.1, -0.8, z, 1.1, 0.8, 1.0, blue, axis="y", rh=0.75, door="f", door_kind="door_double",
              door_w=0.46, wins="", over=0.1)
        k.window(0.1, -1.2, z + 1.12, 0.2, 0.24, "f", "window_wood")
        # corner tower
        k.box(-1.2, 1.05, z, 0.85, 0.85, 2.0, "plaster", skip="tb")
        k.box(-1.2, 1.05, z, 0.91, 0.91, 0.14, "stone_brick", "#d9d0c4")
        k.timber_frame(-1.2, 1.05, z + 1.1, 0.85, 0.85, 0.9, braces="fr")
        k.hip_roof(-1.2, 1.05, z + 2.0, 0.85, 0.85, 0.85, blue, over=0.14)
        k.finial(-1.2, 1.05, z + 2.82, 0.07)
        k.flag(-1.2, 1.05, z + 2.85, 0.5, blue)
        k.window(-1.2, 0.625, z + 1.45, 0.2, 0.24, "f")
        k.window(-0.775, 1.05, z + 1.45, 0.2, 0.24, "r")
        for sx in (-0.6, 0.8):
            k.standard(sx, -1.5, z, 0.9, "banner_blue")
        k.fence(-1.75, -1.75, -0.45, -1.75, z, mat="stone_brick", post=0.08, h=0.2, rails=1)
        k.fence(0.65, -1.75, 1.75, -1.75, z, mat="stone_brick", post=0.08, h=0.2, rails=1)
        yard_props(k, [("barrel", 1.5, -1.0), ("crate", 1.55, -0.65, 0.2), ("crate", -1.45, -0.9, 0.22, 0.5),
                       ("barrel", -1.5, -0.55), ("sack", 1.3, -1.25)])
        k.bush(-1.5, -1.4, z, 0.2, 3)
        k.bush(1.5, 1.45, z, 0.24, 4)
    else:
        wmat, wtint = WALL[t]
        s = pick(t, 0, 0, 2.5, 2.6, 2.7)       # keep width
        kh = pick(t, 0, 0, 1.2, 1.35, 1.5)     # keep height
        tr = pick(t, 0, 0, 0.42, 0.44, 0.46)   # corner tower radius
        th = pick(t, 0, 0, 1.85, 2.2, 2.6)     # corner tower height
        to = s / 2 + 0.08
        k.box(0, 0, z, s, s, kh, wmat, wtint, skip="b", top="cobble")
        k.box(0, 0, z, s + 0.08, s + 0.08, 0.2, "stone_block", SKIRT[t][1], taper=0.985)
        k.crenels(0, 0, z + kh, s, s, 0.2, 0.16, wmat, wtint)
        if t >= 4:
            gold_band(k, 0, 0, z + kh - 0.12, s, s)
        # corner towers
        n = 8 if t < 5 else 10
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.round_tower(sx * to, sy * to, z, tr, th, wmat, wtint, n=n, roof_tint=blue, roof_h=tr * 2.4,
                              finial=0.07 if t >= 4 else None, slits=2 if t >= 4 else 1,
                              collar_tint="#ffffff" if t < 5 else "#e6e2ee")
                if t == 5:
                    k.flag(sx * to, sy * to, z + th + tr * 2.4 + 0.06, 0.4, blue, 0.2)
        # upper hall
        us = pick(t, 0, 0, 1.6, 1.75, 1.95)
        uh = pick(t, 0, 0, 0.65, 0.8, 0.9)
        k.box(0, 0, z + kh, us, us, uh, wmat, wtint, skip="b", top="cobble")
        zz = z + kh + uh
        for f, px, py in (("f", 0, -us / 2), ("r", us / 2, 0)):
            for o in (-0.45, 0.0, 0.45) if t >= 4 else (-0.35, 0.35):
                ox, oy = (o, 0) if f == "f" else (0, o)
                k.window(px + ox, py + oy, z + kh + uh * 0.3, 0.2, 0.3, f, "window_arch", "marble")
        if t == 3:
            k.hip_roof(0, 0, zz, us, us, 1.0, blue, over=0.14)
            k.finial(0, 0, zz + 0.98, 0.08)
            k.flag(0, 0, zz + 1.05, 0.55, blue)
        elif t == 4:
            k.crenels(0, 0, zz, us, us, 0.18, 0.14, wmat, wtint)
            gold_band(k, 0, 0, zz - 0.1, us, us)
            k.box(0, 0, zz, 1.0, 1.0, 0.7, wmat, wtint, skip="b")
            for f, px, py in (("f", 0, -0.5), ("r", 0.5, 0)):
                k.window(px, py, zz + 0.2, 0.22, 0.32, f, "window_arch", "marble")
            k.hip_roof(0, 0, zz + 0.7, 1.0, 1.0, 1.25, blue, over=0.16)
            k.finial(0, 0, zz + 1.93, 0.1)
            k.flag(0, 0, zz + 2.02, 0.6, blue, 0.3)
        else:
            k.crenels(0, 0, zz, us, us, 0.18, 0.14, wmat, wtint)
            gold_band(k, 0, 0, zz - 0.1, us, us)
            # drum, dome and spire
            k.cyl(0, 0, zz, 0.72, 0.75, 12, "marble", None, caps="")
            k.cyl(0, 0, zz + 0.75, 0.78, 0.08, 12, "gold", GOLD, caps="t")
            for i in range(6):
                a = i * math.pi / 3 + math.pi / 6
                k.column(math.cos(a) * 0.8, math.sin(a) * 0.8, zz, 0.75, 0.06)
            for f in "fr":
                with k.face(f, (0, 0, zz + 0.2)):
                    k.quad((-0.12, -0.725, 0), (0.12, -0.725, 0), (0.12, -0.725, 0.36), (-0.12, -0.725, 0.36),
                           "window_arch")
            k.dome(0, 0, zz + 0.83, 0.74, 0.7, 12, 4, "roof_tiles", blue, mix(blue, "#ffffff", 0.25))
            k.cyl(0, 0, zz + 1.5, 0.16, 0.22, 8, "marble", caps="t")
            k.cone_roof(0, 0, zz + 1.72, 0.2, 0.75, 8, GOLD, "gold")
            k.finial(0, 0, zz + 2.44, 0.1)
            k.flag(0, 0, zz + 2.5, 0.55, blue, 0.3)
        # gate and stairs
        gw = pick(t, 0, 0, 0.62, 0.7, 0.8)
        with k.face("f", (0, -s / 2, z)):
            k.box(0, -0.06, 0, gw + 0.3, 0.14, gw * 1.5 + 0.2, "stone_block", SKIRT[t][1], skip="bk")
            k.quad((-gw / 2, -0.135, 0.12), (gw / 2, -0.135, 0.12), (gw / 2, -0.135, 0.12 + gw * 1.35),
                   (-gw / 2, -0.135, 0.12 + gw * 1.35), "door_double")
            k.crenels(0, -0.06, gw * 1.5 + 0.2, gw + 0.3, 0.14, 0.12, 0.1, "stone_block", SKIRT[t][1], sides="f")
        k.stairs(0, -s / 2 - 0.13, z, gw + 0.5 if t >= 4 else gw + 0.2, 0.5, 0.12, 3, "f",
                 "marble" if t == 5 else "stone_brick")
        for sx in (-1, 1):
            k.banner(sx * (gw / 2 + 0.42), -s / 2, z + 0.4, 0.24, 0.5, "f", "banner_blue")
            if t >= 4:
                k.banner(s / 2, sx * 0.5, z + 0.45, 0.24, 0.5, "r", "banner_blue")
        k.window(s / 2, 0.0, z + 0.5, 0.22, 0.32, "r", "window_arch", "marble")
        if t == 3:
            k.window(s / 2, -0.6, z + 0.5, 0.2, 0.3, "r", "window_arch", "marble")
            k.window(s / 2, 0.6, z + 0.5, 0.2, 0.3, "r", "window_arch", "marble")
        for sx in (-1, 1):
            k.standard(sx * 0.95, -1.72, z, pick(t, 0, 0, 0.8, 0.95, 1.05), "banner_blue")
        if t == 5:
            for sx in (-1, 1):
                k.column(sx * (gw / 2 + 0.2), -s / 2 - 0.3, z, 1.25, 0.075)
            k.box(0, -s / 2 - 0.3, z + 1.25, gw + 0.75, 0.3, 0.1, "marble")
            gold_band(k, 0, -s / 2 - 0.3, z + 1.35, gw + 0.75, 0.3, 0.04)


# --- Farm (2x2) --------------------------------------------------------------------


def build_farm(k, t):
    roof = ROOF["farm"]
    z = pad(k, 2, t, "dirt")
    # crop field on the left: grows richer with the tiers
    k.box(-0.47, -0.02, z, 0.8, 1.66, 0.05, "dirt", "#b89a80", top="wheat", top_tint=pick(t, "#e8e0c0", "#ffffff"))
    if t >= 3:
        for i in range(4):
            k.bush(-0.72 + (i % 2) * 0.3, -0.7 + i * 0.07, z + 0.03, 0.09, i, "#4e8a2e", "#b6d95a")
    hw = pick(t, 0.62, 0.7, 0.72, 0.72, 0.76)
    hh = pick(t, 0.36, 0.44, 0.5, 0.5, 0.55)
    house(k, t, 0.5, 0.45, z, hw, 0.78, hh, roof, axis="y", rh=hw * 0.62, door="f", wins="r", win_n=1,
          chimney=(0.16, 0.2) if t >= 2 else None, over=0.09, door_kind="door_plank")
    if t in (1, 2):
        k.hay_bale(0.3, -0.5, z, 0.14, 0.22, 0.3)
        if t == 2:
            k.hay_bale(0.62, -0.62, z, 0.12, 0.2, 1.2)
            k.barrel(0.8, -0.2, z)
        k.fence(-0.05, -0.85, 0.85, -0.85, z, 0.2, 0.04)
    elif t == 3:
        k.round_tower(0.55, -0.48, z, 0.26, 0.85, "stone_brick", None, roof_tint=roof, roof_h=0.5, slits=0)
        k.hay_bale(0.12, -0.68, z, 0.12, 0.2, 0.3)
        k.fence(-0.05, -0.87, 0.3, -0.87, z, 0.2, 0.04)
    else:
        # windmill
        wtint = None if t == 4 else "#fff6e6"
        wmat = "stone_brick" if t == 4 else "marble"
        k.cyl(0.5, -0.45, z, 0.33, 1.1, 8, wmat, wtint, r2=0.22, caps="", phase=math.pi / 8)
        k.cyl(0.5, -0.45, z + 1.1, 0.26, 0.06, 8, "gold" if t == 5 else "timber", GOLD, caps="", phase=math.pi / 8)
        k.cone_roof(0.5, -0.45, z + 1.16, 0.3, 0.42, 8, roof, phase=math.pi / 8, finial=0.06 if t == 5 else None)
        k.door(0.5 - 0.23, -0.45 - 0.23, z, 0.2, 0.3, "f", "door_plank", step=None)
        with k.push((0.5, -0.45 - 0.3, z + 1.0), rx=-0.12):
            k.cyl(0, 0.02, -0.05, 0.05, 0.1, 6, "timber", caps="tb")
            for i in range(4):
                with k.push(ry=i * math.pi / 2 + 0.5):
                    k.beam((0, -0.03, 0), (0, -0.03, 0.72), 0.03, mat="timber")
                    for sy in (-1, 1):
                        k.poly([(0.02, -0.03 + sy * 0.004, 0.14), (0.2, -0.03 + sy * 0.004, 0.16),
                                (0.2, -0.03 + sy * 0.004, 0.7), (0.02, -0.03 + sy * 0.004, 0.7)], "fabric",
                               "#f4ead2" if t == 4 else "#fff8e8", out=(0, sy, 0))
        k.hay_bale(0.05, -0.75, z, 0.11, 0.18, 0.3)
        if t == 5:
            k.standard(0.9, 0.9, z, 0.7, "banner_red", w=0.15)


# --- shared set pieces ------------------------------------------------------------


def horse(k, x, y, z, rot=0.0, tint="#8f5d3b", s=1.0):
    dark = mix(tint, "#000000", 0.45)
    with k.push((x, y, z), rot, s):
        for lx in (-0.1, 0.1):
            for ly in (-0.04, 0.04):
                k.box(lx, ly, 0, 0.035, 0.035, 0.17, "flat", dark)
        k.box(0, 0, 0.16, 0.32, 0.13, 0.13, "flat", tint, taper=0.88, skip="")
        k.beam((0.11, 0, 0.25), (0.2, 0, 0.42), 0.075, 0.09, "flat", tint)
        k.beam((0.17, 0, 0.42), (0.3, 0, 0.36), 0.065, 0.075, "flat", tint)
        k.beam((0.1, 0, 0.3), (0.17, 0, 0.45), 0.02, 0.05, "flat", dark, up=(0, 1, 0))
        k.beam((-0.15, 0, 0.27), (-0.21, 0, 0.1), 0.03, 0.03, "flat", dark)


def catapult(k, x, y, z, rot=0.0, s=1.0, done=True):
    with k.push((x, y, z), rot, s):
        for sy in (-1, 1):
            k.beam((-0.36, sy * 0.16, 0.11), (0.36, sy * 0.16, 0.11), 0.05)
            k.wheel(-0.22, sy * 0.21, 0.0, 0.1)
            k.wheel(0.22, sy * 0.21, 0.0, 0.1)
            k.beam((0.06, sy * 0.16, 0.11), (0.06, sy * 0.16, 0.5), 0.05)
            k.beam((-0.22, sy * 0.16, 0.13), (0.06, sy * 0.16, 0.44), 0.035)
        for px in (-0.32, 0.32):
            k.beam((px, -0.16, 0.11), (px, 0.16, 0.11), 0.045)
        k.beam((0.06, -0.19, 0.48), (0.06, 0.19, 0.48), 0.05)
        if done:
            k.beam((-0.4, 0, 0.17), (0.2, 0, 0.64), 0.045)
            k.box(-0.42, 0, 0.1, 0.15, 0.15, 0.07, "wood_planks")
            k.box(0.2, 0, 0.56, 0.13, 0.13, 0.13, "stone_block", skip="")


def target(k, x, y, z, r=0.2, rot=0.0):
    with k.push((x, y, z), rot):
        k.beam((-r * 0.7, 0.03, 0), (0, 0.03, r * 2.1), 0.03)
        k.beam((r * 0.7, 0.03, 0), (0, 0.03, r * 2.1), 0.03)
        k.beam((0, 0.3, 0), (0, 0.04, r * 1.7), 0.03)
        k.disc(0, 0, r * 1.25, r, "f", "target", 12, off=0.0)
        k.disc(0, 0.02, r * 1.25, r, "k", "hay_end", 12, off=0.0)


def dummy(k, x, y, z, rot=0.0):
    with k.push((x, y, z), rot):
        k.beam((0, 0, 0), (0, 0, 0.42), 0.04)
        k.beam((-0.15, 0, 0.3), (0.15, 0, 0.3), 0.035)
        k.sack(0, 0, 0.36, 0.07, 2)
        k.disc(0, -0.04, 0.22, 0.09, "f", "shield", 8, off=0.0)


def weapon_rack(k, x, y, z, rot=0.0):
    with k.push((x, y, z), rot):
        for sx in (-1, 1):
            k.beam((sx * 0.18, 0, 0), (sx * 0.18, 0, 0.3), 0.035)
        k.beam((-0.2, 0, 0.26), (0.2, 0, 0.26), 0.03)
        for i in range(4):
            px = -0.13 + i * 0.087
            k.beam((px, -0.05, 0), (px, 0.01, 0.46), 0.014, mat="flat", tint="#c9ccd6" if i % 2 else "#9a7550")


def crane(k, x, y, z, h=0.9, reach=0.5, rot=0.0, load="stone_block", gold=False):
    with k.push((x, y, z), rot):
        k.beam((0, 0, 0), (0, 0, h), 0.055)
        k.beam((-0.2, 0, 0), (0, 0, h * 0.5), 0.035)
        k.beam((0, 0.2, 0), (0, 0, h * 0.5), 0.035)
        k.beam((-0.12, 0, h * 0.86), (reach, 0, h * 1.02), 0.045)
        k.beam((reach - 0.03, 0, h * 1.0), (reach - 0.03, 0, h * 0.55), 0.012, mat="flat", tint="#5a4a3a")
        if load:
            k.box(reach - 0.03, 0, h * 0.55 - 0.14, 0.17, 0.15, 0.14, load, skip="")
        if gold:
            k.finial(0, 0, h, 0.05)


def small_tower(k, t, x, y, z, s, h, roof, roof_h=0.5, top="hip", wall=None):
    """Square tower: battlements or a hip roof."""
    wmat, wtint = wall or WALL[max(t, 3)]
    k.box(x, y, z, s, s, h, wmat, wtint, skip="b", top="cobble", taper=0.96)
    k.box(x, y, z + h - 0.12, s + 0.06, s + 0.06, 0.12, wmat, wtint, skip="b", top="cobble")
    if top == "hip":
        k.hip_roof(x, y, z + h, s + 0.06, s + 0.06, roof_h, roof, over=0.08)
        if t >= 4:
            k.finial(x, y, z + h + roof_h - 0.02, 0.06)
    else:
        k.crenels(x, y, z + h, s + 0.06, s + 0.06, 0.13, 0.11, wmat, wtint)
    k.window(x, y - s / 2 * 0.98, z + h * 0.55, 0.14, 0.2, "f", "slit", None)
    k.window(x + s / 2 * 0.98, y, z + h * 0.55, 0.14, 0.2, "r", "slit", None)


# --- Lumber mill (2x2) ------------------------------------------------------------


def build_lumber_mill(k, t):
    roof = ROOF["lumber_mill"]
    z = pad(k, 2, t, "dirt")
    if t == 1:
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.box(-0.3 + sx * 0.45, 0.4 + sy * 0.33, z, 0.07, 0.07, 0.5, "timber")
        k.gable_roof(-0.3, 0.4, z + 0.5, 1.0, 0.76, 0.42, None, "thatch", over=0.1)
        k.box(-0.3, 0.4, z, 0.7, 0.3, 0.16, "wood_planks", skip="b")
        k.log((-0.7, 0.4, z + 0.23), (0.1, 0.4, z + 0.23), 0.07)
    else:
        hh = pick(t, 0, 0.5, 0.55, 0.75, 0.85)
        house(k, t, -0.35, 0.42, z, 0.95, 0.82, hh, roof, door="f", wins="r" if t < 4 else "fr", win_n=1,
              chimney=(-0.25, 0.15), over=0.1, door_x=-0.15)
        if t >= 4:
            k.window(-0.35, 0.01, z + hh * 0.62, 0.17, 0.2, "f", "window_arch", "marble")
        # saw lean-to with the big wheel
        k.box(0.52, 0.42, z, 0.07, 0.07, 0.42, "timber")
        k.box(0.52, 0.78, z, 0.07, 0.07, 0.42, "timber")
        k.box(0.52, 0.06, z, 0.07, 0.07, 0.42, "timber")
        k.poly([(0.12, 0.0, z + 0.52), (0.6, 0.0, z + 0.4), (0.6, 0.84, z + 0.4), (0.12, 0.84, z + 0.52)],
               "wood_planks" if t == 2 else "roof_tiles", None if t == 2 else roof, out=(0, 0, 1))
        k.box(0.3, 0.42, z, 0.22, 0.6, 0.15, "wood_planks", skip="b")
        k.log((0.3, 0.1, z + 0.21), (0.3, 0.74, z + 0.21), 0.06)
        if t >= 3:
            k.wheel(0.66, 0.42, z + 0.02, 0.26 if t < 5 else 0.3, "r", 0.06)
    rows = pick(t, (2, 1), (3, 2), (3, 2, 1), (4, 3, 2), (4, 3, 2, 1))
    k.log_pile(0.35, -0.55, z, 0.7, 0.065, rows, 0.15)
    # stump and plank stack
    k.cyl(-0.6, -0.45, z, 0.09, 0.12, 7, "timber", "#8a623c", cap_decal="log_end")
    if t >= 2:
        for i in range(pick(t, 0, 2, 3, 4, 5)):
            k.box(-0.3, -0.72, z + i * 0.035, 0.4, 0.2, 0.03, "wood_planks", "#f2dcb8", rot=0.08 * (i % 2), skip="b")
    if t >= 4:
        crane(k, 0.78, -0.2, z, 0.75, 0.35, math.pi * 0.75, None, gold=t == 5)
        k.banner(-0.35, 0.01, z + hh + 0.02, 0.16, 0.3, "f", "banner_red")
    if t == 5:
        k.standard(-0.8, -0.8, z, 0.7, "banner_red", w=0.15)


# --- Quarry (2x2) --------------------------------------------------------------------


def build_quarry(k, t):
    roof = ROOF["quarry"]
    z = pad(k, 2, t, "dirt", "#d8d0c8")
    stone = pick(t, "#b9b2a8", "#b9b2a8", "#c2bcb2", "#cfc8bc", "#e8e2d6")
    big = pick(t, 0.42, 0.46, 0.5, 0.55, 0.58)
    k.rock(-0.42, 0.42, z, big, 11, stone, 1.0)
    k.rock(0.1, 0.62, z, big * 0.75, 12, stone, 0.9)
    k.rock(-0.68, -0.05, z, big * 0.55, 13, stone, 0.8)
    if t >= 3:  # terraced cut face
        cut = "stone_block" if t < 5 else "marble"
        k.box(-0.2, 0.2, z, 0.5, 0.36, 0.3, cut, None, skip="b")
        k.box(-0.3, 0.32, z + 0.3, 0.34, 0.26, 0.24, cut, None, skip="b")
    block = "stone_block" if t < 5 else "marble"
    stacks = pick(t, [(0.0, -0.6, 1)], [(0.0, -0.62, 2), (0.3, -0.62, 1)], [(-0.1, -0.62, 2), (0.2, -0.62, 2)],
                  [(-0.2, -0.65, 3), (0.1, -0.65, 2), (0.4, -0.65, 1)], [(-0.25, -0.65, 3), (0.05, -0.65, 3), (0.35, -0.65, 2)])
    for sx, sy, n in stacks:
        for i in range(n):
            k.box(sx, sy, z + i * 0.15, 0.26, 0.2, 0.15, block, None, skip="b", rot=0.12 * ((i + int(sx * 10)) % 3 - 1))
    if t == 1:
        k.box(0.55, 0.1, z, 0.06, 0.06, 0.36, "timber")
        k.box(0.55, 0.5, z, 0.06, 0.06, 0.36, "timber")
        k.poly([(0.2, 0.0, z + 0.48), (0.66, 0.0, z + 0.34), (0.66, 0.6, z + 0.34), (0.2, 0.6, z + 0.48)], "thatch",
               out=(0, 0, 1))
    else:
        crane(k, 0.2, 0.05, z, pick(t, 0, 0.75, 0.85, 1.0, 1.1), 0.45, -math.pi * 0.62, block, gold=t == 5)
    if t >= 3:
        house(k, t, 0.62, 0.55, z, 0.5, 0.56, 0.4, roof, axis="y", door="f", wins="", over=0.07, rh=0.3)
        k.cart(0.62, -0.25, z, math.pi / 2, "stone")
    if t >= 4:
        crane(k, -0.72, -0.5, z, 0.7, 0.36, -0.4, None, gold=t == 5)
        k.banner(0.62, 0.27, z + 0.42, 0.14, 0.26, "f", "banner_red")
    if t == 5:
        k.standard(0.82, -0.82, z, 0.7, "banner_red", w=0.15)


# --- Goldmine (2x2) ------------------------------------------------------------------


def build_goldmine(k, t):
    roof = ROOF["goldmine"]
    z = pad(k, 2, t, "dirt", "#cfc6ba")
    rockc = "#a0958a"
    k.rock(-0.1, 0.35, z, 0.72, 21, rockc, 1.05)
    k.rock(0.55, 0.55, z, 0.4, 22, rockc, 0.9)
    k.rock(-0.68, 0.5, z, 0.36, 23, rockc, 0.9)
    # entrance
    ey = -0.22
    if t <= 2:
        for sx in (-1, 1):
            k.beam((-0.1 + sx * 0.2, ey, z), (-0.1 + sx * 0.17, ey, z + 0.42), 0.07)
        k.beam((-0.36, ey, z + 0.44), (0.16, ey, z + 0.44), 0.08)
    else:
        pm = "stone_block" if t < 5 else "marble"
        for sx in (-1, 1):
            k.box(-0.1 + sx * 0.24, ey + 0.04, z, 0.14, 0.2, 0.46, pm)
        k.box(-0.1, ey + 0.04, z + 0.46, 0.66, 0.22, 0.14, pm, skip="")
        if t >= 4:
            gold_band(k, -0.1, ey + 0.04, z + 0.6, 0.66, 0.22, 0.04)
    k.quad((-0.3, ey + 0.03, z), (0.1, ey + 0.03, z), (0.1, ey + 0.03, z + 0.44), (-0.3, ey + 0.03, z + 0.44), "flat", DARK)
    # rails and cart
    for sx in (-1, 1):
        k.beam((-0.1 + sx * 0.08, ey, z + 0.012), (-0.1 + sx * 0.08, -0.9, z + 0.012), 0.02, mat="flat", tint="#5a5d66")
    for i in range(5):
        k.box(-0.1, ey - 0.08 - i * 0.14, z, 0.26, 0.04, 0.012, "timber")
    with k.push((-0.1, -0.62, z + 0.03)):
        k.box(0, 0, 0.04, 0.2, 0.26, 0.13, "wood_planks", "#b9a88f", taper=1.15)
        k.blob(0, 0, 0.18, 0.09, 0.11, 0.07, "gold", "#d9b14a", "#ffffff", n=6, rings=3, seed=5, jitter=0.25)
        for sy in (-1, 1):
            k.wheel(-0.105, sy * 0.08, -0.02, 0.05, "l", 0.02)
            k.wheel(0.105, sy * 0.08, -0.02, 0.05, "r", 0.02)
    nuggets = pick(t, [(0.45, -0.5)], [(0.45, -0.5), (0.62, -0.3)], [(0.45, -0.5), (0.62, -0.3), (0.3, -0.75)],
                   [(0.45, -0.5), (0.62, -0.3), (0.3, -0.75), (-0.6, -0.5)],
                   [(0.45, -0.5), (0.62, -0.3), (0.3, -0.75), (-0.6, -0.5), (-0.75, -0.2), (0.75, -0.6)])
    for i, (px, py) in enumerate(nuggets):
        k.rock(px, py, z, 0.1, 30 + i, "#a0958a")
        k.blob(px + 0.03, py - 0.02, z + 0.09, 0.06, 0.06, 0.05, "gold", "#d9b14a", "#ffffff", n=5, rings=3, seed=i,
               jitter=0.3)
    if t >= 2:
        yard_props(k, [("sack", -0.7, -0.75), ("barrel", -0.55, -0.2, 0.07)])
    if t >= 3:  # headframe with winding wheel
        hx, hy, hh = 0.5, 0.05, pick(t, 0, 0, 0.9, 1.05, 1.2)
        for sx in (-1, 1):
            for sy in (-1, 1):
                k.beam((hx + sx * 0.22, hy + sy * 0.22, z), (hx + sx * 0.07, hy + sy * 0.07, z + hh), 0.045,
                       mat="gold" if t == 5 else "timber", tint=GOLD if t == 5 else None)
        k.box(hx, hy, z + hh * 0.5, 0.3, 0.3, 0.03, "wood_planks", skip="")
        k.wheel(hx, hy, z + hh - 0.04, 0.13, "f", 0.04)
        k.hip_roof(hx, hy, z + hh + 0.22, 0.3, 0.3, 0.2, roof, over=0.08)
        for sx in (-1, 1):
            k.beam((hx + sx * 0.14, hy, z + hh - 0.05), (hx + sx * 0.14, hy, z + hh + 0.22), 0.03)
    if t >= 4:
        k.standard(-0.8, -0.82, z, 0.7, "banner_red", w=0.15)
        k.crate(0.8, -0.82, z, 0.16, 0.3)
        k.blob(0.8, -0.82, z + 0.18, 0.07, 0.07, 0.05, "gold", "#d9b14a", "#ffffff", n=5, rings=3, seed=9, jitter=0.3)
    if t == 5:  # crystal-like gold outcrops on the mound
        for i, (px, py, pz) in enumerate(((-0.45, 0.3, 0.55), (0.1, 0.55, 0.68), (0.2, 0.2, 0.6))):
            k.cone(px, py, z + pz - 0.1, 0.07, 0.3, 5, "gold", "#ffffff", phase=i)
            k.cone(px + 0.08, py + 0.03, z + pz - 0.1, 0.05, 0.2, 5, "gold", "#ffffff", phase=i + 1)


# --- Storehouse (2x2) ----------------------------------------------------------------


def build_storehouse(k, t):
    roof = ROOF["storehouse"]
    z = pad(k, 2, t)
    w = pick(t, 1.25, 1.35, 1.4, 1.45, 1.5)
    h = pick(t, 0.5, 0.62, 0.7, 0.85, 0.95)
    house(k, t, 0, 0.28, z, w, 0.95, h, roof, door="f", door_kind="door_double", door_w=0.4, wins="fr",
          win_n=2 if t >= 2 else 1, over=0.1, win_z=h * 0.5)
    if t >= 2:  # hoist over the door
        k.beam((0, -0.2, z + h + 0.12), (0, -0.48, z + h + 0.12), 0.045)
        k.beam((0, -0.44, z + h + 0.1), (0, -0.44, z + h - 0.12), 0.012, mat="flat", tint="#5a4a3a")
        k.sack(0, -0.44, z + h - 0.26, 0.07, 4)
    if t >= 3:  # loft dormer
        k.box(0, -0.02, z + h, 0.4, 0.3, 0.3, WALL[t][0], WALL[t][1], skip="b")
        k.gable_roof(0, 0.1, z + h + 0.3, 0.46, 0.5, 0.2, roof, axis="y", over=0.05, wall=WALL[t][0],
                     wall_tint=WALL[t][1], ridge_mat="gold" if t >= 4 else None, ridge_tint=GOLD)
        k.window(0, -0.17, z + h + 0.06, 0.16, 0.19, "f", "window_arch", None)
    if t >= 4:
        small_tower(k, t, -w / 2 + 0.05, 0.6, z, 0.42, h + 0.55, roof, 0.42)
        for sx in (-1, 1):
            k.banner(sx * 0.42, -0.195, z + h * 0.35, 0.15, 0.3, "f", "banner_red")
    props = [("crate", 0.62, -0.55, 0.2, 0.2), ("barrel", -0.6, -0.5)]
    if t >= 2:
        props += [("crate", 0.66, -0.52, 0.0), ("barrel", -0.42, -0.62), ("sack", 0.35, -0.7)]
    if t >= 3:
        props += [("crate", 0.4, -0.45, 0.17, 0.7), ("barrel", -0.75, -0.72), ("sack", -0.2, -0.75)]
    if t >= 4:
        props += [("crate", 0.75, -0.8, 0.16, 1.0), ("sack", -0.55, -0.8)]
    for it in props:
        if it[0] == "crate" and len(it) > 3 and it[3] == 0.0:
            k.crate(it[1], it[2], z + 0.2, 0.15, 0.6)
        else:
            yard_props(k, [it])
    if t == 5:
        k.standard(0.82, 0.82, z, 0.75, "banner_red", w=0.15)
        k.finial(0, 0.28, z + h + 0.95 * 0.55, 0.07)


# --- Barracks (3x3) ------------------------------------------------------------------


def build_barracks(k, t):
    roof = ROOF["barracks"]
    z = pad(k, 3, t)
    w = pick(t, 2.1, 2.2, 1.9, 1.9, 2.0)
    h = pick(t, 0.6, 0.72, 0.85, 1.0, 1.1)
    hx = pick(t, 0.0, 0.0, -0.35, -0.35, 0.0)
    house(k, t, hx, 0.65, z, w, 1.15, h, roof, door="f", door_x=-0.3, door_kind="door_double" if t >= 3 else None,
          door_w=0.36, wins="fr", chimney=(-0.6, 0.3) if t <= 2 else None, win_n=3)
    k.disc(hx + 0.35, 0.065, z + h * 0.62, 0.11, "f", "shield", 10)
    if t >= 2:
        k.disc(hx + 0.65, 0.065, z + h * 0.62, 0.11, "f", "shield", 10)
    if t in (3, 4):
        small_tower(k, t, 1.02, 0.95, z, 0.72, pick(t, 0, 0, 1.6, 1.9), roof, top="crenel")
        k.flag(1.02, 0.95, z + pick(t, 0, 0, 1.6, 1.9), 0.6, roof, 0.28)
    if t == 4:
        small_tower(k, t, -1.15, 1.05, z, 0.5, 1.5, roof, 0.5)
    if t == 5:
        for sx in (-1, 1):
            k.round_tower(sx * 1.1, 1.0, z, 0.34, 2.0, "marble", None, roof_tint=roof, roof_h=0.8, finial=0.07, slits=2)
            k.flag(sx * 1.1, 1.0, z + 2.84, 0.4, roof, 0.2)
        k.box(0, 0.65, z + h, 0.7, 0.7, 0.45, "marble", skip="b")
        k.hip_roof(0, 0.65, z + h + 0.45, 0.7, 0.7, 0.6, roof, over=0.1)
        k.finial(0, 0.65, z + h + 1.03, 0.08)
        k.window(0, 0.3, z + h + 0.1, 0.18, 0.24, "f", "window_arch", "marble")
    # training yard
    if t <= 2:
        k.fence(-1.38, -1.38, 1.38, -1.38, z)
        k.fence(-1.38, -1.38, -1.38, 0.0, z)
        k.fence(1.38, -1.38, 1.38, 0.0, z)
    else:
        wm, wt = ("stone_brick", None) if t < 5 else ("marble", None)
        for x0, x1 in ((-1.38, -0.35), (0.35, 1.38)):
            k.box((x0 + x1) / 2, -1.36, z, x1 - x0, 0.12, 0.24, wm, wt)
            k.crenels((x0 + x1) / 2, -1.36, z + 0.24, x1 - x0, 0.12, 0.12, 0.08, wm, wt, sides="f")
        for sx in (-1, 1):
            k.box(sx * 1.36, -0.7, z, 0.12, 1.2, 0.24, wm, wt)
            k.box(sx * 0.35, -1.36, z, 0.18, 0.18, 0.42, wm, wt, top="cobble")
            if t >= 4:
                k.finial(sx * 0.35, -1.36, z + 0.42, 0.06)
    dummy(k, -0.85, -0.6, z, 0.3)
    dummy(k, -0.35, -0.85, z, -0.2)
    weapon_rack(k, 0.8, -0.35, z, 0.0)
    if t >= 2:
        weapon_rack(k, 0.8, -0.85, z, 0.0)
        yard_props(k, [("barrel", 1.15, -1.1), ("crate", -1.1, -1.1, 0.2, 0.4)])
    if t >= 3:
        dummy(k, 0.2, -0.6, z, 0.5)
        for sx in (-1, 1):
            k.banner(hx - 0.3 + sx * 0.36, 0.075, z + h * 0.42, 0.16, 0.34, "f", "banner_red")
    if t >= 4:
        for sx in (-1, 1):
            k.standard(sx * 0.62, -1.1, z, 0.85, "banner_red")


# --- Archery range (3x3) -------------------------------------------------------------


def build_archery_range(k, t):
    roof = ROOF["archery_range"]
    z = pad(k, 3, t, "dirt" if t <= 2 else None)
    w = pick(t, 1.2, 1.3, 1.4, 1.5, 1.6)
    h = pick(t, 0.5, 0.6, 0.7, 0.85, 0.95)
    house(k, t, -0.6, 0.78, z, w, 0.9, h, roof, door="f", wins="fr", win_n=2, chimney=(-0.35, 0.2) if t == 2 else None)
    # targets along the back right, shooting line at the front
    n = pick(t, 2, 3, 3, 3, 4)
    xs = [0.5 + i * (0.8 / max(1, n - 1)) for i in range(n)] if n > 1 else [0.9]
    for i, px in enumerate(xs):
        target(k, px, 0.55 - 0.1 * (i % 2), z, pick(t, 0.17, 0.18, 0.2, 0.2, 0.2), 0.0)
    k.box(0.9, 0.95, z, 1.0, 0.25, 0.3, "hay", skip="b")
    if t >= 3:
        k.box(0.9, 0.95, z + 0.3, 0.7, 0.22, 0.22, "hay", skip="b")
    # lane markers and line
    for i, px in enumerate((0.45, 0.9, 1.35)):
        k.box(px - 0.22, -0.35, z, 0.025, 1.0, 0.012, "flat", "#efe6d0")
    k.fence(0.1, -1.0, 1.4, -1.0, z, 0.2, 0.04, 1)
    k.barrel(0.35, -1.2, z, 0.075, 0.2)
    for i in range(4):
        k.beam((0.33 + i * 0.015, -1.2, z + 0.15), (0.31 + i * 0.03, -1.2 + (i % 2) * 0.03, z + 0.38), 0.012,
               mat="flat", tint="#d8c9a8")
    if t >= 2:
        weapon_rack(k, -0.9, -0.3, z, math.pi / 2)
        yard_props(k, [("bale", -0.4, -0.9, 0.5), ("bale", -0.7, -1.1, 1.3)])
        k.barrel(1.0, -1.2, z, 0.075, 0.2)
    if t >= 3:
        if t == 3:
            # timber lookout
            for sx in (-1, 1):
                for sy in (-1, 1):
                    k.beam((-1.05 + sx * 0.22, -0.95 + sy * 0.22, z), (-1.05 + sx * 0.16, -0.95 + sy * 0.16, z + 1.1), 0.05)
            k.box(-1.05, -0.95, z + 0.75, 0.5, 0.5, 0.04, "wood_planks", skip="")
            k.fence(-1.3, -1.2, -0.8, -1.2, z + 0.79, 0.16, 0.03, 1)
            k.fence(-0.8, -1.2, -0.8, -0.7, z + 0.79, 0.16, 0.03, 1)
            k.hip_roof(-1.05, -0.95, z + 1.1, 0.5, 0.5, 0.35, roof, over=0.1)
        else:
            k.round_tower(-1.05, 0.95 if t == 5 else -0.95, z, 0.3, pick(t, 0, 0, 0, 1.5, 1.9),
                          "stone_brick" if t == 4 else "marble", WALL[t][1], roof_tint=roof, roof_h=0.7,
                          finial=0.06, slits=1)
        for sx in (-0.3, 0.3):
            k.banner(-0.6 + sx, 0.325, z + h * 0.4, 0.15, 0.3, "f", "banner_red")
    if t >= 4:
        k.standard(1.3, -1.3, z, 0.8, "banner_red")
        k.standard(-0.1, -1.3, z, 0.8, "banner_red")
        k.flag(-0.6, 0.78, z + h + 0.9 * 0.55 - 0.02, 0.45, roof, 0.22)
    if t == 5:
        k.box(-0.6, 0.78, z + h, 0.6, 0.5, 0.36, "marble", skip="b")
        k.gable_roof(-0.6, 0.78, z + h + 0.36, 0.6, 0.5, 0.3, roof, wall="marble", ridge_mat="gold", ridge_tint=GOLD,
                     over=0.07)
        k.round_tower(-1.05, -0.95, z, 0.26, 1.2, "marble", None, roof_tint=roof, roof_h=0.6, finial=0.06)


# --- Stable (3x3) --------------------------------------------------------------------


def build_stable(k, t):
    roof = ROOF["stable"]
    z = pad(k, 3, t, "dirt" if t <= 3 else None, None if t <= 3 else "#f4ecdc")
    h = pick(t, 0.55, 0.62, 0.7, 0.8, 0.9)
    w = pick(t, 2.4, 2.5, 2.5, 2.5, 2.6)
    house(k, t, 0, 0.8, z, w, 0.95, h, roof, wins="r", win_n=1, door=None)
    # stall doors with open top halves
    n = 4
    for i in range(n):
        px = -w / 2 + (i + 0.5) * w / n
        dh = min(0.42, h * 0.7)
        k.door(px, 0.325, z, 0.34, dh, "f", "door_plank", step=None)
        k.quad((px - 0.13, 0.305, z + dh * 0.5), (px + 0.13, 0.305, z + dh * 0.5), (px + 0.13, 0.305, z + dh * 0.92),
               (px - 0.13, 0.305, z + dh * 0.92), "flat", DARK)
    with k.push((-w / 2 + 0.5 * w / n + 0.02, 0.2, z + 0.02), -math.pi / 2, 0.8):
        k.beam((0.0, 0, 0.3), (0.12, 0, 0.44), 0.075, 0.09, "flat", "#6b4a35")
        k.beam((0.1, 0, 0.44), (0.24, 0, 0.38), 0.065, 0.075, "flat", "#6b4a35")
    # paddock
    k.fence(-1.38, -1.38, 0.2, -1.38, z, 0.28, 0.05, 2)
    k.fence(0.75, -1.38, 1.38, -1.38, z, 0.28, 0.05, 2)
    k.fence(-1.38, -1.38, -1.38, 0.2, z, 0.28, 0.05, 2)
    k.fence(1.38, -1.38, 1.38, 0.2, z, 0.28, 0.05, 2)
    horse(k, -0.5, -0.6, z, 0.5, "#8f5d3b")
    if t >= 2:
        horse(k, 0.45, -0.85, z, 2.6, "#d9cdbb" if t >= 4 else "#5a4032")
    if t >= 4:
        horse(k, 0.75, -0.2, z, -1.2, "#3d302a")
    # trough and hay
    k.box(-1.0, -0.15, z, 0.5, 0.18, 0.13, "wood_planks", skip="b", top="flat", top_tint="#5aa0c8")
    yard_props(k, [("bale", 1.05, -0.05, 0.3), ("bale", 1.1, -0.38, 1.4)])
    if t >= 2:
        k.blob(-1.0, -1.0, z + 0.14, 0.26, 0.26, 0.24, "hay", "#b89a4a", "#ffffff", n=7, rings=3, seed=2, bottom=-0.4)
    if t >= 3:
        k.cart(0.2, -0.3, z, 0.4, "hay")
    if t >= 3:
        small_tower(k, t, -w / 2 + 0.3, 0.95, z, 0.6, h + 0.6, roof, 0.5)
    if t >= 4:
        for sx in (-0.5, 0.6):
            k.standard(sx + 0.0, -1.1 if sx > 0 else -1.2, z, 0.8, "banner_red")
        k.flag(-w / 2 + 0.3, 0.95, z + h + 1.08, 0.4, roof, 0.2)
    if t == 5:
        k.box(0.4, 0.8, z + h, 0.9, 0.6, 0.35, "marble", skip="b")
        k.gable_roof(0.4, 0.8, z + h + 0.35, 0.9, 0.6, 0.36, roof, axis="y", wall="marble", ridge_mat="gold",
                     ridge_tint=GOLD, over=0.08)
        k.window(0.4, 0.5, z + h + 0.08, 0.18, 0.22, "f", "window_arch", "marble")


# --- Siege workshop (3x3) ------------------------------------------------------------


def build_siege_workshop(k, t):
    roof = ROOF["siege_workshop"]
    z = pad(k, 3, t)
    h = pick(t, 0.7, 0.8, 0.9, 1.05, 1.15)
    w = pick(t, 1.4, 1.5, 1.6, 1.6, 1.7)
    if t == 1:  # open-sided shed
        for sx in (-1, 1):
            for sy in (-1, 0, 1):
                k.box(-0.55 + sx * (w / 2 - 0.05), 0.6 + sy * 0.6, z, 0.08, 0.08, h, "timber")
        k.gable_roof(-0.55, 0.6, z + h, w, 1.35, 0.6, None, "thatch", axis="y", over=0.1)
        k.box(-0.55, 0.9, z, 0.9, 0.4, 0.22, "wood_planks", skip="b")
        k.log_pile(-0.55, 0.3, z, 0.8, 0.06, (3, 2))
    else:
        house(k, t, -0.55, 0.6, z, w, 1.4, h, roof, axis="y", door="f", door_kind="door_double", door_w=0.6,
              wins="r", win_n=2, chimney=None)
        # forge chimney
        ch = h + pick(t, 0, 0.75, 0.85, 1.0, 1.15)
        k.box(-0.55 - w / 2 + 0.12, 1.0, z, 0.34, 0.34, ch, "stone_brick" if t < 5 else "marble", None, taper=0.8)
        k.box(-0.55 - w / 2 + 0.12, 1.0, z + ch, 0.33, 0.33, 0.07, "stone_block", top="flat", top_tint="#3a332d")
        k.box(0.42, 0.9, z, 0.3, 0.2, 0.16, "stone_block", skip="b")  # anvil block
        k.box(0.42, 0.9, z + 0.16, 0.26, 0.1, 0.07, "flat", "#4a4d58", skip="b", taper=(1.3, 1.0))
    catapult(k, 0.65, -0.55, z, 0.5, pick(t, 0.9, 1.0, 1.05, 1.15, 1.2), done=t >= 2)
    for i, (px, py) in enumerate(((1.1, 0.1), (1.22, 0.24), (1.02, 0.28), (1.15, 0.18))[: pick(t, 1, 2, 3, 3, 3)]):
        k.rock(px, py, z + (0.11 if i == 3 else 0), 0.085, 40 + i, "#c2bcb2", 1.0)
    k.log_pile(-0.75, -1.05, z, 0.8, 0.055, pick(t, (2, 1), (3, 2), (3, 2), (3, 2, 1), (3, 2, 1)), 0.1)
    if t >= 3:  # battering ram frame
        with k.push((-0.7, -0.45, z), 0.1):
            for sx in (-1, 1):
                k.beam((sx * 0.3, -0.14, 0), (sx * 0.3, 0, 0.36), 0.04)
                k.beam((sx * 0.3, 0.14, 0), (sx * 0.3, 0, 0.36), 0.04)
            k.beam((-0.36, 0, 0.36), (0.36, 0, 0.36), 0.04)
            k.log((-0.42, 0, 0.17), (0.42, 0, 0.17), 0.06)
    if t >= 4:
        crane(k, 1.15, 0.85, z, 1.2, 0.5, -math.pi * 0.75, "stone_block", gold=t == 5)
        k.banner(-0.55 - 0.45, -0.105, z + h * 0.45, 0.16, 0.34, "f", "banner_red")
        k.banner(-0.55 + 0.45, -0.105, z + h * 0.45, 0.16, 0.34, "f", "banner_red")
        k.standard(1.25, -1.25, z, 0.85, "banner_red")
    if t == 5:
        with k.push((0.25, 0.35, z), -0.3, 0.8):
            for sy in (-1, 1):
                k.beam((-0.3, sy * 0.12, 0.05), (0.3, sy * 0.12, 0.05), 0.045)
                k.wheel(0.0, sy * 0.17, 0.0, 0.11)
            k.beam((-0.25, 0, 0.12), (0.4, 0, 0.3), 0.05)
            k.beam((0.05, -0.3, 0.2), (0.05, 0.3, 0.2), 0.03)
        k.finial(-0.55, 0.6 - 0.75, z + h + w * 0.55 - 0.03, 0.07)


# --- Hospital (2x2) ------------------------------------------------------------------


def build_hospital(k, t):
    roof = ROOF["hospital"]
    z = pad(k, 2, t, "dirt" if t == 1 else None)
    if t == 1:  # field tent
        k.gable_roof(-0.1, 0.25, z + 0.1, 0.5, 1.15, 0.72, "#f2e9d2", "fabric", axis="y", over=0.02, gable_over=0.0,
                     wall="fabric", wall_tint="#e2d6ba", trim="fabric", trim_tint="#58a98c", thick=0.04,
                     ridge=False)
        k.box(-0.1, 0.25, z, 1.12, 0.5, 0.1, "fabric", "#e2d6ba")
        k.poly([(-0.32, -0.005, z), (0.12, -0.005, z), (0.0, -0.005, z + 0.5), (-0.2, -0.005, z + 0.5)], "flat", DARK,
               out=(0, -1, 0))
        k.beam((-0.1, 0.0, z + 0.78), (-0.1, 0.5, z + 0.78), 0.03)
        k.disc(-0.1, -0.012, z + 0.62, 0.1, "f", "sign_heal", 10)
        yard_props(k, [("crate", 0.65, -0.3, 0.18, 0.2), ("barrel", 0.7, 0.1, 0.075), ("sack", 0.6, -0.65)])
        k.box(-0.55, -0.6, z, 0.5, 0.22, 0.06, "fabric", "#d9e6dc", skip="b")
    else:
        w = pick(t, 0, 1.15, 1.25, 1.3, 1.35)
        h = pick(t, 0, 0.55, 0.62, 0.85, 0.95)
        house(k, t, -0.1, 0.3, z, w, 0.9, h, roof, door="f", wins="fr", win_n=2, chimney=(0.35, 0.2) if t <= 3 else None,
              wall=("plaster", "#ffffff") if t <= 3 else ("marble", None), frame=t != 3, over=0.1)
        k.disc(-0.1, -0.15, z + h + 0.14, 0.12, "f", "sign_heal", 10)
        if t >= 4:
            for o in (-0.35, 0.35):
                k.window(-0.1 + o, -0.15, z + h * 0.62, 0.16, 0.2, "f", "window_arch", "marble")
        if t >= 3:  # bell turret / dome
            tz = z + h + 0.9 * 0.55 - 0.15
            if t < 5:
                k.box(-0.1, 0.3, tz, 0.26, 0.26, 0.3, "plaster" if t == 3 else "marble", "#ffffff", skip="b")
                k.hip_roof(-0.1, 0.3, tz + 0.3, 0.26, 0.26, 0.3, roof, over=0.06)
                k.finial(-0.1, 0.3, tz + 0.58, 0.05)
            else:
                k.cyl(-0.1, 0.3, tz - 0.1, 0.26, 0.3, 10, "marble", caps="")
                k.cyl(-0.1, 0.3, tz + 0.2, 0.29, 0.05, 10, "gold", GOLD, caps="t")
                k.dome(-0.1, 0.3, tz + 0.25, 0.27, 0.26, 10, 3, "roof_tiles", roof, mix(roof, "#ffffff", 0.3))
                k.finial(-0.1, 0.3, tz + 0.5, 0.07)
        # herb garden
        k.box(0.0, -0.62, z, 1.2, 0.3, 0.05, "dirt", "#b89a80", skip="b")
        for i in range(pick(t, 0, 4, 5, 6, 6)):
            k.bush(-0.5 + i * 0.2, -0.62, z + 0.03, 0.08, i, "#3f8a4a", ("#b6e07a", "#e7a6c8", "#f2e27a")[i % 3])
        k.fence(-0.62, -0.84, 0.62, -0.84, z, 0.14, 0.03, 1)
        k.barrel(0.72, 0.6, z, 0.075, 0.2)
        if t >= 4:
            k.box(0.62, 0.42, z, 0.45, 0.6, h * 0.7, "marble", skip="b")
            k.gable_roof(0.62, 0.42, z + h * 0.7, 0.45, 0.6, 0.26, roof, axis="y", wall="marble", over=0.07,
                         ridge_mat="gold", ridge_tint=GOLD)
            k.window(0.62, 0.12, z + h * 0.25, 0.16, 0.2, "f", "window_arch", "marble")
            k.window(0.845, 0.42, z + h * 0.25, 0.16, 0.2, "r", "window_arch", "marble")
        if t == 5:
            for sx in (-1, 1):
                k.column(-0.1 + sx * 0.3, -0.25, z, h * 0.8, 0.05)
            k.box(-0.1, -0.25, z + h * 0.8, 0.8, 0.2, 0.07, "marble")
            gold_band(k, -0.1, -0.25, z + h * 0.8 + 0.07, 0.8, 0.2, 0.03)


# --- Academy (3x3) -------------------------------------------------------------------


def build_academy(k, t):
    roof = ROOF["academy"]
    z = pad(k, 3, t)
    w = pick(t, 1.6, 1.8, 1.9, 2.0, 2.1)
    d = pick(t, 1.2, 1.3, 1.5, 1.6, 1.7)
    h = pick(t, 0.6, 0.75, 0.9, 1.0, 1.1)
    hy = 0.45
    if t <= 2:
        house(k, t, 0.15, hy, z, w, d, h, roof, door="f", wins="fr", win_n=3, chimney=(0.5, 0.3))
        yard_props(k, [("crate", 1.1, -0.9, 0.2, 0.3), ("barrel", -0.2, -1.0)])
        # outdoor lectern with scrolls
        k.box(0.6, -0.9, z, 0.32, 0.2, 0.2, "wood_planks", skip="b")
        k.box(0.6, -0.9, z + 0.2, 0.3, 0.14, 0.02, "flat", "#f2ead2", skip="b")
        if t == 1:
            k.standard(-0.9, -1.0, z, 0.75, "banner_blue", w=0.16)
        else:
            k.round_tower(-1.0, 0.85, z, 0.36, 1.55, "plaster", None, roof_tint=roof, roof_h=0.8, slits=0)
            k.window(-1.0, 0.85 - 0.345, z + 0.95, 0.16, 0.2, "f", "window_wood")
            k.window(-1.0 + 0.345, 0.85, z + 0.95, 0.16, 0.2, "r", "window_wood")
            k.standard(-0.9, -1.0, z, 0.8, "banner_blue", w=0.16)
            k.bush(1.2, 0.0, z, 0.18, 1)
            k.bush(-1.2, -0.3, z, 0.2, 2)
    else:
        wall = WALL[t]
        k.box(0.1, hy, z, w + 0.3, d + 0.3, 0.14, "stone_block", SKIRT[t][1], skip="b", top="marble")
        k.stairs(0.1, hy - d / 2 - 0.15, z, 1.0, 0.36, 0.14, 3, "f", "marble")
        zz = z + 0.14
        k.box(0.1, hy, zz, w, d, h, wall[0], wall[1], skip="b", top="cobble")
        # portico
        n = pick(t, 0, 0, 4, 4, 6)
        pw = pick(t, 0, 0, 1.2, 1.3, w)
        for i in range(n):
            k.column(0.1 - pw / 2 + 0.08 + i * (pw - 0.16) / (n - 1), hy - d / 2 - 0.2, zz, h, 0.06)
        k.box(0.1, hy - d / 2 - 0.12, zz + h, pw + 0.06, 0.34, 0.08, "marble")
        k.gable_roof(0.1, hy - d / 2 - 0.12, zz + h + 0.08, pw + 0.06, 0.34, 0.3, roof, axis="y", wall="marble",
                     over=0.03, gable_over=0.02, ridge_mat="gold" if t >= 4 else None, ridge_tint=GOLD)
        if t == 5:
            for i in range(4):
                k.column(0.1 + w / 2 + 0.2, hy - d / 2 + 0.15 + i * (d - 0.3) / 3, zz, h, 0.06)
            k.box(0.1 + w / 2 + 0.12, hy, zz + h, 0.34, d + 0.06, 0.08, "marble")
        k.door(0.1, hy - d / 2, zz, 0.36, 0.52, "f", "door_double", step=None)
        for o in (-0.55, 0.55):
            k.window(0.1 + o, hy - d / 2, zz + h * 0.4, 0.18, 0.26, "f", "window_arch", "marble")
        for o in (-0.45, 0.0, 0.45):
            k.window(0.1 + w / 2, hy + o, zz + h * 0.4, 0.18, 0.26, "r", "window_arch", "marble")
        zr = zz + h
        if t == 3:
            k.hip_roof(0.1, hy, zr, w, d, 0.7, roof, over=0.1)
        else:
            gold_band(k, 0.1, hy, zr - 0.06, w, d, 0.06)
            k.hip_roof(0.1, hy, zr, w, d, 0.45, roof, over=0.1, top=0.5 if t == 4 else 0.6, top_mat="cobble")
            dr = pick(t, 0, 0, 0, 0.45, 0.56)
            ztop = zr + 0.45
            k.cyl(0.1, hy, ztop - 0.05, dr, 0.3, 12, wall[0], wall[1], caps="")
            k.cyl(0.1, hy, ztop + 0.25, dr + 0.04, 0.05, 12, "gold", GOLD, caps="t")
            k.dome(0.1, hy, ztop + 0.3, dr, dr * 0.95, 12, 4, "roof_tiles", roof, mix(roof, "#ffffff", 0.3))
            k.finial(0.1, hy, ztop + 0.3 + dr * 0.95 - 0.02, 0.1)
            for f in "fr":
                with k.face(f, (0.1, hy, ztop + 0.02)):
                    k.quad((-0.08, -dr * 0.99, 0), (0.08, -dr * 0.99, 0), (0.08, -dr * 0.99, 0.2), (-0.08, -dr * 0.99, 0.2), "window_arch")
        # tower(s)
        th = pick(t, 0, 0, 1.8, 2.1, 2.5)
        k.round_tower(-1.08, 0.98, z, 0.33, th, wall[0], wall[1], roof_tint=roof, roof_h=0.8,
                      finial=0.06 if t >= 4 else None, slits=2)
        if t == 5:
            k.round_tower(1.12, 1.02, z, 0.3, 2.2, wall[0], wall[1], roof_tint=roof, roof_h=0.75, finial=0.06, slits=2)
            k.flag(-1.08, 0.98, z + th + 0.84, 0.4, roof, 0.2)
        for sx in (-1, 1):
            k.standard(0.1 + sx * 0.85, -1.15, z, pick(t, 0, 0, 0.8, 0.9, 1.0), "banner_blue", w=0.17)
        if t >= 4:
            k.bush(-1.15, -0.9, z, 0.2, 5)
            k.bush(1.25, -0.6, z, 0.17, 6)


BUILDERS = {
    "city_hall": (build_city_hall, 4),
    "farm": (build_farm, 2),
    "lumber_mill": (build_lumber_mill, 2),
    "quarry": (build_quarry, 2),
    "goldmine": (build_goldmine, 2),
    "storehouse": (build_storehouse, 2),
    "barracks": (build_barracks, 3),
    "archery_range": (build_archery_range, 3),
    "stable": (build_stable, 3),
    "siege_workshop": (build_siege_workshop, 3),
    "hospital": (build_hospital, 2),
    "academy": (build_academy, 3),
}
TIERS = (1, 2, 3, 4, 5)


def export(kind, tier, out_dir):
    build, _fp = BUILDERS[kind]
    clear_scene()
    k = Kit()
    build(k, tier)
    name = f"{kind}_t{tier}"
    obj = k.to_object(name)
    path = os.path.join(out_dir, name + ".glb")
    export_glb(path, [obj])
    print(f"exported {name}: {k.tri_count()} tris")


def main():
    argv = script_args()
    if not argv:
        sys.exit("usage: blender -b -P build_buildings.py -- <out_dir> [kind[:tier] ...]")
    out_dir = os.path.abspath(argv[0])
    os.makedirs(out_dir, exist_ok=True)
    jobs = []
    for spec in argv[1:] or list(BUILDERS):
        kind, _, tier = spec.partition(":")
        if kind not in BUILDERS:
            sys.exit(f"unknown building kind: {kind}")
        jobs += [(kind, int(tier))] if tier else [(kind, t) for t in TIERS]
    for kind, tier in jobs:
        export(kind, tier, out_dir)


if __name__ == "__main__":
    main()
