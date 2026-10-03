extends SceneTree
## End-to-end smoke test against a running kingdom server: connect, log in,
## receive the city and render it. scripts/verify.sh starts the server first.
##   godot --headless --path client -s res://tests/e2e_login.gd -- ws://127.0.0.1:7777/ws

const TIMEOUT_S := 10.0

var _net: Node
var _elapsed := 0.0
var _upgrade_requested := false


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var url: String = args[0] if args.size() > 0 else "ws://127.0.0.1:7777/ws"
	# Our own instance of the Net script, so the test doesn't depend on autoloads.
	_net = load("res://scripts/net/net.gd").new()
	root.add_child(_net)
	_net.status_changed.connect(func(t: String) -> void: print("net: ", t))
	_net.server_error.connect(func(code: String, m: String) -> void: _fail("server error %s: %s" % [code, m]))
	_net.city_received.connect(_on_city)
	_net.login("e2e_bot", "e2e-password", url)


func _process(delta: float) -> bool:
	_elapsed += delta
	if _elapsed > TIMEOUT_S:
		_fail("timed out after %.0fs" % TIMEOUT_S)
	return false


func _on_city(city: Dictionary) -> void:
	if not city.has("as_of") or not city.has("rates_per_hour") or not city.has("capacity"):
		_fail("missing resource accounting snapshot fields")
		return
	if not _upgrade_requested:
		_upgrade_requested = true
		for building: Dictionary in city.buildings:
			if building.kind == "city_hall":
				_net.send(Protocol.upgrade_building(int(building.id)))
				return
		_fail("missing City Hall")
		return
	var has_upgrade := false
	for building: Dictionary in city.buildings:
		if building.kind == "city_hall" and building.state == "upgrading":
			has_upgrade = building.started_at != null and building.completes_at != null
	if not has_upgrade:
		_fail("upgrade did not push a renderable city_update")
		return
	var view: Node = load("res://scenes/city.tscn").instantiate()
	root.add_child(view)
	view.render_city(city)
	var expected: int = city.buildings.size()
	if expected == 0 or view.building_count() != expected:
		_fail("rendered %d buildings, expected %d" % [view.building_count(), expected])
		return
	print("E2E OK: logged in, upgraded City Hall and rendered %d buildings" % expected)
	quit(0)


func _fail(reason: String) -> void:
	printerr("E2E FAIL: ", reason)
	quit(1)
