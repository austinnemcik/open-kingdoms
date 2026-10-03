extends Node3D
## The player's city in 3D. Renders whatever city snapshot it is given; it
## never changes game state itself.

const GROUND_COLOR := Color(0.36, 0.55, 0.28)

var city_size := 0
var _pending_city: Dictionary = {}

@onready var _buildings: Node3D = $Buildings
@onready var _camera_rig: CameraRig = $CameraRig
@onready var _resources_label: Label = %ResourcesLabel
@onready var _player_label: Label = %PlayerLabel


func _ready() -> void:
	var game_state := get_node_or_null(^"/root/GameState")
	if not _pending_city.is_empty():
		render_city(_pending_city)
	elif game_state and not game_state.city.is_empty():
		_player_label.text = game_state.player_name
		render_city(game_state.city)


## Replace the rendered city with `city` (a protocol CityView dictionary).
## Safe to call before the node enters the tree.
func render_city(city: Dictionary) -> void:
	if not is_node_ready():
		_pending_city = city
		return
	_pending_city = {}
	city_size = int(city.size)
	_camera_rig.bounds = city_size / 2.0
	_build_ground()
	for child in _buildings.get_children():
		_buildings.remove_child(child)
		child.queue_free()
	for b: Dictionary in city.buildings:
		var node := BuildingFactory.create(b.kind, int(b.footprint))
		node.name = "Building%d" % int(b.id)
		node.position = CityLayout.footprint_center(int(b.x), int(b.y), int(b.footprint), city_size)
		node.add_child(_make_label("%s  Lv %d" % [b.name, int(b.level)], float(b.footprint)))
		_buildings.add_child(node)
	var r: Dictionary = city.resources
	_resources_label.text = "Food %d   Wood %d   Stone %d   Gold %d" % [r.food, r.wood, r.stone, r.gold]


func building_count() -> int:
	return _buildings.get_child_count()


func _build_ground() -> void:
	var existing := get_node_or_null(^"Ground")
	if existing:
		existing.free()
	var plane := PlaneMesh.new()
	plane.size = Vector2(city_size, city_size)
	var material := StandardMaterial3D.new()
	material.albedo_color = GROUND_COLOR
	plane.material = material
	var ground := MeshInstance3D.new()
	ground.name = "Ground"
	ground.mesh = plane
	add_child(ground)


func _make_label(text: String, footprint: float) -> Label3D:
	var label := Label3D.new()
	label.text = text
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.pixel_size = 0.006
	label.font_size = 48
	label.outline_size = 12
	label.position.y = footprint * 0.9 + 0.5
	return label
