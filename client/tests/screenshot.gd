extends SceneTree
## Render a city fixture with the real renderer and save a PNG, so agents can
## visually check scenes and models. Needs a GPU/window (not --headless).
##   godot --path client -s res://tests/screenshot.gd -- <out.png> [fixture.json] [camera_distance] [focus_x] [focus_z]

const DEFAULT_FIXTURE := "res://tests/fixtures/showcase_city.json"
const WARMUP_FRAMES := 30

var _out := ""
var _frames := 0


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	_out = args[0] if args.size() > 0 else "user://screenshot.png"
	var fixture: String = args[1] if args.size() > 1 else DEFAULT_FIXTURE
	var city: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(fixture))
	root.size = Vector2i(1600, 900)
	var view: Node = load("res://scenes/city.tscn").instantiate()
	root.add_child(view)
	view.render_city(city)
	if args.size() > 2:
		var rig: CameraRig = view.get_node(^"CameraRig")
		rig.distance = float(args[2])
		if args.size() > 4:
			rig.position = Vector3(float(args[3]), 0.0, float(args[4]))
		rig._update_camera()


func _process(_delta: float) -> bool:
	_frames += 1
	if _frames == WARMUP_FRAMES:
		var err := root.get_texture().get_image().save_png(_out)
		print("saved %s (%s)" % [_out, error_string(err)])
		quit(0 if err == OK else 1)
	return false
