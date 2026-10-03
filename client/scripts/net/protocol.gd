class_name Protocol
## GDScript mirror of server/crates/protocol. Messages are JSON objects with a
## snake_case "type" field. Keep in sync with the Rust crate and bump VERSION
## together with PROTOCOL_VERSION on breaking changes.

# City snapshots carry resources, rates_per_hour, capacity (food/wood/stone/gold)
# Buildings carry state (ready/upgrading/under_construction), started_at and completes_at (nullable Unix seconds).
# city_update carries the same full city as city_state; builder_slots is free capacity.
# and as_of (Unix seconds), plus size and buildings. Production is server-owned.
# Errors may include rate_limited when authentication budgets are exhausted.
const VERSION := 2


static func encode(msg: Dictionary) -> String:
	assert(msg.has("type"), "protocol messages need a type")
	return JSON.stringify(msg)


## Returns the decoded message, or an empty Dictionary if the text is not a
## JSON object with a string "type".
static func decode(text: String) -> Dictionary:
	var json := JSON.new()
	if json.parse(text) != OK:
		return {}
	var parsed: Variant = json.data
	if parsed is Dictionary and parsed.get("type") is String:
		return parsed
	return {}


static func hello() -> Dictionary:
	return {"type": "hello", "protocol": VERSION}


static func login(player_name: String, password: String) -> Dictionary:
	return {"type": "login", "name": player_name, "password": password}


static func get_city() -> Dictionary:
	return {"type": "get_city"}


static func resume(token: String) -> Dictionary:
	return {"type": "resume", "token": token}


static func upgrade_building(building_id: int) -> Dictionary:
	return {"type": "upgrade_building", "building_id": building_id}


static func cancel_upgrade(building_id: int) -> Dictionary:
	return {"type": "cancel_upgrade", "building_id": building_id}


static func build_building(kind: String, x: int, y: int) -> Dictionary:
	return {"type": "build_building", "kind": kind, "x": x, "y": y}
