class_name CityRoads
## Works out the purely visual city dressing from a list of buildings: which
## tiles are cobbled (two avenues from the gates, a plaza round the city hall
## and a path from every building's door to the nearest road) and where
## decorative props stand. Pure and deterministic, so it is unit-testable and
## the city looks the same on every client. Nothing here affects game state:
## roads and props never block building, they simply vanish under buildings.

## Tiles of road mask beyond the grid on each side (roads run out of the gates).
const MARGIN := 12
## Tiles the plaza extends beyond the city hall footprint.
const PLAZA_RING := 2
const CITY_HALL_KIND := "city_hall"
const NEIGHBOURS: Array[Vector2i] = [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]


## Every tile covered by a building footprint.
static func occupied_tiles(buildings: Array) -> Dictionary[Vector2i, bool]:
	var out: Dictionary[Vector2i, bool] = {}
	for b: Dictionary in buildings:
		for dy in int(b.footprint):
			for dx in int(b.footprint):
				out[Vector2i(int(b.x) + dx, int(b.y) + dy)] = true
	return out


## The tile in front of a building's door. Models face +y (south, towards
## the camera) with the door near the middle of that side.
static func door_tile(building: Dictionary) -> Vector2i:
	var fp := int(building.footprint)
	@warning_ignore("integer_division")
	return Vector2i(int(building.x) + (fp - 1) / 2, int(building.y) + fp)


static func in_city(tile: Vector2i, city_size: int) -> bool:
	return tile.x >= 0 and tile.y >= 0 and tile.x < city_size and tile.y < city_size


## The cobbled square: the city hall footprint (or the middle of the grid when
## there is no city hall) grown by PLAZA_RING tiles.
static func plaza_rect(buildings: Array, city_size: int) -> Rect2i:
	@warning_ignore("integer_division")
	var mid := city_size / 2
	var plaza := Rect2i(mid - 2, mid - 2, 4, 4)
	for b: Dictionary in buildings:
		if b.kind == CITY_HALL_KIND:
			plaza = Rect2i(int(b.x), int(b.y), int(b.footprint), int(b.footprint))
			break
	return plaza.grow(PLAZA_RING)


## All road tiles inside the grid (they may run under buildings, which hide them).
static func road_tiles(buildings: Array, city_size: int) -> Dictionary[Vector2i, bool]:
	var roads: Dictionary[Vector2i, bool] = {}
	@warning_ignore("integer_division")
	var mid := city_size / 2
	for i in city_size:
		for lane: int in [mid - 1, mid]:
			roads[Vector2i(i, lane)] = true
			roads[Vector2i(lane, i)] = true
	var plaza := plaza_rect(buildings, city_size)
	for y in range(plaza.position.y, plaza.end.y):
		for x in range(plaza.position.x, plaza.end.x):
			if in_city(Vector2i(x, y), city_size):
				roads[Vector2i(x, y)] = true
	var occupied := occupied_tiles(buildings)
	var ordered := buildings.duplicate()
	ordered.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.id) < int(b.id))
	for b: Dictionary in ordered:
		for tile in _path_to_road(door_tile(b), roads, occupied, city_size):
			roads[tile] = true
	return roads


## Shortest 4-connected path over free tiles from `start` to any road tile
## (exclusive of that road tile). Empty when `start` is blocked or cut off.
static func _path_to_road(start: Vector2i, roads: Dictionary[Vector2i, bool],
		occupied: Dictionary[Vector2i, bool], city_size: int) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	if not in_city(start, city_size) or occupied.has(start) or roads.has(start):
		return path
	var came_from: Dictionary[Vector2i, Vector2i] = {start: start}
	var queue: Array[Vector2i] = [start]
	var head := 0
	while head < queue.size():
		var tile := queue[head]
		head += 1
		for step in NEIGHBOURS:
			var next := tile + step
			if came_from.has(next) or not in_city(next, city_size) or occupied.has(next):
				continue
			came_from[next] = tile
			if roads.has(next):
				var back := tile
				while back != start:
					path.append(back)
					back = came_from[back]
				path.append(start)
				return path
			queue.append(next)
	return path


