extends TestCase

const KINDS: Array[String] = [
	"city_hall", "farm", "lumber_mill", "quarry", "goldmine", "storehouse",
	"barracks", "archery_range", "stable", "siege_workshop", "hospital", "academy",
]


func test_tier_for_level_steps_every_five_levels() -> void:
	assert_eq(BuildingFactory.tier_for_level(1), 1)
	assert_eq(BuildingFactory.tier_for_level(5), 1)
	assert_eq(BuildingFactory.tier_for_level(6), 2)
	assert_eq(BuildingFactory.tier_for_level(10), 2)
	assert_eq(BuildingFactory.tier_for_level(11), 3)
	assert_eq(BuildingFactory.tier_for_level(16), 4)
	assert_eq(BuildingFactory.tier_for_level(21), 5)
	assert_eq(BuildingFactory.tier_for_level(25), 5)


func test_tier_for_level_is_clamped() -> void:
	assert_eq(BuildingFactory.tier_for_level(0), 1, "level 0")
	assert_eq(BuildingFactory.tier_for_level(-7), 1, "negative level")
	assert_eq(BuildingFactory.tier_for_level(26), 5, "past the last tier")
	assert_eq(BuildingFactory.tier_for_level(1000), 5, "far past the last tier")


func test_model_path() -> void:
	assert_eq(BuildingFactory.model_path("farm", 3), "res://assets/models/farm_t3.glb")


func test_every_kind_has_every_tier() -> void:
	for kind in KINDS:
		for tier in range(1, BuildingFactory.TIER_COUNT + 1):
			var level := (tier - 1) * BuildingFactory.LEVELS_PER_TIER + 1
			assert_eq(BuildingFactory.resolve_model(kind, level), BuildingFactory.model_path(kind, tier), kind)


func test_unknown_kind_falls_back_to_placeholder() -> void:
	assert_eq(BuildingFactory.resolve_model("no_such_building", 12), "")
	var node := BuildingFactory.create("no_such_building", 2, 12)
	assert_true(node != null and node.get_child_count() == 1, "placeholder box")
	node.free()


func test_create_uses_the_shared_atlas_material() -> void:
	var node := BuildingFactory.create("farm", 2, 7)
	var meshes := node.find_children("*", "MeshInstance3D", true, false)
	assert_true(meshes.size() > 0, "model has a mesh")
	for mesh: MeshInstance3D in meshes:
		assert_true(mesh.material_override == BuildingFactory.atlas_material(), "atlas material")
	node.free()
