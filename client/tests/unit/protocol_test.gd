extends TestCase


func test_encode_decode_round_trip() -> void:
	var msg := Protocol.login("alice", "password123")
	assert_eq(Protocol.decode(Protocol.encode(msg)), msg)


func test_hello_carries_protocol_version() -> void:
	assert_eq(Protocol.hello(), {"type": "hello", "protocol": Protocol.VERSION})


func test_decode_rejects_non_messages() -> void:
	assert_eq(Protocol.decode("not json"), {}, "garbage")
	assert_eq(Protocol.decode("[1, 2]"), {}, "array")
	assert_eq(Protocol.decode("{\"no_type\": 1}"), {}, "missing type")


func test_authentication_shapes() -> void:
	assert_eq(Protocol.login("alice", "password123"), {"type": "login", "name": "alice", "password": "password123"})
	assert_eq(Protocol.resume("token"), {"type": "resume", "token": "token"})


func test_upgrade_message_shapes() -> void:
	assert_eq(Protocol.upgrade_building(2), {"type": "upgrade_building", "building_id": 2})
	assert_eq(Protocol.cancel_upgrade(2), {"type": "cancel_upgrade", "building_id": 2})


func test_city_update_refreshes_game_state() -> void:
	var net: Node = load("res://scripts/net/net.gd").new()
	var city: Dictionary = {"size": 40, "buildings": []}
	net._handle({"type": "city_update", "city": city})
	assert_eq(GameState.city, city)
	net.free()


func test_construction_message_shape() -> void:
	assert_eq(Protocol.build_building("farm", 0, 38), {"type": "build_building", "kind": "farm", "x": 0, "y": 38})
