class_name CityLayout
## Maps city tile coordinates to world space. One tile = 1 world unit, the
## city grid is centred on the origin, +x is east and +z is south.

const TILE_SIZE := 1.0


## World-space centre (at ground level) of a building footprint whose top-left
## tile is (x, y).
static func footprint_center(x: int, y: int, footprint: int, city_size: int) -> Vector3:
	var half_city := city_size * TILE_SIZE / 2.0
	var half_fp := footprint * TILE_SIZE / 2.0
	return Vector3(x * TILE_SIZE + half_fp - half_city, 0.0, y * TILE_SIZE + half_fp - half_city)


## Tile containing a world-space point, or Vector2i(-1, -1) if outside.
static func world_to_tile(point: Vector3, city_size: int) -> Vector2i:
	var half_city := city_size * TILE_SIZE / 2.0
	var tx := floori((point.x + half_city) / TILE_SIZE)
	var ty := floori((point.z + half_city) / TILE_SIZE)
	if tx < 0 or ty < 0 or tx >= city_size or ty >= city_size:
		return Vector2i(-1, -1)
	return Vector2i(tx, ty)
