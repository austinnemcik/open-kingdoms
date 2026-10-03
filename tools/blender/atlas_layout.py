"""Layout of the shared texture atlas (client/assets/textures/atlas.png).

Pure Python, no dependencies: imported both by gen_textures.py (system Python,
paints the atlas) and by okkit.py (Blender, maps UVs onto it).

Two kinds of cell:

* TILES: seamlessly tiling materials. A cell holds two periods of the tile in
  each direction plus a gutter of wrapped texels all round, so a face up to two
  periods long can sit anywhere without sampling a neighbouring cell, even at
  low mip levels. Longer faces are split by the kit.
* DECALS: one-off painted details (windows, doors, banners...) mapped 0..1.
"""

SIZE = 2048
BIG = 512
SMALL = 256

# name: (x_px, y_px, cell_px, world units covered by one period)
TILES = {
    "stone_brick": (0, 0, BIG, 0.85),
    "stone_block": (512, 0, BIG, 1.0),
    "plaster": (1024, 0, BIG, 1.5),
    "wood_planks": (1536, 0, BIG, 0.9),
    "timber": (0, 512, BIG, 1.0),
    "roof_tiles": (512, 512, BIG, 0.8),
    "thatch": (1024, 512, BIG, 0.8),
    "cobble": (1536, 512, BIG, 1.2),
    "dirt": (0, 1024, BIG, 2.0),
    "rock": (512, 1024, BIG, 2.0),
    "foliage": (1024, 1024, BIG, 1.2),
    "marble": (1536, 1024, BIG, 1.2),
    "flat": (0, 1536, SMALL, 1.0),
    "gold": (256, 1536, SMALL, 0.6),
    "hay": (512, 1536, SMALL, 0.6),
    "wheat": (768, 1536, SMALL, 0.8),
    "fabric": (1024, 1536, SMALL, 0.8),
}

# name: (x_px, y_px, width_px, height_px)
DECALS = {
    "window_wood": (1280, 1536, 256, 256),
    "window_arch": (1536, 1536, 256, 256),
    "door_plank": (1792, 1536, 256, 256),
    "door_double": (0, 1792, 256, 256),
    "crate": (256, 1792, 256, 256),
    "barrel": (512, 1792, 256, 256),
    "target": (768, 1792, 256, 256),
    "wheel": (1024, 1792, 256, 256),
    "shield": (1280, 1792, 256, 256),
    "banner_red": (1536, 1792, 128, 256),
    "banner_blue": (1664, 1792, 128, 256),
    "log_end": (1792, 1792, 128, 128),
    "hay_end": (1920, 1792, 128, 128),
    "slit": (1792, 1920, 128, 128),
    "sign_heal": (1920, 1920, 128, 128),
}

DECAL_INSET = 3


def gutter(cell):
    return cell // 8


def period_px(cell):
    return (cell - 2 * gutter(cell)) // 2


def tile_uv(name, u, v):
    """Atlas UV (Blender convention, v up) for tile-space (u, v) in [0, 2]."""
    x, y, cell, _ = TILES[name]
    g, p = gutter(cell), period_px(cell)
    return ((x + g + u * p) / SIZE, 1.0 - (y + cell - g - v * p) / SIZE)


def decal_uv(name, u, v):
    """Atlas UV for decal-space (u, v) in [0, 1], v up."""
    x, y, w, h = DECALS[name]
    i = DECAL_INSET
    return ((x + i + u * (w - 2 * i)) / SIZE, 1.0 - (y + h - i - v * (h - 2 * i)) / SIZE)
