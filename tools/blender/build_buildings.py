"""Generate low-poly building models procedurally and export them as .glb.

Run headless (no Blender UI needed):
    blender -b --factory-startup -P tools/blender/build_buildings.py -- client/assets/models [kind ...]

Every model is built around the origin with its base at z=0, sized so that
one Blender unit = one city tile. The footprint must match data/buildings.yaml.
To add a building: write a `build_<kind>(fp)` function and register it in
BUILDERS. Keep models stylised and low-poly (a few hundred tris).
"""

import math
import os
import sys

import bmesh
import bpy

PALETTE = {
    "stone": (0.62, 0.60, 0.56),
    "stone_dark": (0.40, 0.39, 0.37),
    "plaster": (0.90, 0.85, 0.74),
    "wood": (0.48, 0.32, 0.18),
    "wood_dark": (0.30, 0.20, 0.12),
    "roof_red": (0.66, 0.20, 0.14),
    "roof_blue": (0.20, 0.32, 0.58),
    "roof_slate": (0.28, 0.30, 0.34),
    "thatch": (0.78, 0.64, 0.32),
    "crop": (0.80, 0.72, 0.25),
    "crop_green": (0.42, 0.62, 0.22),
    "soil": (0.42, 0.30, 0.20),
    "gold": (0.95, 0.75, 0.20),
    "banner": (0.75, 0.12, 0.12),
    "white": (0.95, 0.95, 0.95),
    "straw": (0.88, 0.80, 0.50),
}

_materials = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def material(name):
    """PALETTE colours are sRGB (as picked in an image editor); glTF wants linear."""
    if name not in _materials:
        mat = bpy.data.materials.new(name)
        rgba = (*(srgb_to_linear(c) for c in PALETTE[name]), 1.0)
        mat.diffuse_color = rgba
        if mat.node_tree is None:
            mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = 0.85
        _materials[name] = mat
    return _materials[name]


def _finish(obj, mat, loc=(0, 0, 0), rot=(0, 0, 0)):
    obj.location = loc
    obj.rotation_euler = rot
    obj.data.materials.append(material(mat))
    return obj


def box(size, loc, mat, rot=(0, 0, 0)):
    """Axis-aligned box; `loc` is the centre of its bottom face."""
    sx, sy, sz = size
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    return _finish(obj, mat, (loc[0], loc[1], loc[2] + sz / 2), rot)