## Ground mask for ground.gdshader, one pixel per tile, covering the grid plus
## MARGIN tiles on every side. R = road, G = worn ground around buildings,
## B = inside the city.
static func build_mask(buildings: Array, city_size: int) -> Image:
	var side := city_size + 2 * MARGIN
	var image := Image.create_empty(side, side, false, Image.FORMAT_RGB8)
	var roads := road_tiles(buildings, city_size)
	var occupied := occupied_tiles(buildings)
	@warning_ignore("integer_division")
	var mid := city_size / 2
	for py in side:
		for px in side:
			var tile := Vector2i(px - MARGIN, py - MARGIN)
			var color := Color.BLACK
			if in_city(tile, city_size):
				color.b = 1.0
				color.r = 1.0 if roads.has(tile) else 0.0
				color.g = 1.0 if occupied.has(tile) else 0.0
			else:
				# the avenues leave through the gates and fade into dirt tracks
				var outside := maxi(maxi(-tile.x, tile.x - city_size + 1), maxi(-tile.y, tile.y - city_size + 1))
				var on_avenue := tile.x == mid - 1 or tile.x == mid or tile.y == mid - 1 or tile.y == mid
				if on_avenue:
					color.r = clampf(1.0 - float(outside - 3) / float(MARGIN - 3), 0.0, 1.0)
				# bare earth under the wall
				color.g = 0.7 if outside <= 2 else 0.0
			image.set_pixel(px, py, color)
	return image


## Stable pseudo-random value in 0..999 for a tile.
static func tile_hash(tile: Vector2i, salt: int = 0) -> int:
	var h := (tile.x * 73856093) ^ (tile.y * 19349663) ^ (salt * 83492791)
	h = (h ^ (h >> 13)) * 1274126177
	return absi(h ^ (h >> 16)) % 1000


## Decorative props for the free tiles: an Array of
## { "prop": String, "tile": Vector2i, "offset": Vector2, "rotation": float, "scale": float }.
## Never on a building, and only the plaza's market props stand on a road;
## greenery is denser towards the wall so the middle of the city stays open.
static func prop_spots(buildings: Array, city_size: int) -> Array[Dictionary]:
	var spots: Array[Dictionary] = []
	var roads := road_tiles(buildings, city_size)
	var occupied := occupied_tiles(buildings)
	@warning_ignore("integer_division")
	var mid := city_size / 2
	# lamp posts on both sides of the avenues, leaning in over the road
	for i in range(1, city_size, 4):
		for side: int in [mid - 2, mid + 1]:
			var inward := 0.36 if side == mid - 2 else -0.36
			var lamps: Array[Dictionary] = [
				{"tile": Vector2i(side, i), "offset": Vector2(inward, 0.0), "rotation": 0.0 if inward > 0.0 else PI},
				{"tile": Vector2i(i, side), "offset": Vector2(0.0, inward), "rotation": -signf(inward) * PI / 2.0},
			]
			for lamp in lamps:
				var tile: Vector2i = lamp.tile
				if occupied.has(tile) or roads.has(tile):
					continue
				lamp["prop"] = "prop_lamp"
				lamp["scale"] = 1.0
				spots.append(lamp)
				occupied[tile] = true
	# market life in the corners of the plaza (the only props that stand on cobbles)
	var plaza := plaza_rect(buildings, city_size)
	var corners: Dictionary[String, Vector2i] = {
		"prop_stall_a": Vector2i(plaza.position.x, plaza.end.y - 1),
		"prop_well": Vector2i(plaza.end.x - 1, plaza.end.y - 1),
		"prop_stall_b": Vector2i(plaza.end.x - 1, plaza.position.y),
		"prop_cart": plaza.position,
	}
	for prop: String in corners:
		var tile := corners[prop]
		if in_city(tile, city_size) and not occupied.has(tile):
			spots.append({"prop": prop, "tile": tile, "offset": Vector2.ZERO, "rotation": 0.0, "scale": 1.0})
			occupied[tile] = true
	for y in city_size:
		for x in city_size:
			var tile := Vector2i(x, y)
			if occupied.has(tile) or roads.has(tile):
				continue
			var edge := mini(mini(x, y), mini(city_size - 1 - x, city_size - 1 - y))
			var roll := tile_hash(tile)
			var tree_chance := 260 if edge < 2 else (110 if edge < 5 else 35)
			var prop := ""
			if roll < tree_chance:
				prop = ["prop_tree_a", "prop_tree_b", "prop_tree_c", "prop_pine"][tile_hash(tile, 1) % 4]
			elif roll < tree_chance + 30:
				prop = "prop_bush"
			elif roll < tree_chance + 50:
				prop = "prop_flowers"
			elif roll < tree_chance + 62:
				prop = "prop_rock"
			if prop == "":
				continue
			spots.append({
				"prop": prop,
				"tile": tile,
				"offset": Vector2(tile_hash(tile, 2) - 500, tile_hash(tile, 3) - 500) / 2200.0,
				"rotation": tile_hash(tile, 4) / 1000.0 * TAU,
				"scale": 0.85 + tile_hash(tile, 5) / 1000.0 * 0.45,
			})
	return spots
