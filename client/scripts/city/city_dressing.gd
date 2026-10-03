class_name CityDressing
extends Node3D
## Everything around and between the buildings that is pure decoration: the
## terrain with its road mask, the river, the city wall, the forests and the
## props on free tiles. Models come from tools/blender/build_scenery.py.
## Holds no game state; rebuild it with refresh() whenever the city changes.

const SCENERY_DIR := "res://assets/models/scenery/"
const GROUND_SHADER := "res://assets/shaders/ground.gdshader"
const WATER_SHADER := "res://assets/shaders/water.gdshader"
const TEXTURE_DIR := "res://assets/textures/"
const WATER_LEVEL := -0.35
const WATER_SIZE := 224.0

var _ground_material: ShaderMaterial
var _props := Node3D.new()
var _built := false


## Update roads, worn ground and props for `buildings` (protocol BuildingView
## dictionaries) in a square city of `city_size` tiles.
func refresh(buildings: Array, city_size: int) -> void:
	if not _built:
		_build_static()
	var mask := ImageTexture.create_from_image(CityRoads.build_mask(buildings, city_size))
	_ground_material.set_shader_parameter(&"road_mask", mask)
	_ground_material.set_shader_parameter(&"mask_half_extent", city_size / 2.0 + CityRoads.MARGIN)
	for child in _props.get_children():
		_props.remove_child(child)
		child.queue_free()
	for spot: Dictionary in CityRoads.prop_spots(buildings, city_size):
		var node := _load_model(spot.prop)
		if node == null:
			continue
		var tile: Vector2i = spot.tile
		var offset: Vector2 = spot.offset
		node.position = CityLayout.footprint_center(tile.x, tile.y, 1, city_size) + Vector3(offset.x, 0.0, offset.y)
		node.rotation.y = spot.rotation
		node.scale = Vector3.ONE * float(spot.scale)
		_props.add_child(node)


func prop_count() -> int:
	return _props.get_child_count()


func _build_static() -> void:
	_built = true
	_ground_material = ShaderMaterial.new()
	_ground_material.shader = load(GROUND_SHADER)
	for key: String in ["grass", "dirt", "cobble", "rock"]:
		_ground_material.set_shader_parameter(key + "_tex", load(TEXTURE_DIR + "ground_%s.png" % key))
	var noise: Texture2D = load(TEXTURE_DIR + "noise.png")
	_ground_material.set_shader_parameter(&"noise_tex", noise)

	var terrain := _load_model("terrain", false)
	if terrain:
		terrain.name = "Terrain"
		_override_material(terrain, _ground_material)
		add_child(terrain)
	else:
		# no generated terrain: keep at least a flat lawn under the city
		var plane := MeshInstance3D.new()
		var mesh := PlaneMesh.new()
		mesh.size = Vector2(WATER_SIZE, WATER_SIZE)
		plane.mesh = mesh
		plane.material_override = _ground_material
		plane.name = "Terrain"
		add_child(plane)

	var water := MeshInstance3D.new()
	var water_mesh := PlaneMesh.new()
	water_mesh.size = Vector2(WATER_SIZE, WATER_SIZE)
	water.mesh = water_mesh
	var water_material := ShaderMaterial.new()
	water_material.shader = load(WATER_SHADER)
	water_material.set_shader_parameter(&"noise_tex", noise)
	water.material_override = water_material
	water.position.y = WATER_LEVEL
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	water.name = "Water"
	add_child(water)

	for model: String in ["city_wall", "scatter"]:
		var node := _load_model(model)
		if node:
			node.name = model.to_pascal_case()
			add_child(node)
	_props.name = "Props"
	add_child(_props)


func _load_model(model: String, atlas: bool = true) -> Node3D:
	var path := SCENERY_DIR + model + ".glb"
	if not ResourceLoader.exists(path):
		return null
	var scene: PackedScene = load(path)
	var node: Node3D = scene.instantiate()
	if atlas:
		BuildingFactory.apply_atlas(node)
	return node


func _override_material(node: Node, material: Material) -> void:
	if node is MeshInstance3D:
		(node as MeshInstance3D).material_override = material
	for child in node.get_children():
		_override_material(child, material)
