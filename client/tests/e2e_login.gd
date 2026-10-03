extends SceneTree
## End-to-end smoke test against a running kingdom server: connect, log in,
## receive the city and render it. scripts/verify.sh starts the server first.
##   godot --headless --path client -s res://tests/e2e_login.gd -- ws://127.0.0.1:7777/ws

const TIMEOUT_S := 10.0

var _net: Node
var _elapsed := 0.0


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var url: String = args[0] if args.size() > 0 else "ws://127.0.0.1:7777/ws"
	# Our own instance of the Net script, so the test doesn't depend on autoloads.
	_net = load("res://scripts/net/net.gd").new()
	root.add_child(_net)
	_net.status_changed.connect(func(t: String) -> void: print("net: ", t))
	_net.server_error.connect(func(code: String, m: String) -> void: _fail("server error %s: %s" % [code, m]))
	_net.city_received.connect(_on_city)
	_net.login("e2e_bot", url)


func _process(delta: float) -> bool:
	_elapsed += delta
	if _elapsed > TIMEOUT_S:
		_fail("timed out after %.0fs" % TIMEOUT_S)
	return false


func _on_city(city: Dictionary) -> void:
	var view: Node = load("res://scenes/city.tscn").instantiate()
	root.add_child(view)
	view.render_city(city)
	var expected: int = city.buildings.size()
	if expected == 0 or view.building_count() != expected:
		_fail("rendered %d buildings, expected %d" % [view.building_count(), expected])
		return
	print("E2E OK: logged in and rendered %d buildings" % expected)
	quit(0)


func _fail(reason: String) -> void:
	printerr("E2E FAIL: ", reason)
	quit(1)