def cylinder(radius, depth, loc, mat, vertices=10, rot=(0, 0, 0)):
    """Cylinder standing on `loc` (bottom centre) unless rotated."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth)
    obj = bpy.context.active_object
    z_off = depth / 2 if rot == (0, 0, 0) else 0
    return _finish(obj, mat, (loc[0], loc[1], loc[2] + z_off), rot)


def cone(radius, depth, loc, mat, vertices=8, rot_z=0.0):
    """Cone or pyramid (vertices=4) with its base at `loc`."""
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=0, depth=depth)
    obj = bpy.context.active_object
    return _finish(obj, mat, (loc[0], loc[1], loc[2] + depth / 2), (0, 0, rot_z))


def pyramid(width, depth, loc, mat):
    """Square pyramid roof whose base edges align with the axes."""
    return cone(width / math.sqrt(2), depth, loc, mat, vertices=4, rot_z=math.pi / 4)


def gable_roof(width, length, height, loc, mat, along_x=False):
    """Triangular prism roof; ridge runs along Y (or X if along_x)."""
    mesh = bpy.data.meshes.new("roof")
    bm = bmesh.new()
    w, l = width / 2, length / 2
    if along_x:
        pts = [(-l, -w, 0), (-l, w, 0), (-l, 0, height), (l, -w, 0), (l, w, 0), (l, 0, height)]
    else:
        pts = [(-w, -l, 0), (w, -l, 0), (0, -l, height), (-w, l, 0), (w, l, 0), (0, l, height)]
    v = [bm.verts.new(p) for p in pts]
    for face in ([0, 1, 2], [5, 4, 3], [0, 3, 4, 1], [1, 4, 5, 2], [2, 5, 3, 0]):
        bm.faces.new([v[i] for i in face])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("roof", mesh)
    bpy.context.collection.objects.link(obj)
    return _finish(obj, mat, loc)


def rock(radius, loc, mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius)
    obj = bpy.context.active_object
    obj.scale = (1.0, 0.85, 0.6)
    return _finish(obj, mat, (loc[0], loc[1], loc[2] + radius * 0.4))


def plinth(fp, mat="stone_dark"):
    box((fp * 0.96, fp * 0.96, 0.08), (0, 0, 0), mat)


def house(w, d, h, loc, wall="plaster", roof="roof_red", roof_h=None, along_x=False):
    x, y, z = loc
    box((w, d, h), (x, y, z), wall)
    rw, rl = (d, w) if along_x else (w, d)
    gable_roof(rw + 0.1, rl + 0.1, roof_h or h * 0.6, (x, y, z + h), roof, along_x)


def flag(loc, height=1.2, color="banner"):
    x, y, z = loc
    cylinder(0.025, height, (x, y, z), "wood_dark", vertices=6)
    box((0.02, 0.35, 0.22), (x, y + 0.18, z + height - 0.25), color)


# --- Buildings ---------------------------------------------------------------


def build_city_hall(fp):
    plinth(fp, "stone")
    box((2.6, 2.6, 1.4), (0, 0, 0.08), "plaster")
    pyramid(2.9, 1.3, (0, 0, 1.48), "roof_blue")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = (sx * 1.45, sy * 1.45, 0.08)
            cylinder(0.32, 2.0, p, "stone", vertices=8)
            cone(0.42, 0.8, (p[0], p[1], 2.08), "roof_blue", vertices=8)
    box((0.7, 0.1, 0.9), (0, -1.32, 0.08), "wood_dark")
    flag((0, 0, 2.7), 1.0)


def build_farm(fp):
    plinth(fp, "soil")
    for i, crop in enumerate(("crop", "crop_green", "crop")):
        box((0.3, 1.7, 0.12), (-0.75 + i * 0.4, 0, 0.08), crop)
    house(0.6, 0.8, 0.5, (0.55, 0.3, 0.08), wall="wood", roof="thatch")
    cylinder(0.18, 0.35, (0.55, -0.55, 0.08), "straw", vertices=8)


def build_lumber_mill(fp):
    plinth(fp)
    house(1.0, 0.8, 0.6, (-0.3, 0.3, 0.08), wall="wood", roof="roof_slate")
    for i in range(3):
        cylinder(0.12, 0.9, (0.45, -0.25 - i * 0.0, 0.2 + i * 0.22), "wood", vertices=8,
                 rot=(0, math.pi / 2, 0))
    cylinder(0.1, 0.25, (-0.6, -0.55, 0.08), "wood_dark", vertices=8)


def build_quarry(fp):
    plinth(fp, "stone_dark")
    rock(0.5, (-0.35, 0.3, 0.08), "stone")
    rock(0.35, (0.35, 0.45, 0.08), "stone")
    rock(0.3, (0.1, -0.1, 0.08), "stone_dark")
    house(0.6, 0.5, 0.4, (0.45, -0.5, 0.08), wall="wood", roof="roof_slate", along_x=True)


def build_goldmine(fp):
    plinth(fp, "stone_dark")
    rock(0.7, (0, 0.3, 0.08), "stone_dark")
    box((0.5, 0.2, 0.55), (0, -0.25, 0.08), "wood_dark")
    rock(0.15, (-0.5, -0.5, 0.08), "gold")
    rock(0.12, (0.5, -0.45, 0.08), "gold")


def build_storehouse(fp):
    plinth(fp)
    house(1.6, 1.2, 0.8, (0, 0, 0.08), wall="wood", roof="roof_red", along_x=True)
    for i in range(3):
        cylinder(0.12, 0.28, (-0.6 + i * 0.3, -0.8, 0.08), "wood", vertices=8)


def build_barracks(fp):
    plinth(fp)
    house(2.4, 1.2, 0.8, (0, 0.5, 0.08), wall="stone", roof="roof_red", along_x=True)
    for x in (-1.2, 1.2):
        box((0.06, 1.2, 0.3), (x, -0.85, 0.08), "wood")
    box((2.4, 0.06, 0.3), (0, -1.42, 0.08), "wood")
    flag((1.0, -1.0, 0.08))


def build_archery_range(fp):
    plinth(fp)
    house(1.4, 1.0, 0.7, (-0.6, 0.7, 0.08), wall="wood", roof="roof_red", along_x=True)
    for x in (-0.6, 0.2, 1.0):
        cylinder(0.3, 0.06, (x, -0.9, 0.5), "straw", vertices=12, rot=(math.pi / 2, 0, 0))
        cylinder(0.12, 0.07, (x, -0.92, 0.5), "banner", vertices=12, rot=(math.pi / 2, 0, 0))


def build_stable(fp):
    plinth(fp, "soil")
    house(2.4, 1.0, 0.65, (0, 0.6, 0.08), wall="wood", roof="thatch", along_x=True)
    for x in (-1.3, 1.3):
        box((0.06, 1.4, 0.35), (x, -0.6, 0.08), "wood_dark")
    cylinder(0.25, 0.4, (0.5, -0.6, 0.08), "straw", vertices=8)


def build_siege_workshop(fp):
    plinth(fp)
    house(1.8, 1.4, 0.9, (-0.4, 0.5, 0.08), wall="stone", roof="roof_slate")
    box((0.7, 0.5, 0.2), (0.8, -0.8, 0.12), "wood")
    for x in (0.55, 1.05):
        cylinder(0.14, 0.06, (x, -1.08, 0.14), "wood_dark", vertices=10, rot=(math.pi / 2, 0, 0))
    box((0.08, 0.08, 1.0), (0.8, -0.8, 0.3), "wood", rot=(0.5, 0, 0))


def build_hospital(fp):
    plinth(fp)
    house(1.5, 1.2, 0.8, (0, 0, 0.08), wall="white", roof="roof_red")
    box((0.5, 0.06, 0.14), (0, -0.62, 0.45), "banner")
    box((0.14, 0.06, 0.5), (0, -0.62, 0.27), "banner")


def build_academy(fp):
    plinth(fp, "stone")
    box((2.0, 2.0, 1.0), (0, 0, 0.08), "plaster")
    for i in range(4):
        x = -0.75 + i * 0.5
        cylinder(0.1, 1.0, (x, -1.1, 0.08), "white", vertices=8)
    box((2.2, 0.4, 0.1), (0, -1.0, 1.08), "stone")
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.8)
    dome = bpy.context.active_object
    dome.scale = (1, 1, 0.7)
    _finish(dome, "roof_blue", (0, 0.1, 1.08))


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


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def export(kind, out_dir):
    build, fp = BUILDERS[kind]
    clear_scene()
    build(fp)
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = kind
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    path = os.path.join(out_dir, f"{kind}.glb")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
    )
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    print(f"exported {path} ({tris} tris)")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        sys.exit("usage: blender -b -P build_buildings.py -- <out_dir> [kind ...]")
    out_dir = os.path.abspath(argv[0])
    kinds = argv[1:] or list(BUILDERS)
    os.makedirs(out_dir, exist_ok=True)
    unknown = [k for k in kinds if k not in BUILDERS]
    if unknown:
        sys.exit(f"unknown building kinds: {unknown}")
    for kind in kinds:
        export(kind, out_dir)


if __name__ == "__main__":
    main()
