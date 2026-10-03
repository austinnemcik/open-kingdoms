extends TestCase

const SIZE := 40
const PLAZA_PROPS: Array[String] = ["prop_stall_a", "prop_stall_b", "prop_well", "prop_cart"]


func _building(id: int, kind: String, x: int, y: int, footprint: int) -> Dictionary:
	return {"id": id, "kind": kind, "x": x, "y": y, "footprint": footprint, "level": 1}


func _city() -> Array:
	return [
		_building(1, "city_hall", 18, 18, 4),
		_building(2, "farm", 5, 6, 2),
		_building(3, "barracks", 30, 28, 3),
	]


func test_occupied_tiles_cover_footprints() -> void:
	var occupied := CityRoads.occupied_tiles(_city())
	assert_eq(occupied.size(), 16 + 4 + 9)
	assert_true(occupied.has(Vector2i(21, 21)), "city hall corner")
	assert_true(not occupied.has(Vector2i(22, 21)), "just outside the city hall")


func test_door_tile_is_in_front_of_the_building() -> void:
	assert_eq(CityRoads.door_tile(_building(1, "farm", 5, 6, 2)), Vector2i(5, 8))
	assert_eq(CityRoads.door_tile(_building(1, "barracks", 30, 28, 3)), Vector2i(31, 31))


func test_avenues_and_plaza_are_roads() -> void:
	var roads := CityRoads.road_tiles(_city(), SIZE)
	for i in SIZE:
		assert_true(roads.has(Vector2i(i, 19)) and roads.has(Vector2i(20, i)), "avenue tile %d" % i)
	assert_true(roads.has(Vector2i(16, 16)) and roads.has(Vector2i(23, 23)), "plaza ring")
	assert_true(not roads.has(Vector2i(15, 15)), "outside the plaza")


func test_every_door_connects_to_the_road_network() -> void:
	var city := _city()
	var roads := CityRoads.road_tiles(city, SIZE)
	var occupied := CityRoads.occupied_tiles(city)
	for b: Dictionary in city:
		var tile := CityRoads.door_tile(b)
		assert_true(roads.has(tile), "door of %s is on a road" % b.kind)
		# walk road tiles only: the avenue crossing must be reachable
		var seen: Dictionary[Vector2i, bool] = {tile: true}
		var queue: Array[Vector2i] = [tile]
		while not queue.is_empty():
			var at: Vector2i = queue.pop_back()
			for step in CityRoads.NEIGHBOURS:
				var next := at + step
				if roads.has(next) and not seen.has(next) and not occupied.has(next):
					seen[next] = true
					queue.append(next)
		assert_true(seen.has(Vector2i(19, 0)), "%s reaches the north gate" % b.kind)


func test_paths_never_cross_buildings() -> void:
	# a wall of buildings between the farm and the avenues forces a detour
	var city := _city()
	for i in 4:
		city.append(_building(10 + i, "storehouse", 8, 2 + i * 2, 2))
	var with_detour := CityRoads.road_tiles(city, SIZE)
	var occupied := CityRoads.occupied_tiles(city)
	var avenue_or_plaza := CityRoads.road_tiles([city[0]], SIZE)
	for tile: Vector2i in with_detour:
		if not avenue_or_plaza.has(tile):
			assert_true(not occupied.has(tile), "path tile %s is under a building" % tile)
	assert_true(with_detour.has(CityRoads.door_tile(city[1])), "farm still connected")


func test_mask_matches_roads_and_buildings() -> void:
	var city := _city()
	var mask := CityRoads.build_mask(city, SIZE)
	assert_eq(mask.get_width(), SIZE + 2 * CityRoads.MARGIN)
	var m := CityRoads.MARGIN
	assert_true(mask.get_pixel(m + 19, m + 3).r > 0.9, "avenue is road")
	assert_true(mask.get_pixel(m + 3, m + 3).r < 0.1, "lawn is not road")
	assert_true(mask.get_pixel(m + 5, m + 6).g > 0.9, "farm wears the ground")
	assert_true(mask.get_pixel(m + 3, m + 3).b > 0.9, "inside the city")
	assert_true(mask.get_pixel(2, 2).b < 0.1, "outside the city")
	assert_true(mask.get_pixel(m + 19, m - 2).r > 0.9, "avenue runs out of the gate")
	assert_true(mask.get_pixel(m + 19, 0).r < 0.2, "and fades out")


func test_props_keep_off_buildings_and_roads() -> void:
	var city := _city()
	var roads := CityRoads.road_tiles(city, SIZE)
	var occupied := CityRoads.occupied_tiles(city)
	var spots := CityRoads.prop_spots(city, SIZE)
	assert_true(spots.size() > 40, "a 40x40 city gets a decent number of props")
	var used: Dictionary[Vector2i, bool] = {}
	for spot: Dictionary in spots:
		var tile: Vector2i = spot.tile
		assert_true(CityRoads.in_city(tile, SIZE), "prop inside the grid")
		assert_true(not occupied.has(tile), "prop %s on a building" % tile)
		if spot.prop not in PLAZA_PROPS:
			assert_true(not roads.has(tile), "prop %s on a road" % tile)
		assert_true(not used.has(tile), "two props on %s" % tile)
		used[tile] = true
		var offset: Vector2 = spot.offset
		assert_true(absf(offset.x) < 0.5 and absf(offset.y) < 0.5, "prop stays on its tile")


func test_plaza_gets_market_props() -> void:
	var props: Array = CityRoads.prop_spots(_city(), SIZE).map(func(s: Dictionary) -> String: return s.prop)
	for prop in PLAZA_PROPS:
		assert_true(prop in props, prop)
	assert_eq(CityRoads.plaza_rect(_city(), SIZE), Rect2i(16, 16, 8, 8))
	assert_eq(CityRoads.plaza_rect([], SIZE), Rect2i(16, 16, 8, 8), "no city hall")


func test_props_are_deterministic() -> void:
	assert_eq(CityRoads.prop_spots(_city(), SIZE), CityRoads.prop_spots(_city(), SIZE))


func test_every_prop_has_a_model() -> void:
	for spot: Dictionary in CityRoads.prop_spots(_city(), SIZE):
		var path: String = CityDressing.SCENERY_DIR + spot.prop + ".glb"
		assert_true(ResourceLoader.exists(path), "missing " + path)
	for model: String in ["terrain", "city_wall", "scatter"]:
		assert_true(ResourceLoader.exists(CityDressing.SCENERY_DIR + model + ".glb"), "missing " + model)
