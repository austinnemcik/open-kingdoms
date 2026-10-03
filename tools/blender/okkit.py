"""Open Kingdoms model kit: a tiny procedural modelling library for Blender.

Everything is emitted as textured, vertex-coloured polygons into a `Kit`,
which then bakes ambient occlusion into the vertex colours and exports a .glb.
Conventions (see docs/ART_BIBLE.md):

* 1 unit = 1 city tile, +Z up, the building front faces -Y (Godot +Z, towards
  the default camera). Models stand on z = 0 centred on the origin.
* One shared atlas (atlas_layout.py). `mat` is either a tiling material name
  or a decal name. Tiling faces get world-scaled UVs and are split
  automatically where they exceed the atlas cell.
* `tint` multiplies the texture: a "#rrggbb" sRGB string (or a list of them,
  one per point, for gradients). Neutral textures (roof_tiles, foliage, flat,
  fabric, rock) are designed to be tinted.
* glb files carry no material: the client applies the shared atlas material.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_layout as L  # noqa: E402

FACE_ROT = {"f": 0.0, "r": math.pi / 2, "k": math.pi, "l": -math.pi / 2}
_tint_cache = {}


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def tint_rgb(t):
    """'#rrggbb' (sRGB) or an (r, g, b) linear tuple -> linear tuple."""
    if t is None:
        return (1.0, 1.0, 1.0)
    if isinstance(t, str):
        if t not in _tint_cache:
            h = t.lstrip("#")
            _tint_cache[t] = tuple(lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))
        return _tint_cache[t]
    return tuple(t)


def mix(a, b, t):
    a, b = tint_rgb(a), tint_rgb(b)
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _normal(pts):
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n.normalized() if n.length > 1e-12 else Vector((0, 0, 1))


def _lerp_item(a, b, t):
    return (a[0].lerp(b[0], t),
            (a[1][0] + (b[1][0] - a[1][0]) * t, a[1][1] + (b[1][1] - a[1][1]) * t),
            tuple(a[2][i] + (b[2][i] - a[2][i]) * t for i in range(3)),
            a[3].lerp(b[3], t))


def _clip(items, axis, lo, hi):
    for bound, sign in ((lo, 1.0), (hi, -1.0)):
        out = []
        for i in range(len(items)):
            a, b = items[i], items[(i + 1) % len(items)]
            da = (a[1][axis] - bound) * sign
            db = (b[1][axis] - bound) * sign
            if da >= -1e-9:
                out.append(a)
            if (da > 1e-9 and db < -1e-9) or (da < -1e-9 and db > 1e-9):
                out.append(_lerp_item(a, b, da / (da - db)))
        items = out
        if len(items) < 3:
            return []
    return items


def _shift(items, axis, amount):
    out = []
    for p, uv, c, n in items:
        uv = (uv[0] - amount, uv[1]) if axis == 0 else (uv[0], uv[1] - amount)
        out.append((p, uv, c, n))
    return out


def _split(items, axis):
    """Split a polygon so each piece spans at most two texture periods."""
    lo = min(it[1][axis] for it in items)
    items = _shift(items, axis, math.floor(lo + 1e-6))
    hi = max(it[1][axis] for it in items)
    lo = min(it[1][axis] for it in items)
    if hi <= 2.0 + 1e-6:
        if hi - lo > 1.0:  # give spans of 1..2 periods the whole cell
            pass
        return [items]
    out = []
    k = 0
    while 2 * k < hi - 1e-6:
        piece = _clip(items, axis, 2.0 * k, 2.0 * k + 2.0)
        if len(piece) >= 3:
            out.append(_shift(piece, axis, 2.0 * k))
        k += 1
    return out


class _Push:
    def __init__(self, kit, m):
        self.kit, self.m = kit, m

    def __enter__(self):
        self.kit.m.append(self.kit.m[-1] @ self.m)

    def __exit__(self, *a):
        self.kit.m.pop()


class Kit:
    def __init__(self):
        self.polys = []  # each: list of (co, atlas_uv, colour, normal)
        self.m = [Matrix.Identity(4)]

    # --- core --------------------------------------------------------------

    def push(self, loc=(0, 0, 0), rot=0.0, scale=1.0, rx=0.0, ry=0.0):
        s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
        m = (Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rot, 4, "Z") @ Matrix.Rotation(ry, 4, "Y")
             @ Matrix.Rotation(rx, 4, "X") @ Matrix.Diagonal((s[0], s[1], s[2], 1.0)))
        return _Push(self, m)

    def face(self, face, loc=(0, 0, 0)):
        """Local frame on a wall: x along the wall, -y outwards, z up."""
        return self.push(loc, FACE_ROT[face])

    def poly(self, pts, mat, tint=None, uv=None, normals=None, out=None):
        pts = [Vector(p) for p in pts]
        n = len(pts)
        cols = [tint_rgb(t) for t in tint] if isinstance(tint, list) else [tint_rgb(tint)] * n
        fn = _normal(pts)
        if out is not None and fn.dot(Vector(out)) < 0:
            pts.reverse()
            cols.reverse()
            if uv is not None:
                uv = list(reversed(uv))
            if normals is not None:
                normals = list(reversed(normals))
            fn = -fn
        nrm = [Vector(v).normalized() for v in normals] if normals is not None else [fn] * n
        if mat in L.DECALS:
            if uv is None:
                uv = [(0, 0), (1, 0), (1, 1), (0, 1)][:n]
            items = [(pts[i], L.decal_uv(mat, uv[i][0], uv[i][1]), cols[i], nrm[i]) for i in range(n)]
            pieces = [items]
        else:
            period = L.TILES[mat][3]
            if uv is None:
                if abs(fn.z) > 0.95:
                    uv = [(p.x / period, p.y / period) for p in pts]
                else:
                    t = Vector((-fn.y, fn.x, 0)).normalized()
                    b = fn.cross(t)
                    uv = [(p.dot(t) / period, p.dot(b) / period) for p in pts]
            items = [(pts[i], (uv[i][0], uv[i][1]), cols[i], nrm[i]) for i in range(n)]
            pieces = []
            for a in _split(items, 0):
                for b in _split(a, 1):
                    pieces.append([(p, L.tile_uv(mat, u[0], u[1]), c, nn) for p, u, c, nn in b])
        m = self.m[-1]
        m3 = m.to_3x3()
        nm = m3.inverted_safe().transposed()
        flip = m3.determinant() < 0
        for piece in pieces:
            # drop coincident points (degenerate quads become triangles)
            clean = []
            for it in piece:
                if not clean or (it[0] - clean[-1][0]).length > 1e-6:
                    clean.append(it)
            if len(clean) > 1 and (clean[0][0] - clean[-1][0]).length < 1e-6:
                clean.pop()
            if len(clean) < 3:
                continue
            world = [(m @ p, u, c, (nm @ nn).normalized()) for p, u, c, nn in clean]
            if flip:
                world.reverse()
            self.polys.append(world)

    def tri_count(self):
        return sum(len(p) - 2 for p in self.polys)

    # --- primitives --------------------------------------------------------

    def quad(self, a, b, c, d, mat, tint=None, **kw):
        self.poly([a, b, c, d], mat, tint, **kw)

    def box(self, x, y, z, sx, sy, sz, mat, tint=None, taper=1.0, skip="b", top=None, top_tint=None, rot=0.0):
        """Box with its bottom centre at (x, y, z). skip: any of f r k l t b."""
        if rot:
            with self.push((x, y, z), rot):
                self.box(0, 0, 0, sx, sy, sz, mat, tint, taper, skip, top, top_tint)
            return
        tx, ty = taper if isinstance(taper, (tuple, list)) else (taper, taper)
        hx, hy = sx / 2, sy / 2
        b = [(x - hx, y - hy, z), (x + hx, y - hy, z), (x + hx, y + hy, z), (x - hx, y + hy, z)]
        t = [(x - hx * tx, y - hy * ty, z + sz), (x + hx * tx, y - hy * ty, z + sz),
             (x + hx * tx, y + hy * ty, z + sz), (x - hx * tx, y + hy * ty, z + sz)]
        sides = {"f": (0, 1), "r": (1, 2), "k": (2, 3), "l": (3, 0)}
        for key, (i, j) in sides.items():
            if key not in skip:
                self.poly([b[i], b[j], t[j], t[i]], mat, tint)
        if "t" not in skip:
            self.poly(t, top or mat, top_tint if top_tint is not None else tint)
        if "b" not in skip:
            self.poly(list(reversed(b)), mat, tint)

    def beam(self, p0, p1, w, h=None, mat="timber", tint=None, up=(0, 0, 1), ends=True):
        """Rectangular bar between two points (posts, rails, braces, arms)."""
        p0, p1 = Vector(p0), Vector(p1)
        h = w if h is None else h
        axis = p1 - p0
        length = axis.length
        if length < 1e-6:
            return
        a = axis / length
        side = a.cross(Vector(up))
        if side.length < 1e-4:
            side = a.cross(Vector((1, 0, 0)))
        side.normalize()
        u2 = side.cross(a).normalized()
        period = L.TILES[mat][3] if mat in L.TILES else 1.0
        corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        ring0 = [p0 + side * (cx * w / 2) + u2 * (cy * h / 2) for cx, cy in corners]
        ring1 = [p + axis for p in ring0]
        centre = p0 + axis / 2
        for i in range(4):
            j = (i + 1) % 4
            mid = (ring0[i] + ring0[j]) / 2 - p0
            width = (ring0[j] - ring0[i]).length / period
            uv = [(0, 0), (length / period, 0), (length / period, width), (0, width)]
            self.poly([ring0[i], ring1[i], ring1[j], ring0[j]], mat, tint, uv=uv if mat in L.TILES else None, out=mid)
        if ends:
            self.poly(ring0, mat, tint, out=-a)
            self.poly(ring1, mat, tint, out=a)
        del centre

    def cyl(self, x, y, z, r, h, n=8, mat="stone_brick", tint=None, r2=None, caps="t", smooth=True,
            cap_mat=None, cap_tint=None, cap_decal=None, tint_top=None, phase=0.0):
        """Upright (optionally tapered) cylinder. caps: 't', 'b', 'tb' or ''."""
        r2 = r if r2 is None else r2
        period = L.TILES[mat][3] if mat in L.TILES else 1.0
        c0 = tint_rgb(tint)
        c1 = tint_rgb(tint_top) if tint_top is not None else c0
        slope = (r - r2) / h if h else 0.0
        ang = [phase + i * 2 * math.pi / n for i in range(n + 1)]
        for i in range(n):
            a0, a1 = ang[i], ang[i + 1]
            p = [(x + math.cos(a0) * r, y + math.sin(a0) * r, z), (x + math.cos(a1) * r, y + math.sin(a1) * r, z),
                 (x + math.cos(a1) * r2, y + math.sin(a1) * r2, z + h),
                 (x + math.cos(a0) * r2, y + math.sin(a0) * r2, z + h)]
            if mat in L.TILES:
                arc = 2 * math.pi * max(r, r2) / n / period
                uv = [(i * arc, z / period), ((i + 1) * arc, z / period), ((i + 1) * arc, (z + h) / period),
                      (i * arc, (z + h) / period)]
            else:
                uv = [(i / n, 0), ((i + 1) / n, 0), ((i + 1) / n, 1), (i / n, 1)]
            nr = None
            if smooth:
                n0 = (math.cos(a0), math.sin(a0), slope)
                n1 = (math.cos(a1), math.sin(a1), slope)
                nr = [n0, n1, n1, n0]
            self.poly(p, mat, [c0, c0, c1, c1], uv=uv, normals=nr)
        for which in caps:
            rr, zz = (r2, z + h) if which == "t" else (r, z)
            if rr < 1e-4:
                continue
            pts = [(x + math.cos(a) * rr, y + math.sin(a) * rr, zz) for a in ang[:-1]]
            col = cap_tint if cap_tint is not None else (tint_top if (which == "t" and tint_top is not None) else tint)
            if cap_decal:
                uv = [(0.5 + 0.5 * math.cos(a - phase), 0.5 + 0.5 * math.sin(a - phase)) for a in ang[:-1]]
                self.poly(pts, cap_decal, col, uv=uv, out=(0, 0, 1 if which == "t" else -1))
            else:
                self.poly(pts, cap_mat or mat, col, out=(0, 0, 1 if which == "t" else -1))

    def cone(self, x, y, z, r, h, n=8, mat="roof_tiles", tint=None, smooth=False, tint_top=None, phase=0.0):
        self.cyl(x, y, z, r, h, n, mat, tint, r2=0.0, caps="", smooth=smooth, tint_top=tint_top, phase=phase)

    def dome(self, x, y, z, r, h, n=10, rings=4, mat="roof_tiles", tint=None, tint_top=None):
        period = L.TILES[mat][3]
        c0, c1 = tint_rgb(tint), tint_rgb(tint_top if tint_top is not None else tint)

        def pt(i, j):
            a = i * 2 * math.pi / n
            e = j * (math.pi / 2) / rings
            return Vector((x + math.cos(a) * math.cos(e) * r, y + math.sin(a) * math.cos(e) * r, z + math.sin(e) * h))

        def nrm(i, j):
            a = i * 2 * math.pi / n
            e = j * (math.pi / 2) / rings
            return (math.cos(a) * math.cos(e) / r, math.sin(a) * math.cos(e) / r, math.sin(e) / h)

        def col(j):
            return mix(c0, c1, j / rings)

        arc = 2 * math.pi * r / n / period
        rise = (math.pi / 2) * max(r, h) / rings / period
        for j in range(rings):
            for i in range(n):
                idx = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                self.poly([pt(*k) for k in idx], mat, [col(k[1]) for k in idx],
                          uv=[(k[0] * arc, k[1] * rise) for k in idx], normals=[nrm(*k) for k in idx])

    def blob(self, x, y, z, rx, ry, rz, mat="foliage", lo="#3f7a34", hi="#8cc152", n=7, rings=4, seed=0,
             jitter=0.14, bottom=-0.45):
        """Lumpy squashed sphere (foliage, boulders, sacks, haystacks). z is the centre height."""
        rnd = random.Random(seed)
        period = L.TILES[mat][3]
        lo, hi = tint_rgb(lo), tint_rgb(hi)
        e0 = math.asin(bottom)
        grid = []
        for j in range(rings + 1):
            e = e0 + (math.pi / 2 - e0) * j / rings
            row = []
            for i in range(n):
                a = (i + 0.5 * (j % 2)) * 2 * math.pi / n
                k = 1.0 + (rnd.random() - 0.5) * 2 * jitter if j < rings else 1.0
                d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
                p = Vector((x + d.x * rx * k, y + d.y * ry * k, z + d.z * rz * k))
                t = (math.sin(e) - bottom) / (1 - bottom)
                row.append((p, Vector((d.x / rx, d.y / ry, d.z / rz)).normalized(), mix(lo, hi, t ** 0.8),
                            ((i + 0.5 * (j % 2)) * 2 * math.pi * max(rx, ry) / n / period,
                             j * 1.6 * rz / rings / period)))
            grid.append(row)
        for j in range(rings):
            for i in range(n):
                i2 = (i + 1) % n
                wrap = 2 * math.pi * max(rx, ry) / period if i2 == 0 else 0.0

                def item(jj, ii, w=0.0):
                    p, nn, c, u = grid[jj][ii]
                    return p, nn, c, (u[0] + w, u[1])

                if j % 2 == 0:
                    tris = [[item(j, i), item(j, i2, wrap), item(j + 1, i)],
                            [item(j, i2, wrap), item(j + 1, i2, wrap), item(j + 1, i)]]
                else:
                    tris = [[item(j, i), item(j, i2, wrap), item(j + 1, i2, wrap)],
                            [item(j, i), item(j + 1, i2, wrap), item(j + 1, i)]]
                for t3 in tris:
                    self.poly([q[0] for q in t3], mat, [q[2] for q in t3], uv=[q[3] for q in t3],
                              normals=[q[1] for q in t3])

    # --- roofs --------------------------------------------------------------

    def gable_roof(self, x, y, z, w, d, h, tint=None, mat="roof_tiles", axis="x", over=0.12, gable_over=0.08,
                   wall=None, wall_tint=None, trim="timber", trim_tint=None, thick=0.05, ridge=True,
                   ridge_mat=None, ridge_tint=None):
        """Flared gable roof over a w x d box whose top is at z. Ridge runs along `axis`."""
        if axis == "y":
            with self.push((x, y, z), math.pi / 2):
                self.gable_roof(0, 0, 0, d, w, h, tint, mat, "x", over, gable_over, wall, wall_tint, trim,
                                trim_tint, thick, ridge, ridge_mat, ridge_tint)
            return
        s = d / 2
        ln = w / 2 + gable_over
        low = 0.9 * h / s
        prof = [(0.0, h), (0.6 * s, 0.36 * h), (s + over, -over * low)]
        l_up = math.dist(prof[0], prof[1])
        l_lo = math.dist(prof[1], prof[2])
        period = L.TILES[mat][3]
        vv = [(l_lo + l_up) / period, l_lo / period, 0.0]
        with self.push((x, y, z)):
            for side in (1, -1):
                for a, b in ((0, 1), (1, 2)):
                    pts = [(ln, side * prof[b][0], prof[b][1]), (-ln, side * prof[b][0], prof[b][1]),
                           (-ln, side * prof[a][0], prof[a][1]), (ln, side * prof[a][0], prof[a][1])]
                    uv = [(ln * side / period, vv[b]), (-ln * side / period, vv[b]), (-ln * side / period, vv[a]),
                          (ln * side / period, vv[a])]
                    self.poly(pts, mat, tint, uv=uv, out=(0, side, 1))
                e = prof[2]
                self.poly([(-ln, side * e[0], e[1]), (ln, side * e[0], e[1]), (ln, side * e[0], e[1] - thick),
                           (-ln, side * e[0], e[1] - thick)], trim, trim_tint, out=(0, side, 0))
                self.poly([(-ln, side * e[0], e[1] - thick), (ln, side * e[0], e[1] - thick),
                           (ln, side * (s - 0.01), e[1] - thick + 0.0), (-ln, side * (s - 0.01), e[1] - thick)],
                          trim, trim_tint, out=(0, 0, -1))
                for end in (1, -1):
                    for a, b in ((0, 1), (1, 2)):
                        self.poly([(end * ln, side * prof[a][0], prof[a][1]), (end * ln, side * prof[b][0], prof[b][1]),
                                   (end * ln, side * prof[b][0], prof[b][1] - thick * 1.6),
                                   (end * ln, side * prof[a][0], prof[a][1] - thick * 1.6)], trim, trim_tint,
                                  out=(end, 0, 0))
            if wall:
                for end in (1, -1):
                    self.poly([(end * w / 2, -s, 0), (end * w / 2, s, 0), (end * w / 2, 0.6 * s, 0.36 * h),
                               (end * w / 2, 0, h), (end * w / 2, -0.6 * s, 0.36 * h)], wall, wall_tint,
                              out=(end, 0, 0))
            if ridge:
                self.box(0, 0, h - 0.035, 2 * ln + 0.04, 0.075, 0.07, ridge_mat or trim,
                         ridge_tint if ridge_mat else trim_tint)

    def hip_roof(self, x, y, z, w, d, h, tint=None, mat="roof_tiles", over=0.12, top=0.0, trim="timber",
                 trim_tint=None, thick=0.05, top_mat=None, top_tint=None):
        """Flared hip/pyramid roof. `top` > 0 leaves a flat square of that half-size at the apex."""
        rx = max(w - d, 0) / 2 + top
        ry = max(d - w, 0) / 2 + top
        smin = min(w / 2 - rx, d / 2 - ry)
        low = 0.9 * h / smin

        def ring(t, zz):
            ex, ey = rx + (w / 2 - rx) * t, ry + (d / 2 - ry) * t
            return [(-ex, -ey, zz), (ex, -ey, zz), (ex, ey, zz), (-ex, ey, zz)]

        r0 = ring(0.0, h)
        r1 = ring(0.6, 0.36 * h)
        te = 1 + over / smin
        r2 = ring(te, -over * low)
        outs = [(0, -1, 1), (1, 0, 1), (0, 1, 1), (-1, 0, 1)]
        with self.push((x, y, z)):
            for i in range(4):
                j = (i + 1) % 4
                self.poly([r1[i], r1[j], r0[j], r0[i]], mat, tint, out=outs[i])
                self.poly([r2[i], r2[j], r1[j], r1[i]], mat, tint, out=outs[i])
                a, b = Vector(r2[i]), Vector(r2[j])
                dn = Vector((0, 0, -thick))
                self.poly([a, b, b + dn, a + dn], trim, trim_tint, out=(outs[i][0], outs[i][1], 0))
            if top > 0:
                self.poly(r0, top_mat or mat, top_tint if top_mat else tint, out=(0, 0, 1))

    def cone_roof(self, x, y, z, r, h, n=8, tint=None, mat="roof_tiles", phase=0.0, finial=None):
        """Flared, faceted cone roof (turrets)."""
        rings = [(r, 0.0), (r * 0.5, h * 0.42), (0.0, h)]
        for (ra, za), (rb, zb) in zip(rings, rings[1:]):
            for i in range(n):
                a0 = phase + i * 2 * math.pi / n
                a1 = phase + (i + 1) * 2 * math.pi / n
                am = (a0 + a1) / 2
                self.poly([(x + math.cos(a0) * ra, y + math.sin(a0) * ra, z + za),
                           (x + math.cos(a1) * ra, y + math.sin(a1) * ra, z + za),
                           (x + math.cos(a1) * rb, y + math.sin(a1) * rb, z + zb),
                           (x + math.cos(a0) * rb, y + math.sin(a0) * rb, z + zb)], mat, tint,
                          out=(math.cos(am), math.sin(am), 0.5))
        if finial:
            self.finial(x, y, z + h - 0.02, finial)

    def finial(self, x, y, z, size=0.08, tint=None):
        self.cyl(x, y, z, size * 0.25, size * 1.2, 5, "gold", tint, caps="")
        self.blob(x, y, z + size * 1.5, size * 0.55, size * 0.55, size * 0.55, "gold", "#ffffff", "#ffffff", n=5,
                  rings=3, jitter=0.0, bottom=-0.95)

    # --- architecture -------------------------------------------------------

    def crenels(self, x, y, z, w, d, size=0.16, h=0.15, mat="stone_brick", tint=None, sides="frkl"):
        """Merlons around the top edge of a w x d rectangle."""
        t = size * 0.75

        def run(length):
            cnt = max(2, int(round(length / (size * 2))) + 1)
            return [-length / 2 + size / 2 + i * (length - size) / (cnt - 1) for i in range(cnt)]

        for key, length, fx, fy in (("f", w, 0, -1), ("k", w, 0, 1), ("r", d, 1, 0), ("l", d, -1, 0)):
            if key not in sides:
                continue
            for p in run(length):
                if fx == 0:
                    self.box(x + p, y + fy * (d / 2 - t / 2), z, size, t, h, mat, tint)
                elif abs(abs(p) - (length - size) / 2) > 1e-6 or not ("f" in sides or "k" in sides):
                    self.box(x + fx * (w / 2 - t / 2), y + p, z, t, size, h, mat, tint)

    def crenel_ring(self, x, y, z, r, count=8, size=0.14, h=0.14, mat="stone_brick", tint=None, phase=0.0):
        for i in range(count):
            a = phase + i * 2 * math.pi / count
            self.box(x + math.cos(a) * r, y + math.sin(a) * r, z, size * 0.75, size, h, mat, tint, rot=a)

    def round_tower(self, x, y, z, r, h, mat="stone_brick", tint=None, n=8, top="cone", roof_tint=None,
                    roof_h=None, slits=1, finial=None, phase=None, collar_tint=None):
        """Round tower with a corbelled collar and a cone roof or battlements."""
        phase = math.pi / n if phase is None else phase
        self.cyl(x, y, z, r, h - 0.22, n, mat, tint, r2=r * 0.92, caps="", phase=phase)
        self.cyl(x, y, z + h - 0.22, r * 0.92, 0.08, n, mat, collar_tint or tint, r2=r * 1.14, caps="", phase=phase)
        self.cyl(x, y, z + h - 0.14, r * 1.14, 0.14, n, mat, collar_tint or tint, caps="t", phase=phase,
                 cap_mat="cobble")
        if top == "cone":
            self.cone_roof(x, y, z + h, r * 1.32, roof_h or r * 2.2, n, roof_tint, phase=phase, finial=finial)
        else:
            self.crenel_ring(x, y, z + h, r * 1.14 - 0.05, max(6, n), 0.13, 0.13, mat, tint, phase=phase)
        for i in range(slits):
            zz = z + h * (0.45 + 0.28 * i)
            for face in ("f", "r"):
                with self.face(face, (x, y, zz)):
                    self.quad((-0.07, -r * 0.97, 0), (0.07, -r * 0.97, 0), (0.07, -r * 0.95, 0.2),
                              (-0.07, -r * 0.95, 0.2), "slit", tint)

    def disc(self, x, y, z, r, face="f", decal="shield", n=10, off=0.02):
        """Vertical decal disc on a wall face, centred at (x, y, z)."""
        with self.face(face, (x, y, z)):
            ring = [(math.cos(i * 2 * math.pi / n), math.sin(i * 2 * math.pi / n)) for i in range(n)]
            self.poly([(c * r, -off, s * r) for c, s in ring], decal, uv=[(0.5 + 0.5 * c, 0.5 + 0.5 * s) for c, s in ring],
                      out=(0, -1, 0))

    def window(self, x, y, z, w=0.2, h=0.22, face="f", kind="window_wood", sill="timber", sill_tint=None):
        with self.face(face, (x, y, z)):
            self.quad((-w / 2, -0.012, 0), (w / 2, -0.012, 0), (w / 2, -0.012, h), (-w / 2, -0.012, h), kind)
            if sill:
                self.box(0, -0.03, -0.03, w + 0.05, 0.06, 0.035, sill, sill_tint)

    def door(self, x, y, z, w=0.3, h=0.42, face="f", kind="door_plank", step="cobble", step_tint=None):
        with self.face(face, (x, y, z)):
            self.quad((-w / 2, -0.014, 0), (w / 2, -0.014, 0), (w / 2, -0.014, h), (-w / 2, -0.014, h), kind)
            if step:
                self.box(0, -0.07, 0, w + 0.1, 0.14, 0.03, step, step_tint)

    def timber_frame(self, x, y, z, w, d, h, t=0.06, tint=None, mid=True, braces="fr"):
        """Half-timbering on a w x d x h wall box standing at (x, y, z)."""
        e = 0.012
        hx, hy = w / 2 + e, d / 2 + e
        for sx in (-1, 1):
            for sy in (-1, 1):
                self.box(x + sx * (hx - t / 2), y + sy * (hy - t / 2), z, t, t, h, "timber", tint)
        levels = [z, z + h - t] + ([z + h * 0.5 - t / 2] if mid else [])
        for zz in levels:
            for sy in (-1, 1):
                self.box(x, y + sy * (hy - t / 4), zz, w, t / 2, t, "timber", tint, skip="b")
            for sx in (-1, 1):
                self.box(x + sx * (hx - t / 4), y, zz, t / 2, d, t, "timber", tint, skip="b")
        top = z + (h * 0.5 if mid else h)
        if "f" in braces:
            for sx in (-1, 1):
                self.beam((x + sx * (hx - t), y - hy + t / 4, z + t), (x + sx * (hx - t - (top - z) * 0.5), y - hy + t / 4, top - t / 2),
                          t * 0.8, t / 2, "timber", tint, up=(0, 1, 0))
        if "r" in braces:
            for sy in (-1, 1):
                self.beam((x + hx - t / 4, y + sy * (hy - t), z + t), (x + hx - t / 4, y + sy * (hy - t - (top - z) * 0.5), top - t / 2),
                          t * 0.8, t / 2, "timber", tint, up=(1, 0, 0))

    def chimney(self, x, y, z, h=0.5, s=0.16, mat="stone_brick", tint=None):
        self.box(x, y, z, s, s, h, mat, tint, taper=0.9)
        self.box(x, y, z + h, s * 1.15, s * 1.15, 0.05, mat, tint, top="flat", top_tint="#3a332d")

    def stairs(self, x, y, z, w, depth, h, steps=3, face="f", mat="stone_brick", tint=None):
        """Steps climbing towards the wall at local y = 0; they extend `depth` outwards."""
        with self.face(face, (x, y, z)):
            for i in range(steps):
                dd = depth * (steps - i) / steps
                self.box(0, -dd / 2, h * i / steps, w, dd, h / steps, mat, tint, skip="bk")

    def column(self, x, y, z, h, r=0.07, mat="marble", tint=None, n=8):
        self.box(x, y, z, r * 2.8, r * 2.8, 0.05, mat, tint)
        self.cyl(x, y, z + 0.05, r, h - 0.11, n, mat, tint, r2=r * 0.88, caps="")
        self.box(x, y, z + h - 0.06, r * 2.8, r * 2.8, 0.06, mat, tint)

    def pad(self, fp, mat="cobble", tint=None, h=0.05, margin=0.07, side=None, side_tint=None):
        """Ground slab filling the footprint."""
        s = fp - 2 * margin
        self.box(0, 0, 0, s, s, h, side or mat, side_tint if side else tint, taper=1 - 0.03 / s, skip="bt")
        k = s / 2 - 0.015
        self.poly([(-k, -k, h), (k, -k, h), (k, k, h), (-k, k, h)], mat, tint)

    # --- props ---------------------------------------------------------------

    def crate(self, x, y, z, s=0.2, rot=0.0, tint=None):
        with self.push((x, y, z), rot):
            h = s / 2
            for a in (0, 1, 2, 3):
                with self.push(rot=a * math.pi / 2):
                    self.quad((-h, -h, 0), (h, -h, 0), (h, -h, s), (-h, -h, s), "crate", tint)
            self.quad((-h, -h, s), (h, -h, s), (h, h, s), (-h, h, s), "crate", tint)

    def barrel(self, x, y, z, r=0.09, h=0.24, tint=None, n=8):
        for z0, z1, ra, rb, v0, v1 in ((0, h / 2, r * 0.82, r, 0.0, 0.5), (h / 2, h, r, r * 0.82, 0.5, 1.0)):
            for i in range(n):
                a0, a1 = i * 2 * math.pi / n, (i + 1) * 2 * math.pi / n
                self.poly([(x + math.cos(a0) * ra, y + math.sin(a0) * ra, z + z0),
                           (x + math.cos(a1) * ra, y + math.sin(a1) * ra, z + z0),
                           (x + math.cos(a1) * rb, y + math.sin(a1) * rb, z + z1),
                           (x + math.cos(a0) * rb, y + math.sin(a0) * rb, z + z1)], "barrel", tint,
                          uv=[(i / n, v0), ((i + 1) / n, v0), ((i + 1) / n, v1), (i / n, v1)],
                          normals=[(math.cos(a0), math.sin(a0), 0), (math.cos(a1), math.sin(a1), 0)] * 1
                          + [(math.cos(a1), math.sin(a1), 0), (math.cos(a0), math.sin(a0), 0)])
        self.poly([(x + math.cos(i * 2 * math.pi / n) * r * 0.82, y + math.sin(i * 2 * math.pi / n) * r * 0.82, z + h)
                   for i in range(n)], "log_end", mix(tint, "#b98a55", 0.6),
                  uv=[(0.5 + 0.5 * math.cos(i * 2 * math.pi / n), 0.5 + 0.5 * math.sin(i * 2 * math.pi / n))
                      for i in range(n)])

    def sack(self, x, y, z, s=0.1, seed=0, tint="#c9a877"):
        self.blob(x, y, z + s * 0.55, s, s * 0.85, s * 0.8, "fabric", mix(tint, "#000000", 0.35), tint, n=6, rings=3,
                  seed=seed, jitter=0.1, bottom=-0.7)

    def log(self, p0, p1, r=0.08, n=7, tint="#8a623c"):
        """Horizontal log between two points with ring-patterned ends."""
        p0, p1 = Vector(p0), Vector(p1)
        axis = p1 - p0
        ln = axis.length
        a = axis / ln
        side = a.cross(Vector((0, 0, 1))).normalized()
        up = side.cross(a)
        period = L.TILES["timber"][3]
        ring = [(math.cos(i * 2 * math.pi / n), math.sin(i * 2 * math.pi / n)) for i in range(n + 1)]
        for i in range(n):
            (c0, s0), (c1, s1) = ring[i], ring[i + 1]
            n0, n1 = side * c0 + up * s0, side * c1 + up * s1
            arc = 2 * math.pi * r / n / period
            self.poly([p0 + n0 * r, p1 + n0 * r, p1 + n1 * r, p0 + n1 * r], "timber", tint,
                      uv=[(0, i * arc), (ln / period, i * arc), (ln / period, (i + 1) * arc), (0, (i + 1) * arc)],
                      normals=[n0, n0, n1, n1], out=(n0 + n1))
        for p, d in ((p0, -a), (p1, a)):
            self.poly([p + (side * c + up * s) * r for c, s in ring[:-1]], "log_end",
                      uv=[(0.5 + 0.5 * c, 0.5 + 0.5 * s) for c, s in ring[:-1]], out=d)

    def log_pile(self, x, y, z, length=0.7, r=0.07, rows=(3, 2, 1), rot=0.0, tint="#8a623c"):
        with self.push((x, y, z), rot):
            for j, count in enumerate(rows):
                for i in range(count):
                    off = (i - (count - 1) / 2) * r * 2.05
                    self.log((-length / 2, off, r + j * r * 1.75), (length / 2, off, r + j * r * 1.75), r, tint=tint)

    def hay_bale(self, x, y, z, r=0.14, length=0.22, rot=0.0):
        with self.push((x, y, z), rot):
            n = 8
            ring = [(math.cos(i * 2 * math.pi / n), math.sin(i * 2 * math.pi / n)) for i in range(n + 1)]
            period = L.TILES["hay"][3]
            for i in range(n):
                (c0, s0), (c1, s1) = ring[i], ring[i + 1]
                arc = 2 * math.pi * r / n / period
                self.poly([(-length / 2, c0 * r, r + s0 * r), (length / 2, c0 * r, r + s0 * r),
                           (length / 2, c1 * r, r + s1 * r), (-length / 2, c1 * r, r + s1 * r)], "hay",
                          uv=[(i * arc, 0), (i * arc, length / period), ((i + 1) * arc, length / period),
                              ((i + 1) * arc, 0)],
                          normals=[(0, c0, s0), (0, c0, s0), (0, c1, s1), (0, c1, s1)], out=(0, c0 + c1, s0 + s1))
            for sx in (-1, 1):
                self.poly([(sx * length / 2, c * r, r + s * r) for c, s in ring[:-1]], "hay_end",
                          uv=[(0.5 + 0.5 * c, 0.5 + 0.5 * s) for c, s in ring[:-1]], out=(sx, 0, 0))

    def fence(self, x0, y0, x1, y1, z=0.0, h=0.26, post=0.045, rails=2, mat="timber", tint=None, gap=0.42):
        a, b = Vector((x0, y0, z)), Vector((x1, y1, z))
        ln = (b - a).length
        cnt = max(1, int(round(ln / gap)))
        for i in range(cnt + 1):
            p = a.lerp(b, i / cnt)
            self.box(p.x, p.y, p.z, post, post, h, mat, tint, taper=0.8)
        for r in range(rails):
            zz = h * (0.45 + 0.4 * r) if rails > 1 else h * 0.7
            self.beam(a + Vector((0, 0, zz)), b + Vector((0, 0, zz)), post * 0.6, post * 0.9, mat, tint, ends=False)

    def wheel(self, x, y, z, r=0.13, face="f", t=0.04):
        """Cart wheel standing on z, axle along the face normal."""
        with self.face(face, (x, y, z)):
            n = 10
            ring = [(math.cos(i * 2 * math.pi / n), math.sin(i * 2 * math.pi / n)) for i in range(n + 1)]
            for i in range(n):
                (c0, s0), (c1, s1) = ring[i], ring[i + 1]
                self.poly([(c0 * r, -t / 2, r + s0 * r), (c0 * r, t / 2, r + s0 * r), (c1 * r, t / 2, r + s1 * r),
                           (c1 * r, -t / 2, r + s1 * r)], "flat", "#4a3524", out=(c0 + c1, 0, s0 + s1))
            for sy in (-1, 1):
                self.poly([(c * r, sy * t / 2, r + s * r) for c, s in ring[:-1]], "wheel",
                          uv=[(0.5 + 0.5 * c, 0.5 + 0.5 * s) for c, s in ring[:-1]], out=(0, sy, 0))

    def cart(self, x, y, z, rot=0.0, load=None):
        with self.push((x, y, z), rot):
            self.box(0, 0, 0.13, 0.5, 0.3, 0.035, "wood_planks", skip="")
            for sy in (-1, 1):
                self.box(0, sy * 0.14, 0.165, 0.5, 0.025, 0.09, "wood_planks")
                self.wheel(-0.05, sy * 0.18, 0.0, 0.13)
            self.box(-0.24, 0, 0.165, 0.025, 0.28, 0.09, "wood_planks")
            for sy in (-1, 1):
                self.beam((0.25, sy * 0.1, 0.15), (0.55, sy * 0.1, 0.06), 0.025, mat="timber")
            if load == "hay":
                self.blob(0, 0, 0.24, 0.22, 0.14, 0.14, "hay", "#b89a4a", "#ffffff", n=6, rings=3, seed=3, bottom=-0.3)
            elif load == "stone":
                for i, (px, py) in enumerate(((-0.1, 0.03), (0.08, -0.04), (0.0, 0.06))):
                    self.rock(px, py, 0.17, 0.09, seed=i + 5)
            elif load == "logs":
                self.log_pile(0, 0, 0.165, 0.46, 0.045, (3, 2))

    def rock(self, x, y, z, r=0.2, seed=0, tint="#b0a89c", flat=0.7):
        rnd = random.Random(seed)
        self.blob(x, y, z + r * flat * 0.35, r * (0.85 + rnd.random() * 0.3), r * (0.85 + rnd.random() * 0.3),
                  r * flat, "rock", mix(tint, "#3d3a40", 0.45), tint, n=6, rings=3, seed=seed, jitter=0.22,
                  bottom=-0.5)

    def flag(self, x, y, z, h=0.6, tint="#c23a2e", size=0.26, finial=True, wave=0.03):
        """Pole with a pennant flying towards +x."""
        self.cyl(x, y, z, 0.016, h, 5, "flat", "#6b4a2e", caps="")
        if finial:
            self.finial(x, y, z + h - 0.02, 0.045)
        top = z + h - 0.03
        segs = 3
        dark = mix(tint, "#000000", 0.25)
        for i in range(segs):
            t0, t1 = i / segs, (i + 1) / segs
            y0 = y + math.sin(t0 * math.pi * 1.5) * wave
            y1 = y + math.sin(t1 * math.pi * 1.5) * wave
            h0, h1 = size * 0.62 * (1 - t0 * 0.75), size * 0.62 * (1 - t1 * 0.75)
            pts = [(x + 0.016 + t0 * size, y0, top - h0), (x + 0.016 + t1 * size, y1, top - h1 - (h0 - h1) * 0.0),
                   (x + 0.016 + t1 * size, y1, top - (h0 - h1) * 0.5), (x + 0.016 + t0 * size, y0, top)]
            cols = [dark, dark, tint, tint]
            self.poly(pts, "fabric", cols)
            self.poly(list(reversed(pts)), "fabric", list(reversed(cols)))

    def banner(self, x, y, z, w=0.22, h=0.44, face="f", kind="banner_red", pole=True):
        """Banner hanging flat against a wall face (top edge at z + h)."""
        with self.face(face, (x, y, z)):
            e = -0.03
            tip = h * 0.14
            self.poly([(-w / 2, e, tip), (0, e, 0), (w / 2, e, tip), (w / 2, e, h), (-w / 2, e, h)], kind,
                      uv=[(0, tip / h), (0.5, 0), (1, tip / h), (1, 1), (0, 1)])
            if pole:
                self.beam((-w / 2 - 0.03, e, h), (w / 2 + 0.03, e, h), 0.025, mat="gold")

    def standard(self, x, y, z, h=0.9, kind="banner_red", rot=0.0, w=0.2):
        """Free-standing banner on a pole with a crossbar; readable from both sides."""
        with self.push((x, y, z), rot):
            self.cyl(0, 0, 0, 0.02, h, 5, "flat", "#6b4a2e", caps="")
            self.finial(0, 0, h - 0.02, 0.05)
            self.beam((-w / 2 - 0.03, 0, h - 0.06), (w / 2 + 0.03, 0, h - 0.06), 0.022, mat="gold")
            bh = w * 2.0
            top = h - 0.07
            tip = bh * 0.14
            for sy in (-1, 1):
                self.poly([(-w / 2, sy * 0.022, top - bh + tip), (0, sy * 0.022, top - bh),
                           (w / 2, sy * 0.022, top - bh + tip), (w / 2, sy * 0.022, top), (-w / 2, sy * 0.022, top)],
                          kind, uv=[(0, tip / bh), (0.5, 0), (1, tip / bh), (1, 1), (0, 1)], out=(0, sy, 0))

    def tree(self, x, y, z, s=1.0, kind="round", seed=0, lo=None, hi=None, n=7):
        rnd = random.Random(seed)
        with self.push((x, y, z), rnd.random() * 6.28, s):
            if kind == "pine":
                lo, hi = lo or "#2f5f3a", hi or "#5f9a4a"
                self.cyl(0, 0, 0, 0.07, 0.4, 5, "timber", "#8a6a4a", r2=0.05, caps="")
                for i, (rr, zz, hh) in enumerate(((0.42, 0.28, 0.55), (0.33, 0.62, 0.5), (0.22, 0.95, 0.5))):
                    self.cyl(0, 0, zz, rr, hh, n, "foliage", mix(lo, hi, i * 0.3), r2=0.0, caps="", smooth=False,
                             tint_top=mix(lo, hi, 0.5 + i * 0.25), phase=i * 0.4)
            else:
                lo, hi = lo or "#3f7a34", hi or "#9acb55"
                th = 0.45 + rnd.random() * 0.15
                self.cyl(0, 0, 0, 0.085, th + 0.2, 5, "timber", "#9a7550", r2=0.05, caps="")
                self.blob(0, 0, th + 0.42, 0.5, 0.5, 0.44, "foliage", lo, hi, n=n, rings=4, seed=seed)
                if kind == "round":
                    a = rnd.random() * 6.28
                    self.blob(math.cos(a) * 0.3, math.sin(a) * 0.3, th + 0.22, 0.33, 0.33, 0.28, "foliage", lo,
                              mix(lo, hi, 0.8), n=max(5, n - 1), rings=3, seed=seed + 1)
                    self.blob(-math.cos(a) * 0.22, -math.sin(a) * 0.22, th + 0.72, 0.3, 0.3, 0.26, "foliage",
                              mix(lo, hi, 0.3), hi, n=max(5, n - 1), rings=3, seed=seed + 2)

    def bush(self, x, y, z, s=0.2, seed=0, lo="#3f7a34", hi="#9acb55"):
        self.blob(x, y, z + s * 0.4, s, s, s * 0.75, "foliage", lo, hi, n=6, rings=3, seed=seed, bottom=-0.5)

    # --- output ---------------------------------------------------------------

    def bake_ao(self, strength=0.6, reach=0.7, ground=True):
        verts, faces = [], []
        for poly in self.polys:
            base = len(verts)
            verts.extend(it[0] for it in poly)
            faces.append(list(range(base, base + len(poly))))
        if ground:
            base = len(verts)
            verts.extend(Vector(p) for p in ((-50, -50, -0.001), (50, -50, -0.001), (50, 50, -0.001), (-50, 50, -0.001)))
            faces.append([base, base + 1, base + 2, base + 3])
        tree = BVHTree.FromPolygons(verts, faces)
        rnd = random.Random(7)
        dirs = []
        while len(dirs) < 14:
            v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.15, 1)))
            if 0.1 < v.length <= 1:
                dirs.append(v.normalized())
        cache = {}
        for poly in self.polys:
            fn = _normal([it[0] for it in poly])
            t = fn.orthogonal().normalized()
            b = fn.cross(t)
            centre = sum((it[0] for it in poly), Vector()) / len(poly)
            for i, (p, uv, col, nn) in enumerate(poly):
                key = (round(p.x, 3), round(p.y, 3), round(p.z, 3), round(fn.x, 2), round(fn.y, 2), round(fn.z, 2))
                ao = cache.get(key)
                if ao is None:
                    origin = p + (centre - p) * 0.04 + fn * 0.015
                    occ = 0.0
                    for d in dirs:
                        hit = tree.ray_cast(origin, t * d.x + b * d.y + fn * d.z, reach)
                        if hit[0] is not None:
                            occ += 1.0 - hit[3] / reach
                    ao = 1.0 - strength * min(1.0, occ / len(dirs) * 1.6)
                    cache[key] = ao
                # shadows drift slightly cool, like skylight filling them
                poly[i] = (p, uv, (col[0] * ao ** 1.15, col[1] * ao, col[2] * ao ** 0.85), nn)

    def to_object(self, name, ao=True, ground=True):
        if ao:
            self.bake_ao(ground=ground)
        verts, faces, uvs, cols, nrms = [], [], [], [], []
        for poly in self.polys:
            base = len(verts)
            for p, uv, col, nn in poly:
                verts.append(p)
                uvs.append(uv)
                cols.append(col)
                nrms.append(nn)
            faces.append(list(range(base, base + len(poly))))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        uv_layer = mesh.uv_layers.new(name="UVMap")
        col_layer = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="CORNER")
        # vertices are never shared between faces, so loop i is vertex i;
        # foreach_set is orders of magnitude faster than per-loop access
        mesh.polygons.foreach_set("use_smooth", [True] * len(faces))
        uv_layer.data.foreach_set("uv", [c for uv in uvs for c in uv])
        col_layer.data.foreach_set("color", [c for col in cols for c in (col[0], col[1], col[2], 1.0)])
        mesh.color_attributes.active_color = col_layer
        mesh.color_attributes.render_color_index = 0
        mesh.normals_split_custom_set_from_vertices([tuple(n) for n in nrms])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def export_glb(path, objects):
    """Export objects to a material-less .glb (UVs + vertex colours + normals)."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="NONE",
        export_vertex_color="ACTIVE",
        export_active_vertex_color_when_no_material=True,
        export_all_vertex_colors=False,
        export_normals=True,
        export_animations=False,
    )


def script_args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
