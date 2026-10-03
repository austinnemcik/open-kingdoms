"""Generate the city's surroundings: wall, terrain, forests and small props.

Run:
    blender -b --factory-startup -P tools/blender/build_scenery.py -- client/assets/models/scenery [what ...]

`what` is any of: wall terrain scatter props (default: all).

Outputs (Godot coordinates: the 40x40 city grid is centred on the origin):

* city_wall.glb   crenellated wall, corner towers and four gates just outside
                  the buildable grid (atlas material).
* terrain.glb     ground mesh: flat under the city, rolling hills, a river
                  valley with a lake and a ring of mountains. Vertex colours are
                  masks for ground.gdshader (R rock, G grass variation, B sand).
* scatter.glb     every tree, bush and boulder outside the wall merged into
                  one mesh (atlas material).
* prop_*.glb      small set pieces the client scatters on free city tiles.

Everything is deterministic: fixed seeds, no clocks.
See docs/ART_BIBLE.md for the style rules.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okkit import Kit, clear_scene, export_glb, mix, script_args  # noqa: E402

CITY_HALF = 20.0  # half the buildable grid
WALL_LINE = 21.3  # wall centre line, just outside the grid
WALL_H = 1.4
WALL_T = 0.8
GATE_HALF = 1.6  # half-width of the gate opening
TERRAIN_HALF = 112.0
WATER_LEVEL = -0.35
BLUE = "#3f66bd"

# River centre line (Blender x, y; Godot z = -y) and half-widths. It curls round
# the far corner of the city so it shows at the top of the default view.
RIVER = [(-112, -12, 3.0), (-70, -4, 3.0), (-50, 3, 3.2), (-38, 12, 3.4), (-34.5, 27, 4.0), (-30, 37, 6.5),
         (-17, 41, 4.0), (4, 38.5, 3.4), (28, 37, 3.2), (52, 46, 3.2), (80, 43, 3.0), (112, 50, 3.0)]


def _catmull_rom(points, steps=6):
    """Round the corners of a polyline of (x, y, width) points."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps):
            t = s / steps
            out.append(tuple(
                0.5 * (2 * p1[c] + (p2[c] - p0[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t * t
                       + (3 * p1[c] - p0[c] - 3 * p2[c] + p3[c]) * t ** 3) for c in range(3)))
    out.append(points[-1])
    return out


RIVER = _catmull_rom(RIVER)


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def river_dist(x, y):
    """(distance to the river centre line, half-width there)."""
    best, width = 1e9, 3.0
    for (ax, ay, aw), (bx, by, bw) in zip(RIVER, RIVER[1:]):
        dx, dy = bx - ax, by - ay
        t = min(1.0, max(0.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        d = math.hypot(x - ax - dx * t, y - ay - dy * t)
        if d < best:
            best, width = d, aw + (bw - aw) * t
    return best, width


def height(x, y):
    d = max(abs(x), abs(y))
    if d < 24.0:
        return 0.0
    r = math.hypot(x, y)
    hills = noise.fractal(Vector((x * 0.03 + 11.3, y * 0.03 + 4.7, 0.0)), 1.0, 2.0, 4)
    h = 1.3 + hills * 2.8
    ridged = noise.ridged_multi_fractal(Vector((x * 0.017 + 7.1, y * 0.017 + 3.3, 0.5)), 1.0, 2.1, 5, 1.0, 2.0)
    h += smooth(50, 88, r) * (5.0 + min(ridged, 3.0) * 8.5)
    h = max(h, 0.25)
    h *= smooth(24.0, 40.0, d)
    dr, w = river_dist(x, y)
    bank = smooth(w, w + 10.0, dr)
    h = h * bank + 0.12 * (1 - bank) * smooth(24.0, 27.0, d)
    h -= (1 - smooth(w * 0.4, w, dr)) * 1.3
    return h


def slope(x, y, e=0.6):
    return math.hypot(height(x + e, y) - height(x - e, y), height(x, y + e) - height(x, y - e)) / (2 * e)


# --- terrain -------------------------------------------------------------------------


def axis_coords():
    """Vertex coordinates along one axis: fine near the city, coarse far away."""
    out, x = [0.0], 0.0
    while x < TERRAIN_HALF:
        x += 1.5 if x < 62 else 4.0
        out.append(min(x, TERRAIN_HALF))
    return [-v for v in reversed(out[1:])] + out


def build_terrain():
    xs = axis_coords()
    n = len(xs)
    verts, cols = [], []
    for y in xs:
        for x in xs:
            h = height(x, y)
            verts.append((x, y, h))
            dr, w = river_dist(x, y)
            rock = max(smooth(0.5, 1.0, slope(x, y)), smooth(9.0, 14.0, h) * 0.8)
            grass = 0.5 + 0.5 * noise.noise(Vector((x * 0.045 + 3.0, y * 0.045 + 9.0, 2.0)))
            sand = (1 - smooth(w - 0.4, w + 1.3, dr)) * smooth(24.0, 26.0, max(abs(x), abs(y)))
            cols.append((rock, grass, sand))
    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            faces.append((a, a + 1, a + n + 1, a + n))
    mesh = bpy.data.meshes.new("terrain")
    mesh.from_pydata(verts, [], faces)
    layer = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="CORNER")
    mesh.polygons.foreach_set("use_smooth", [True] * len(faces))
    loop_verts = [0] * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", loop_verts)
    layer.data.foreach_set("color", [c for vi in loop_verts for c in (*cols[vi], 1.0)])
    mesh.color_attributes.active_color = layer
    mesh.color_attributes.render_color_index = 0
    mesh.update()
    obj = bpy.data.objects.new("terrain", mesh)
    bpy.context.collection.objects.link(obj)
    return obj, len(faces) * 2


# --- scatter -------------------------------------------------------------------------

TREE_GREENS = [("#3f7a34", "#9acb55"), ("#3a7238", "#86bf52"), ("#4a8336", "#aed460"), ("#356b3c", "#7fb84e"),
               ("#5c8a34", "#c4d65e")]


def on_gate_road(x, y, pad=2.6):
    return (abs(x) < pad or abs(y) < pad) and max(abs(x), abs(y)) < 36


def build_scatter():
    k = Kit()
    rnd = random.Random(20261003)
    trees = bushes = rocks = 0
    placed = []
    for _ in range(15000):
        x, y = rnd.uniform(-96, 96), rnd.uniform(-96, 96)
        d = max(abs(x), abs(y))
        if d < 23.4 or on_gate_road(x, y):
            continue
        h = height(x, y)
        dr, w = river_dist(x, y)
        if h < 0.1 or dr < w + 1.4 or h > 13.0:
            continue
        sl = slope(x, y)
        forest = 0.5 + 0.5 * noise.noise(Vector((x * 0.055 + 40.0, y * 0.055 + 17.0, 0.0)))
        r = math.hypot(x, y)
        roll = rnd.random()
        kind_roll = rnd.random()
        size = rnd.random()
        seed = rnd.randrange(1 << 30)
        if sl > 0.75 or roll > 0.988:
            if sl > 0.75 and roll > 0.3:
                continue
            if any((x - px) ** 2 + (y - py) ** 2 < 4.0 for px, py in placed[-40:]):
                continue
            k.rock(x, y, h - 0.1, 0.6 + size * 1.3, seed, ("#b0a89c", "#a39a90", "#bdb6aa")[seed % 3], 0.75)
            rocks += 1
            continue
        # open meadows near the wall, thick woods in noise patches further out
        density = smooth(0.38, 0.62, forest) * 0.9 + 0.03
        density *= 0.35 + 0.65 * smooth(24, 34, d)
        if roll > density:
            if roll < density + 0.02:
                lo, hi = TREE_GREENS[seed % len(TREE_GREENS)]
                k.bush(x, y, h - 0.03, 0.35 + size * 0.35, seed, lo, hi)
                bushes += 1
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 1.7 for px, py in placed):
            continue
        placed.append((x, y))
        far = r > 58
        pine = kind_roll < smooth(2.0, 7.0, h) * 0.85 + 0.12
        s = 1.25 + size * 0.9
        if pine:
            k.tree(x, y, h - 0.05, s * 1.15, "pine", seed, n=5 if far else 7)
        else:
            lo, hi = TREE_GREENS[seed % len(TREE_GREENS)]
            k.tree(x, y, h - 0.05, s, "simple" if far or kind_roll > 0.8 else "round", seed, lo, hi,
                   n=5 if far else 7)
        trees += 1
    print(f"scatter: {trees} trees, {bushes} bushes, {rocks} rocks")
    return k


# --- city wall -----------------------------------------------------------------------


def wall_run(k, x0, x1, y):
    """Straight wall from x0 to x1 in the side's local frame (outside is -y)."""
    cx, ln = (x0 + x1) / 2, x1 - x0
    k.box(cx, y, 0, ln, WALL_T + 0.16, 0.3, "stone_block", "#d6d0c8", skip="b", taper=(1.0, 0.92))
    k.box(cx, y, 0.3, ln, WALL_T, WALL_H - 0.3, "stone_brick", skip="bt")
    k.box(cx, y, WALL_H - 0.14, ln, WALL_T + 0.14, 0.14, "stone_block", skip="b", top="cobble")
    k.crenels(cx, y - 0.02, WALL_H, ln, WALL_T + 0.14, 0.3, 0.26, "stone_brick", None, sides="f")
    k.box(cx, y + WALL_T / 2 + 0.01, WALL_H, ln, 0.1, 0.1, "stone_brick", skip="b")


def square_tower(k, x, y, s, h, roof=None, flag=False):
    k.box(x, y, 0, s + 0.16, s + 0.16, 0.35, "stone_block", "#d6d0c8", skip="b", taper=0.94)
    k.box(x, y, 0.35, s, s, h - 0.35, "stone_brick", skip="bt", taper=0.96)
    top = s * 0.96 + 0.2
    k.box(x, y, h - 0.2, top, top, 0.2, "stone_block", skip="b", top="cobble")
    for face, (fx, fy) in (("f", (0, -1)), ("r", (1, 0)), ("k", (0, 1)), ("l", (-1, 0))):
        k.window(x + fx * s * 0.485, y + fy * s * 0.485, h * 0.55, 0.2, 0.3, face, "slit", None)
    if roof:
        k.box(x, y, h, top - 0.3, top - 0.3, 0.35, "stone_brick", skip="bt")
        k.crenels(x, y, h, top, top, 0.26, 0.22, "stone_brick")
        k.hip_roof(x, y, h + 0.35, top - 0.3, top - 0.3, s * 0.75, roof, over=0.16)
        k.finial(x, y, h + 0.35 + s * 0.75 - 0.03, 0.12)
    else:
        k.crenels(x, y, h, top, top, 0.28, 0.24, "stone_brick")
    if flag:
        k.flag(x, y, h + (0.35 + s * 0.75 if roof else 0.0), 1.1, BLUE, 0.55)


def gatehouse(k, y):
    for sx in (-1, 1):
        square_tower(k, sx * (GATE_HALF + 0.75), y, 1.5, 2.7, BLUE)
        # arch haunches
        k.poly([(sx * GATE_HALF, y - 0.5, 1.25), (sx * (GATE_HALF - 0.7), y - 0.5, 1.95), (sx * GATE_HALF, y - 0.5, 1.95)][::sx],
               "stone_block", out=(0, -1, 0))
        k.poly([(sx * GATE_HALF, y + 0.5, 1.25), (sx * (GATE_HALF - 0.7), y + 0.5, 1.95), (sx * GATE_HALF, y + 0.5, 1.95)][::-sx],
               "stone_block", out=(0, 1, 0))
        k.poly([(sx * GATE_HALF, y - 0.5, 1.25), (sx * GATE_HALF, y + 0.5, 1.25), (sx * (GATE_HALF - 0.7), y + 0.5, 1.95),
                (sx * (GATE_HALF - 0.7), y - 0.5, 1.95)][::sx], "stone_block", "#8f8a86", out=(-sx, 0, -1))
        k.banner(sx * (GATE_HALF + 0.75), y - 0.76, 1.05, 0.42, 0.9, "f", "banner_blue")
    k.box(0, y, 1.95, GATE_HALF * 2, 1.0, 0.55, "stone_brick", skip="", top="cobble")
    k.box(0, y, 2.5, GATE_HALF * 2 + 0.1, 1.14, 0.12, "stone_block", skip="b", top="cobble")
    k.crenels(0, y, 2.62, GATE_HALF * 2, 1.14, 0.28, 0.24, "stone_brick", None, sides="fk")
    k.disc(0, y - 0.5, 2.25, 0.24, "f", "shield", 12)
    # raised portcullis teeth
    for i in range(7):
        px = -GATE_HALF + 0.35 + i * (GATE_HALF * 2 - 0.7) / 6
        k.box(px, y, 1.72, 0.06, 0.06, 0.24, "flat", "#4a4d58", skip="t")


def build_wall():
    k = Kit()
    corner = WALL_LINE
    for i in range(4):
        with k.push((0, 0, 0), i * math.pi / 2):
            y = -WALL_LINE
            gate_edge = GATE_HALF + 1.5
            mid = (corner + gate_edge) / 2
            for sx in (-1, 1):
                lo, hi = sorted((sx * (gate_edge - 0.1), sx * (mid - 0.85)))
                wall_run(k, lo, hi, y)
                lo, hi = sorted((sx * (mid + 0.85), sx * (corner - 1.0)))
                wall_run(k, lo, hi, y)
                square_tower(k, sx * mid, y - 0.15, 1.7, 2.2, flag=sx > 0)
            gatehouse(k, y)
            k.round_tower(-corner, -corner, 0, 1.3, 3.1, "stone_brick", None, n=10, roof_tint=BLUE, roof_h=2.3,
                          slits=2, finial=0.14)
            k.cyl(-corner, -corner, 0, 1.45, 0.35, 10, "stone_block", "#d6d0c8", r2=1.32, caps="", phase=math.pi / 10)
            k.flag(-corner, -corner, 3.1 + 2.3, 1.0, BLUE, 0.5)
    return k


# --- props ---------------------------------------------------------------------------


def prop_lamp(k):
    k.box(0, 0, 0, 0.16, 0.16, 0.1, "stone_block", skip="b")
    k.cyl(0, 0, 0.1, 0.035, 0.85, 6, "timber", caps="")
    k.beam((0, 0, 0.9), (0.2, 0, 0.9), 0.035)
    k.box(0.2, 0, 0.66, 0.12, 0.12, 0.17, "gold", "#fff2c0", skip="", taper=1.25)
    k.cone(0.2, 0, 0.83, 0.1, 0.08, 4, "flat", "#4a3a2e", phase=math.pi / 4)


def prop_well(k):
    k.cyl(0, 0, 0, 0.36, 0.32, 10, "stone_brick", caps="t", cap_mat="flat", cap_tint="#3d7fa8")
    k.cyl(0, 0, 0.26, 0.4, 0.08, 10, "stone_block", r2=0.4, caps="t", cap_mat="flat", cap_tint="#3d7fa8")
    for sx in (-1, 1):
        k.box(sx * 0.36, 0, 0, 0.07, 0.07, 0.85, "timber")
    k.beam((-0.36, 0, 0.66), (0.36, 0, 0.66), 0.04)
    k.gable_roof(0, 0, 0.85, 0.8, 0.5, 0.3, "#b5533c", over=0.08)
    k.barrel(0.0, 0.0, 0.36, 0.06, 0.13)


def prop_stall(k, tint):
    k.box(0, 0.05, 0, 0.9, 0.4, 0.26, "wood_planks", skip="b")
    for sx in (-1, 1):
        k.box(sx * 0.45, 0.25, 0, 0.05, 0.05, 0.85, "timber")
        k.box(sx * 0.45, -0.25, 0, 0.05, 0.05, 0.68, "timber")
    for i in range(4):
        x0, x1 = -0.5 + i * 0.25, -0.25 + i * 0.25
        c = tint if i % 2 == 0 else "#f4ecd8"
        k.poly([(x0, -0.34, 0.66), (x1, -0.34, 0.66), (x1, 0.3, 0.88), (x0, 0.3, 0.88)], "fabric", c, out=(0, -0.3, 1))
        k.poly([(x0, -0.34, 0.56), (x1, -0.34, 0.56), (x1, -0.34, 0.66), (x0, -0.34, 0.66)], "fabric", c, out=(0, -1, 0))
    for i, c in enumerate(("#d9534a", "#e8b84a", "#7fb84e")):
        k.blob(-0.26 + i * 0.26, 0.02, 0.3, 0.1, 0.1, 0.07, "flat", mix(c, "#000000", 0.3), c, n=6, rings=3, seed=i,
               jitter=0.2, bottom=-0.2)
    k.crate(0.62, 0.1, 0, 0.2, 0.3)


def prop_flowers(k, seed):
    rnd = random.Random(seed)
    for i in range(7):
        x, y = rnd.uniform(-0.32, 0.32), rnd.uniform(-0.32, 0.32)
        c = ("#f2e27a", "#e7a6c8", "#f4f0e6", "#e0705a")[rnd.randrange(4)]
        k.blob(x, y, 0.05, 0.07, 0.07, 0.05, "foliage", "#3f8a4a", "#8cc152", n=5, rings=3, seed=i, bottom=-0.3)
        k.blob(x, y, 0.11, 0.035, 0.035, 0.03, "flat", c, c, n=5, rings=3, seed=i, jitter=0.0, bottom=-0.6)


def build_props():
    """name -> Kit."""
    out = {}

    def add(name, fn):
        k = Kit()
        fn(k)
        out[name] = k

    add("prop_tree_a", lambda k: k.tree(0, 0, 0, 1.0, "round", 3))
    add("prop_tree_b", lambda k: k.tree(0, 0, 0, 1.0, "round", 8, "#4a8336", "#aed460"))
    add("prop_tree_c", lambda k: k.tree(0, 0, 0, 1.0, "simple", 5, "#5c8a34", "#c4d65e"))
    add("prop_pine", lambda k: k.tree(0, 0, 0, 1.0, "pine", 4))
    add("prop_bush", lambda k: (k.bush(0, 0, 0, 0.26, 2), k.bush(0.22, 0.12, 0, 0.17, 3)))
    add("prop_rock", lambda k: (k.rock(0, 0, 0, 0.3, 4), k.rock(0.28, -0.12, 0, 0.16, 6)))
    add("prop_flowers", lambda k: prop_flowers(k, 1))
    add("prop_lamp", prop_lamp)
    add("prop_well", prop_well)
    add("prop_stall_a", lambda k: prop_stall(k, "#c8473a"))
    add("prop_stall_b", lambda k: prop_stall(k, "#3f66bd"))
    add("prop_cart", lambda k: k.cart(0, 0, 0, 0.3, "hay"))
    return out


# --- main ----------------------------------------------------------------------------


def export_kit(k, name, out_dir, ao=True):
    clear_scene()
    obj = k.to_object(name, ao=ao)
    export_glb(os.path.join(out_dir, f"{name}.glb"), [obj])
    print(f"exported {name}: {k.tri_count()} tris")


def main():
    argv = script_args()
    if not argv:
        sys.exit("usage: blender -b -P build_scenery.py -- <out_dir> [wall|terrain|scatter|props ...]")
    out_dir = os.path.abspath(argv[0])
    os.makedirs(out_dir, exist_ok=True)
    what = argv[1:] or ["wall", "terrain", "scatter", "props"]
    if "wall" in what:
        export_kit(build_wall(), "city_wall", out_dir)
    if "terrain" in what:
        clear_scene()
        obj, tris = build_terrain()
        export_glb(os.path.join(out_dir, "terrain.glb"), [obj])
        print(f"exported terrain: {tris} tris")
    if "scatter" in what:
        export_kit(build_scatter(), "scatter", out_dir, ao=False)
    if "props" in what:
        for name, k in build_props().items():
            export_kit(k, name, out_dir)


if __name__ == "__main__":
    main()
