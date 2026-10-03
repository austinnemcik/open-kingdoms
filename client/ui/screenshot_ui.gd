extends SceneTree
## Render a UI scene to a PNG at an exact size (off-screen, so it can be larger
## than the monitor). Needs a GPU/window (not --headless).
##   godot --path client -s res://ui/screenshot_ui.gd -- <scene.tscn> <out.png> [width] [height]
##   e.g. res://ui/showcase.tscn docs/screenshots/ui_showcase.png 1980 1500
##        res://ui/hud_mock.tscn docs/screenshots/ui_hud_mock.png 1600 900

const WARMUP_FRAMES := 12

var _out := ""
var _viewport: SubViewport
var _frames := 0


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		printerr("usage: -- <scene.tscn> <out.png> [width] [height]")
		quit(2)
		return
	_out = args[1]
	var width := int(args[2]) if args.size() > 2 else 1600
	var height := int(args[3]) if args.size() > 3 else 900
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(width, height)
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(_viewport)
	var scene: Control = (load(args[0]) as PackedScene).instantiate()
	_viewport.add_child(scene)


func _process(_delta: float) -> bool:
	_frames += 1
	if _frames == WARMUP_FRAMES:
		var err := _viewport.get_texture().get_image().save_png(_out)
		print("saved %s (%s)" % [_out, error_string(err)])
		quit(0 if err == OK else 1)
	return false
