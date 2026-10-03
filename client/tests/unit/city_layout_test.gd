extends TestCase


func test_footprint_center_is_centred_on_origin() -> void:
	# A 4x4 building at (18, 18) in a 40-tile city covers tiles 18..21, so its
	# centre is exactly the city centre.
	assert_almost_eq(CityLayout.footprint_center(18, 18, 4, 40), Vector3.ZERO)


func test_top_left_tile() -> void:
	assert_almost_eq(CityLayout.footprint_center(0, 0, 1, 40), Vector3(-19.5, 0, -19.5))


func test_world_to_tile_round_trip() -> void:
	var p := CityLayout.footprint_center(7, 12, 1, 40)
	assert_eq(CityLayout.world_to_tile(p, 40), Vector2i(7, 12))
	assert_eq(CityLayout.world_to_tile(Vector3(100, 0, 0), 40), Vector2i(-1, -1), "outside")
